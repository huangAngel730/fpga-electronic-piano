"""Strict score integration gate: old physical gates plus exact two UART ports."""
from __future__ import annotations
import argparse,hashlib,inspect,json,math,re,types,xml.etree.ElementTree as ET
from pathlib import Path
import prepare_138k_score_receive_integration as prepared
import check_138k_waveform_integration_build_v3 as original
import check_138k_waveform_integration_v3_reset_profile as reset_profile
import check_138k_waveform_integration_v3_final as final_wave
from platform_profiles import profile as old_profile
ROOT=Path(__file__).resolve().parents[2]
NEW_SYNC=('u_score_receiver/receiver','rx_meta','rx_sync')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def xml_resource(path):
    try:
        root=ET.parse(path).getroot()
        def find(name):
            x=[n for n in root.iter() if n.attrib.get('name')==name]
            if len(x)!=1:raise ValueError('resource scope '+name)
            return x[0]
        def count(node,key):
            val=node.attrib.get('T_'+key,node.attrib.get(key,'0'))
            if not re.fullmatch(r'\d+(?:\(\d+\))?',val):raise ValueError('countsyntax')
            return int(val.split('(')[0])
        score=find('u_score_receiver');audio=find('g_polyphonic.u_audio_core');wave=find('u_waveform');bridge=find('u_wave_bridge')
        if (count(audio,'Bsram'),count(audio,'Ssram'),count(wave,'Bsram'),count(wave,'Ssram'),count(bridge,'Bsram'),count(bridge,'Ssram'))!=(20,32,3,0,0,28):raise ValueError('original sound/wave resource altered')
        for node in [score,wave,bridge]:
            for k,v in node.attrib.items():
                if k.startswith(('T_MULT','MULT','T_DSP','DSP')) and int(v.split('(')[0]):raise ValueError('new score/wave DSP unexpectedly mapped')
        expectedRAM=23+count(score,'Bsram');expectedSS=89+count(score,'Ssram')
        if count(root,'Bsram')!=expectedRAM or count(root,'Ssram')!=expectedSS:raise ValueError('resource outside original+score scope')
        facts={'audio_BSRAM':20,'audio_SSRAM':32,'wave_BSRAM':3,'observer_SSRAM':28,'score_actual_BSRAM':count(score,'Bsram'),'score_actual_SSRAM':count(score,'Ssram'),'score_actual_registers':count(score,'Register'),'score_actual_LUT':count(score,'Lut'),'total_BSRAM':expectedRAM,'total_SSRAM':expectedSS,'no_added_DSP':True}
        return facts,expectedRAM,[]
    except (OSError,ValueError,ET.ParseError) as exc:return {},None,['score hierarchy: '+str(exc)]

def pins_profile(name):
    p=old_profile(name)
    for port,ball,direction in [('score_uart_rx','R18','in'),('score_uart_tx','T18','out')]:
        p['pins'][port]={'Loc./Bank':ball+'/4','Constraint':'Y','Dir.':direction,'Diff Pair':'-','IO Type':'LVCMOS33','BankVccio':'3.3','Drive':'OFF' if direction=='in' else '8','Pull Mode':'UP'}
    return p

def baseline(scoreRAM):
    old=reset_profile.reset_profile_baseline()
    # The inherited generated reset gate already carries exactly4 reset CLEAR entries.
    source=inspect.getsource(original.baseline_gate.visual.check)
    anchor='    expected_false = {"set_false_path -from [get_ports {sys_rst_n}]"}\n'
    if source.count(anchor)!=1:raise ValueError('base visual template changed')
    source=source.replace(anchor,anchor+'    expected_false.update(APPROVED_RESET_INPUTS)\n',1)
    env=dict(original.baseline_gate.visual.check.__globals__)
    reset=json.loads((original.prepared.SCOPE/'revision_manifest.json').read_bytes())['additional_exact_falsepaths'];env['APPROVED_RESET_INPUTS']=tuple(x.replace('u_visual/','') for x in reset);env['FIRST_STAGES']=original.baseline_gate.visual.FIRST_STAGES+original.ADDITIONAL_STAGES+(NEW_SYNC,);env['BUSS']=original.baseline_gate.visual.BUSS+(original.ADDITIONAL_BUS,);exec(compile(source,'<score_fixed_original_visual_checks_plus_reset4_and_UART1>','exec'),env)
    visual=types.SimpleNamespace(check=env['check'],FIRST_STAGES=env['FIRST_STAGES'],BUSS=env['BUSS'])
    env2=dict(original.baseline_gate.review.__globals__);env2['visual']=visual
    def profile(name):
        p=pins_profile(name);p['BSRAM']=scoreRAM if scoreRAM is not None else -1;return p
    env2['profile']=profile
    return types.FunctionType(original.baseline_gate.review.__code__,env2)

def exact_extra_commands():
    return ['set_false_path -to [get_pins {u_score_receiver/receiver/rx_meta_s0/D}]',
    'report_timing -setup -from [get_regs {u_score_receiver/receiver/rx_meta_s0}] -to [get_regs {u_score_receiver/receiver/rx_sync_s0}] -max_paths 1',
    'report_timing -hold -from [get_regs {u_score_receiver/receiver/rx_meta_s0}] -to [get_regs {u_score_receiver/receiver/rx_sync_s0}] -max_paths 1',
    'set_output_delay -clock sys_clk -max 5.000 [get_ports {score_uart_tx}]',
    'set_output_delay -clock sys_clk -min 0.000 [get_ports {score_uart_tx}]']

def directed(timing,usage,sdc,expectedSS):
    normalize=lambda t:{re.sub(r'\s+',' ',x.strip()) for x in t.splitlines() if x.strip() and not x.lstrip().startswith('#')}
    parent=(original.prepared.SCOPE/'audio_visual_hold055.sdc').read_text(encoding='utf-8');errors=[]
    if normalize(sdc)!=normalize(parent)|set(exact_extra_commands()):errors.append('old timing changed or additional score constraints not exact')
    rows=original.baseline_gate.parsed(timing);errs,proof=final_wave.dedicated_paths(rows);errors+=errs
    active={r[2] for s,r in rows if s=='SDC_Report' and len(r)==3 and r[1]=='Actived'}
    if not set(exact_extra_commands())<=active:errors.append('new UART constraints not active')
    for typ in ['Setup','Hold']:
        cmds=[r[2] for sec,r in rows if sec=='SDC_Report' and len(r)==3 and r[1]=='Actived' and r[2].startswith('report_timing -'+typ.lower()+' ')];wanted=exact_extra_commands()[1 if typ=='Setup' else 2]
        if cmds.count(wanted)!=1:errors.append('dedicated UART sync command missing/duplicate');continue
        name=typ+'_Slack_Table'+str(cmds.index(wanted)+1);paths=[r for s,r in rows if s==name and len(r)>=4 and r[0].isdigit()]
        if len(paths)!=1 or paths[0][2]!='u_score_receiver/receiver/rx_meta_s0/Q' or paths[0][3]!='u_score_receiver/receiver/rx_sync_s0/D' or float(paths[0][1])<0:errors.append('dedicated UART sync path missing/negative')
        proof[name]=paths
    matches=re.findall(r'--SSRAM\(RAM16\)\s*\|\s*(\d+)',usage)
    if matches!=[str(expectedSS)]:errors.append('physical SSRAM does not match exact hierarchy')
    return errors,proof

def review(run):
    run=run.resolve();run.relative_to((prepared.BUILD_ROOT/'runs').resolve());project=run/'project';prepared.validate(project);b=json.loads((run/'build_receipt.json').read_bytes());errors=[]
    if b.get('version')!='score_receive_integration_1' or b.get('attempt_count')!=1 or b.get('exit_code')!=0 or b.get('timed_out') or b.get('programmed') is not False or not 1<=b.get('timeout_seconds',0)<=1800:errors.append('singlebounded build contract')
    for key,p in [('frozen_sha256_before',project/'frozen_receipt.json'),('frozen_sha256_after',project/'frozen_receipt.json'),('log_sha256',run/'build.log')]:
        if b.get(key)!=sha(p):errors.append('runidentity '+key)
    for name,digest in b.get('tools_and_sources_sha256',{}).items():
        if not Path(name).is_file() or sha(name)!=digest:errors.append('executedtool/source changed '+name)
    log=(run/'build.log').read_text(encoding='utf-8',errors='replace')
    for marker in ['GowinSynthesis finish','Placement and routing completed','Timing analysis completed','Bitstream generation completed']:
        if marker not in log:errors.append('incomplete '+marker)
    if re.search(r'(?:ERROR|FATAL)\s*[:(]',log):errors.append('ERROR/FATAL')
    paths={'timing':project/'impl/pnr/audio_visual_coexistence_top_tr_content.html','usage':project/'impl/pnr/audio_visual_coexistence_top.rpt.txt','pins':project/'impl/pnr/audio_visual_coexistence_top.pin.html','command':project/'impl/pnr/cmd.do','config':project/'impl/pnr/device.cfg','bitstream':project/'impl/pnr/audio_visual_coexistence_top.fs'}
    missing=[name for name,q in paths.items() if not q.is_file()]
    if missing:return {'passed':False,'errors':errors+['missing'+str(missing)],'board_release_allowed':False}
    facts,RAM,rs_errors=xml_resource(project/'impl/gwsynthesis/audio_visual_coexistence_top_syn_rsc.xml');errors+=rs_errors;text={n:q.read_text(encoding='utf-8',errors='replace') for n,q in paths.items() if n!='bitstream'};sdc=(project/'inputs/constraints/audio_visual_hold055.sdc').read_text(encoding='utf-8');base=baseline(RAM);timing=base('138k_c40_hold065',text['timing'],text['usage'],text['pins'],sdc,text['command'],text['config']);errors+=timing['errors'];extra,proof=directed(text['timing'],text['usage'],sdc,facts.get('total_SSRAM',-1));errors+=extra
    if not isinstance(timing['slacks']['Setup'],(float,int)) or timing['slacks']['Setup']<0.5:errors.append('Setup0.5floor')
    return {'date':'2026-10-09','version':'score_receive_integration_1','passed':not errors,'errors':errors,'report_gate':timing,'actual_hierarchy':facts,'additional_UART_and_parent_directed_proof':proof,'new_input_pins_engineering_only':{'RX':'R18 Bank4 J9-5','TX':'T18 Bank4 J9-6'},'old_MIDI_STAT_preserved':True,'playback_connected':False,'artifact_sha256':{n:sha(q) for n,q in paths.items()},'board_release_allowed':False}
if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('run',type=Path);r=review(cli.parse_args().run);print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(0 if r['passed'] else 1)
