"""40MHz subsystem capture; no new algorithm, PLL/HDMI simulation or PnR."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import zipfile
from platform_profiles import profile

ROOT=Path(__file__).resolve().parents[2]
SCOPE=ROOT/'code/tb/board/platform_audio_acceptance_20261005'
CAD=Path('D:/Gowin/oss-cad-suite')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def audited_observation(path,expected_hz):
    counts={'REQUEST':0,'COMMIT':0,'STATE':0,'RESET':0}
    pending=set()
    seen=set()
    epoch=0
    rows=path.read_text(encoding='ascii').splitlines()
    if not rows:
        raise ValueError('empty observation')
    meta=json.loads(rows[0])
    if meta!={'tag':'META','schema':1,'sys_hz':expected_hz,'sample_hz':48000,'physical_PLL_test':False,'analog_test':False}:
        raise ValueError('wrong capture profile/schema')
    finished=False
    for line in rows[1:]:
        r=json.loads(line)
        if finished:
            raise ValueError('records after END')
        tag=r['tag']
        if tag=='RESET':
            if r['epoch']!=epoch+1:
                raise ValueError('reset epoch order')
            epoch=r['epoch']
            pending.clear()
        elif tag in ('REQUEST','COMMIT'):
            if r['epoch']!=epoch:
                raise ValueError('request/result epoch mismatch')
            key=(epoch,r['request_id'])
            if tag=='REQUEST':
                if key in seen:
                    raise ValueError('duplicate logical sample request')
                pending.add(key)
                seen.add(key)
            else:
                if key not in pending:
                    raise ValueError('duplicate/unrequested PCM commit')
                pending.remove(key)
                if not (-8388608<=r['pcm_left']<=8388607 and -8388608<=r['pcm_right']<=8388607):
                    raise ValueError('PCM24 range')
        elif tag=='STATE':
            if r['lane'] not in range(4) or r['epoch']!=epoch or r['velocity'] not in range(1024):
                raise ValueError('voice identity/width')
            for field,bits in [('level_q16',32),('start_q16',32),('peak_q16',32),('sustain_q16',32),('step_q16_twos33',33),('phase_acc',32),('dds_fcw',32)]:
                if not 0<=int(r[field],16)<1<<bits:
                    raise ValueError('nonfinite/unknown or bad fixed width '+field)
        elif tag=='END':
            if counts!=r['counts'] or pending or counts['COMMIT']<512 or counts['STATE']<2048:
                raise ValueError('truncated/nonvacuous/drain counts')
            finished=True
        else:
            raise ValueError('unknown observation record')
        if tag in counts:
            counts[tag]+=1
    if not finished:
        raise ValueError('missing END')
    return {'counts':counts,'independent_ADSR_reference_not_checked':True,
            'sys_hz':expected_hz,'logical_sample_hz':48000}


def audit_pair(observation,raw_capture,expected_hz):
    result=audited_observation(observation,expected_hz)
    observed=[]
    for line in observation.read_text(encoding='ascii').splitlines():
        r=json.loads(line)
        if r['tag']=='COMMIT':
            observed.append((r['epoch'],r['cycle'],r['request_id'],r['pcm_left'],r['pcm_right']))
    recorded=[]
    epoch=0
    def signed24(value):
        v=int(value,16)
        return v-(1<<24) if v&(1<<23) else v
    for line in raw_capture.read_text(encoding='ascii').splitlines():
        f=line.split()
        if f[0]=='R':
            epoch=int(f[2])
        elif f[0]=='M':
            recorded.append((epoch,int(f[1]),int(f[2]),signed24(f[3]),signed24(f[4])))
    if observed!=recorded or not recorded:
        raise ValueError('observation PCM/request/cycle differs from actual F capture')
    result['all_observed_commits_match_raw_F_capture']=True
    return result


def main():
    cli=argparse.ArgumentParser()
    cli.add_argument('--output',type=Path,required=True)
    cli.add_argument('--profile',default='138k_c40_hold055',choices=['138k_c40_hold055','138k_c40_hold065'])
    a=cli.parse_args()
    p=profile(a.profile)
    out=a.output.resolve()
    out.relative_to(ROOT/'code/output')
    out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy()
    env['PATH']=str(CAD/'bin')+';'+str(CAD/'lib')+';'+env['PATH']
    env['PYTHONDONTWRITEBYTECODE']='1'
    runs={}
    record={'profile':a.profile,'passed':False,'physical_PLL_or_HDMI_test':False,
            'source_H40_STA_remains_failed':True,'not_a_new_I_L_build':True}
    def run(name,cmd,timeout=90):
        log=out/(name+'.log')
        with log.open('wb') as f:
            r=subprocess.run(list(map(str,cmd)),cwd=out,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
        text=log.read_text(encoding='utf-8',errors='replace')
        runs[name]={'exit':r.returncode,'command':list(map(str,cmd)),'log_sha256':sha(log)}
        print(name,r.returncode,text[-600:],flush=True)
        if r.returncode:
            raise RuntimeError(name)
        return text
    try:
        archive=ROOT/'code/rtl/138K_try/clock_trials_20261005/M3_138K_clock40_evidence_20261005.zip'
        old_prefix='E:/FPGA/GAOYUNFPGA/138K_try/clock_trials_20261005/H_pll_core40_route2'
        inputs=[]
        with zipfile.ZipFile(archive) as z:
            manifest=json.loads(z.read('H_pll_core40_route2/input_manifest.json'))
            for item in manifest['inputs']:
                rel=item['path'].replace('\\','/')
                data=z.read('H_pll_core40_route2/'+rel)
                assert hashlib.sha256(data).hexdigest()==item['candidate_SHA256']
                target=out/rel
                target.parent.mkdir(parents=True,exist_ok=True)
                rebound=data.replace(old_prefix.encode(),out.as_posix().encode())
                if target.suffix in ('.sv','.v'):
                    for header in ('sine_table.svh','sustain_controller_ports.svh'):
                        rebound=rebound.replace((out.as_posix()+'/include/'+header).encode(),header.encode())
                target.write_bytes(rebound)
                inputs.append({'path':rel,'original_sha':item['candidate_SHA256'],'simulation_SHA':sha(target),
                               'adaptation':'path rebinding/include basename only'})
        record['archive_sha256']=sha(archive)
        record['frozen_simulation_inputs']=inputs
        sources=out/'sources'
        # Reconstruct the already accepted independent center bank from Git:
        # only module names and previously proved 6/4 settling waits differ.
        bank=subprocess.run(['git','show','e5eb025:code/rtl/board/polyphonic_envelope_bank.sv'],cwd=ROOT,capture_output=True,check=True).stdout.decode('utf-8')
        bank=bank.replace('module polyphonic_envelope_bank','module bank_reference',1).replace('polyphonic_event_router u_events','polyphonic_event_router_reference u_events',1)
        assert bank.count('delay_count<=3;phase<=SETTLE;')==1 and bank.count('phase<=SNAPSHOT;delay_count<=2;')==1
        bank=bank.replace('delay_count<=3;phase<=SETTLE;','delay_count<=6;phase<=SETTLE;',1).replace('phase<=SNAPSHOT;delay_count<=2;','phase<=SNAPSHOT;delay_count<=4;',1)
        expected='f407d8ee288d48946036ba4779e06ca16bf1e5f008a9d7a7e8b14529d9a570ff'
        assert hashlib.sha256(bank.encode()).hexdigest()==expected
        reference=out/'bank_reference.sv'
        reference.write_text(bank,encoding='utf-8',newline='\n')
        ys=out/'lower_allocator.ys'
        allocator=out/'allocator.v'
        ys.write_text('read_slang --top voice_allocator_4 '+(sources/'voice_allocator_4.sv').as_posix()+'\nproc\nopt\ntechmap\nopt\nwrite_verilog -noattr '+allocator.as_posix()+'\n',encoding='ascii')
        run('lower_allocator',[CAD/'bin/yosys.exe','-Q','-T','-s',ys],60)
        tb=ROOT/'code/tb/board/m3_midi_pcm_acceptance/tb_midi_pcm.sv'
        text=tb.read_text(encoding='utf-8')
        record['original_F_TB_sha256']=sha(tb)
        replacements=[('module tb_midi_pcm;','module tb_platform_audio_capture;'),
                      ('always #10 clk=~clk;','always #12.5 clk=~clk;'),
                      ('.SOURCE_ID(1)) input_a(','.SOURCE_ID(1),.CLK_HZ(40_000_000)) input_a('),
                      ('.SOURCE_ID(9)) input_second(','.SOURCE_ID(9),.CLK_HZ(40_000_000)) input_second('),
                      ('1041,1042,1042 clocks','833,833,834 clocks'),
                      ('cadence_index%3==0 ? 1041 : 1042','cadence_index%3==2 ? 834 : 833'),
                      ('cycle-last_frame_cycle==1041','cycle-last_frame_cycle==833'),
                      ('cycle-last_frame_cycle==1042','cycle-last_frame_cycle==834'),
                      ('repeat(1600)','repeat(1280)'),('1600-clock UART','1280-clock UART'),
                      ('while(ticks_left!=618)','while(ticks_left!=496)')]
        for old,new in replacements:
            assert old in text,old
            text=text.replace(old,new)
        observer=(SCOPE/'observer.sv.in').read_text(encoding='utf-8').replace('@SYS_HZ@',str(p['sys_hz']))
        finish='''$fdisplay(observation_fd,"{\\"tag\\":\\"END\\",\\"counts\\":{\\"REQUEST\\":%0d,\\"COMMIT\\":%0d,\\"STATE\\":%0d,\\"RESET\\":%0d}}",observation_requests,observation_commits,observation_states,observation_epoch);
        $fclose(observation_fd);'''
        assert text.count('$fclose(fd);test_passed=1;')==1
        text=text.replace('$fclose(fd);test_passed=1;','$fclose(fd);'+finish+'test_passed=1;',1)
        anchor='    task automatic check(input logic ok,input string label);'
        assert text.count(anchor)==1
        text=text.replace(anchor,observer+'\n'+anchor,1)
        staged_tb=out/'tb_platform_audio_capture.sv'
        staged_tb.write_text(text,encoding='utf-8',newline='\n')
        # Source ROM inputs are originals; TB file name binds the existing wave
        # parameter and velocity plusarg without changing arithmetic.
        (out/'wave.mem').write_bytes((out/'rom/piano_band_4x256_8191.mem').read_bytes())
        names=['audio_defs_pkg.sv','uart_rx.sv','performance_event_fifo.sv','midi_input.sv','midi_event_parser.sv','note_pitch.sv','sustain_control_contract_pkg.sv','sustain_controller.sv','performance_control_snapshot.sv','pitch_mod_fcw_pipeline.sv','pitch_mod_snapshot_pipeline.sv','dds_oscillator.sv','piano_dds_oscillator.sv','adsr_piano_envelope.sv','polyphonic_pcm_commit.sv','pcm_mixer_4voice.sv','pcm_result_hold.sv','pcm_frame_buffer.sv','pcm_clip_counter.sv','system_status_counters.sv','voice_gain_q15_candidate.sv','polyphonic_audio_core.sv','polyphonic_event_router.sv','polyphonic_envelope_bank.sv']
        files=[sources/n for n in names]+[allocator,reference,ROOT/'code/tb/board/system_control_pipeline_candidate/polyphonic_event_router_reference.sv']
        run('compile',[CAD/'bin/iverilog.exe','-g2012','-I',out/'include','-I',ROOT/'code/rtl/board','-s','tb_platform_audio_capture','-o',out/'capture.vvp',*files,staged_tb],90)
        log=run('run',[CAD/'bin/vvp.exe',out/'capture.vvp','+VELOCITY_ROM_PATH='+str(out/'rom/velocity_gain_rom.mem')],900)
        assert 'PASS F real UART FIFO allocator V1 CC64 PitchMod PCM' in log
        old=ROOT/'code/tb/board/m3_midi_pcm_acceptance/scoreboard.py'
        code=old.read_text(encoding='utf-8')
        assert code.count('>= 50000')==1 and code.count('in (1041, 1042)')==1
        code=code.replace('>= 50000','>= 40000',1).replace('in (1041, 1042)','in (833, 834)',1)
        scoreboard=out/'scoreboard40.py'
        scoreboard.write_text(code,encoding='utf-8',newline='\n')
        spec=importlib.util.spec_from_file_location('accepted_F_profile40_checker',scoreboard)
        model=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(model)
        record['existing_F_PCM_reference']=model.check_capture(out/'midi_pcm.capture',ROOT)
        record['observation']=audit_pair(out/'audio_observation.jsonl',out/'midi_pcm.capture',40_000_000)
        record.update(passed=True,observation_SHA=sha(out/'audio_observation.jsonl'),raw_F_SHA=sha(out/'midi_pcm.capture'),
                      compiled_inputs={str(f):sha(f) for f in files+[staged_tb]},
                      independent_ADSR_math_pending_M1=True,Gowin_run=False,production_modified=False)
        print('PASS 40MHz real UART FIFO PCM and read-only observation; independent ADSR model still M1 task',flush=True)
    finally:
        record['runs']=runs
        (out/'capture_review.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
