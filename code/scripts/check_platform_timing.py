"""Fail-closed profile-specific report gate. Never edits sources/constraints."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import types
import xml.etree.ElementTree as ET
from check_hdmi_link_report import ReportParser
import check_visual_full_path_report as visual
from platform_profiles import profile

STEM = 'audio_visual_coexistence_top'


def parsed(text):
    p = ReportParser()
    p.feed(text)
    return p.rows


def pin_check(text, wanted):
    rows = [r for section,r in parsed(text) if section=='Pinout_by_Port_Name']
    headers = [r for r in rows if r and r[0]=='Port Name']
    if len(headers)!=1 or len(set(headers[0]))!=len(headers[0]):
        return {}, ['pin table header missing/duplicate']
    h=headers[0]
    keys=['Diff Pair','Loc./Bank','Constraint','Dir.','IO Type','BankVccio','Pull Mode','Drive']
    if not all(k in h for k in keys):
        return {}, ['pin header required columns missing']
    actual={}
    errors=[]
    for r in rows:
        if len(r)==len(h) and r[0]!='Port Name':
            if r[0] in actual:
                errors.append('duplicate pin '+r[0])
            actual[r[0]]={k:r[h.index(k)] for k in keys}
    if set(actual)!=set(wanted):
        errors.append('physical port set differs from explicit profile')
    for name,value in wanted.items():
        if actual.get(name)!=value:
            errors.append('pin electrical/location mismatch: '+name)
    return actual,errors


def review(name, timing, usage, pin_html, sdc, command, config):
    p=profile(name)
    rows=parsed(timing)
    actual_pins,pin_errors=pin_check(pin_html,p['pins'])
    # Reuse the original 14 CDC second-stage and payload checks exactly; use a
    # private globals dictionary, never change the shared 60K gate's clocks.
    globals_copy=dict(visual.check.__globals__)
    globals_copy['EXPECTED_CLOCKS']={n:[f'{v[1]:.3f}',f'{v[2]:.3f}'] for n,v in p['clocks'].items()}
    globals_copy['analyze_pins']=lambda ignored:(actual_pins,pin_errors)
    gate=types.FunctionType(visual.check.__code__,globals_copy)
    errors, visual_facts=gate(timing.replace('u_visual/',''), usage)
    if '<Part Number>: '+p['part'] not in usage or '<Device Version>: '+p['version'] not in usage:
        errors.append('part/version mismatch')
    if '<Tool Version>: V1.9.11.03 Education' not in usage:
        errors.append('tool version mismatch')
    clocks=[r for s,r in rows if s=='Clock_Report' and r[0].isdigit()]
    if len(clocks)!=len(p['clocks']) or {r[1] for r in clocks}!=set(p['clocks']):
        errors.append('actual clock set/count differs from profile')
    for r in clocks:
        if r[1] not in p['clocks']:
            continue
        expected=p['clocks'][r[1]]
        try:
            observed=(r[2],float(r[3]),float(r[4]),r[8],r[9])
            if observed!=expected or float(r[5])!=0 or float(r[6])!=expected[1]/2:
                errors.append('actual clock type/master/object/waveform mismatch: '+r[1])
        except (IndexError,ValueError):
            errors.append('malformed clock row')
    active={r[2] for s,r in rows if s=='SDC_Report' and len(r)==3 and r[1]=='Actived'}
    hold=f"set_clock_uncertainty -hold {p['hold_uncertainty_ns']:.3f} -from [get_clocks {{sys_clk}}] -to [get_clocks {{sys_clk}}]"
    setup='set_clock_uncertainty -setup 1.000 -from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}]'
    if hold not in active or setup not in active:
        errors.append('exact setup/hold uncertainty missing')
    # Do not accept a candidate merely declaring a different period in SDC.
    declarations={re.sub(r'\s+',' ',s.strip()) for s in sdc.splitlines()
                  if s.strip().startswith(('create_clock ','create_generated_clock '))}
    master='ref_clk' if p['sys_hz']==40_000_000 else 'sys_clk'
    expected_clock_lines={f'create_clock -name {master} -period 20.000 [get_ports {{sys_clk}}]',
        f'create_generated_clock -name video_pixel -source [get_ports {{sys_clk}}] -master_clock {master} -multiply_by 1 -divide_by 2 [get_pins {{u_visual/u_video_pll/PLLA_inst/CLKOUT1}}]',
        f'create_generated_clock -name video_serial -source [get_ports {{sys_clk}}] -master_clock {master} -multiply_by 5 -divide_by 2 [get_pins {{u_visual/u_video_pll/PLLA_inst/CLKOUT0}}]'}
    if p['sys_hz']==40_000_000:
        expected_clock_lines.add('create_generated_clock -name sys_clk -source [get_ports {sys_clk}] -master_clock ref_clk -multiply_by 4 -divide_by 5 [get_pins {u_visual/u_video_pll/PLLA_inst/CLKOUT2}]')
    if declarations!=expected_clock_lines or not declarations<=active:
        errors.append('exact active physical-clock SDC declarations mismatch')
    normalized=lambda text: {re.sub(r'\s+',' ',s.strip()) for s in text.splitlines()
                             if s.strip() and not s.lstrip().startswith('#')}
    specified=normalized(sdc)
    if any(s.startswith(('set_multicycle_path','set_clock_groups')) for s in specified):
        errors.append('unapproved multicycle or clock-domain cut in SDC')
    if not specified<=active:
        errors.append('specified SDC command inactive or missing')
    for port in ('i2s_bclk','i2s_lrck','i2s_din'):
        for typ,value in [('max','5.000'),('min','0.000')]:
            if f'set_output_delay -clock sys_clk -{typ} {value} [get_ports {{{port}}}]' not in active:
                errors.append('audio output delay missing '+port+typ)
    slacks={}
    for kind in ('Setup','Hold','Recovery','Removal'):
        values=[float(r[1]) for s,r in rows if s.startswith(kind+'_Slack_Table') and len(r)>=4 and r[0].isdigit()]
        slacks[kind]=min(values) if values else None
        if not values or any(not math.isfinite(v) or v<0 for v in values):
            errors.append('missing/nonfinite/negative '+kind)
    tns=[r for s,r in rows if s=='Total_Negative_Slack_Report' and len(r)==4 and r[0]!='Clock Name']
    actual={(r[0],r[1]) for r in tns}
    required={(n,k) for n in ('sys_clk','video_pixel','video_serial') for k in ('Setup','Hold')}
    if not required<=actual or len(actual)!=len(tns):
        errors.append('missing/duplicate operational-domain TNS')
    for r in tns:
        if r[0] not in p['clocks'] or not math.isfinite(float(r[2])) or float(r[2])!=0 or int(r[3])!=0:
            errors.append('nonzero/unreviewed TNS/violated endpoints '+str(r))
    pulse=[float(r[1]) for s,r in rows if s=='MIN_PULSE_WIDTH_TABLE' and len(r)>=7 and r[0].isdigit()]
    if not pulse or any(not math.isfinite(v) or v<0 for v in pulse):
        errors.append('missing/nonfinite/negative minimum pulse width')
    locations={f'u_visual/u_serial_reset/sync_chain_{i}_s0':loc for i,loc in enumerate(p['reset_locs'])}
    locations.update(p['additional_ff_locations'])
    location_evidence={}
    for cell,loc in locations.items():
        observed={r[5] for s,r in rows if 'Analysis' in s and len(r)==7 and r[6] in (cell+'/CLK',cell+'/Q')}
        location_evidence[cell]=sorted(observed)
        if observed!={loc}:
            errors.append('actual fixed FF location mismatch/missing '+cell)
    fmax={r[1]:float(r[3].replace('(MHz)','')) for s,r in rows if s=='Max_Frequency_Report' and r[0].isdigit()}
    for n in ('sys_clk','video_pixel','video_serial'):
        if not math.isfinite(fmax.get(n,float('nan'))) or fmax[n]<p['clocks'][n][2]:
            errors.append('Fmax below operating frequency '+n)
    resources={}
    for kind in ('Logic','Register','DSP','BSRAM'):
        matches=re.findall(r'^\s*'+kind+r'\s*\|\s*(\d+)/(\d+)',usage,re.M)
        if len(matches)!=1:
            errors.append('missing resource '+kind)
        else:
            resources[kind]={'used':int(matches[0][0]),'total':int(matches[0][1])}
            if resources[kind]['used']>resources[kind]['total']:
                errors.append('resource exceeded '+kind)
    for k in ('DSP','BSRAM'):
        if resources.get(k,{}).get('used')!=p[k]:
            errors.append('frozen resource footprint changed '+k)
    latch=re.search(r'--Logic Register as Latch\s*\|\s*(\d+)/',usage)
    if not latch or latch[1]!='0':
        errors.append('latch-free not proven')
    lines=command.splitlines()
    for value in ('-timing','-correct_hold 1','-place_option 0','-route_option '+str(p['route_option']),'-route_maxfan 23','-pn '+p['part']):
        if lines.count(value)!=1:
            errors.append('actual PnR option missing/duplicate '+value)
    if 'set vccx = '+p['vccx'] not in config:
        errors.append('device vccx does not match profile')
    return {'profile':name,'errors':errors,'offline_timing_gate_pass':not errors,
            'slacks':slacks,'fmax_MHz':fmax,'resources':resources,'TNS':tns,'actual_pins':actual_pins,
            'reset_and_diagnostic_LOC':location_evidence,'visual_CDC_gate':visual_facts,
            'minimum_pulse_ns':min(pulse) if pulse else None,
            'setup_engineering_goal':slacks['Setup'] is not None and slacks['Setup']>=.5,
            'board_release_allowed':False,'I_L_original_package_required':name.endswith('065')}


def from_folder(name,folder):
    folder=Path(folder)
    pnr=folder/'impl/pnr'
    sdc=next((folder/'constraints').glob('*.sdc'))
    args=[pnr/(STEM+'_tr_content.html'),pnr/(STEM+'.rpt.txt'),pnr/(STEM+'.pin.html'),sdc,pnr/'cmd.do',pnr/'device.cfg']
    result=review(name,*(p.read_text(encoding='utf-8') for p in args))
    result['source_preflight']=source_preflight(name,folder)
    result['errors'].extend(result['source_preflight']['errors'])
    log=folder/'build.log'
    if not log.is_file():
        result['errors'].append('complete source-build log missing')
    else:
        text=log.read_text(encoding='utf-8',errors='replace')
        for marker in ('GowinSynthesis finish','Placement and routing completed','Timing analysis completed','Bitstream generation completed'):
            if marker not in text:
                result['errors'].append('build completion missing '+marker)
        receipts=[folder/n for n in ('build_receipt.json','bounded_build_result.json') if (folder/n).exists()]
        if len(receipts)!=1:
            result['errors'].append('unique final build receipt required')
        else:
            receipt=json.loads(receipts[0].read_text(encoding='utf-8'))
            if receipt.get('exit_code',receipt.get('exit'))!=0 or receipt.get('timed_out'):
                result['errors'].append('build receipt exit/timeout failed')
            expected=receipt.get('build_log_SHA256',receipt.get('log_sha',receipt.get('build_log_sha256')))
            if expected!=hashlib.sha256(log.read_bytes()).hexdigest():
                result['errors'].append('actual build log hash differs from receipt')
    result['offline_timing_gate_pass']=not result['errors']
    return result


def source_preflight(name,folder):
    p=profile(name)
    folder=Path(folder)
    errors=[]
    manifests=[folder/n for n in ('migration_manifest.json','input_manifest.json') if (folder/n).is_file()]
    if len(manifests)!=1:
        return {'errors':['unique frozen input manifest required']}
    manifest=json.loads(manifests[0].read_text(encoding='utf-8'))
    entries=manifest.get('inputs',manifest.get('all_input_files'))
    if not isinstance(entries,list) or len(entries)!=56:
        return {'errors':['current profile requires56 frozen physical inputs, not a partial manifest']}
    actual={}
    for item in entries:
        path=Path(item.get('path',item.get('actual_source','')))
        path=path if path.is_absolute() else folder/path
        expected=item.get('actual_sha',item.get('candidate_SHA256'))
        if not path.is_file() or not path.resolve().is_relative_to(folder.resolve()) or not expected:
            errors.append('input missing/external/unhashed '+str(path))
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            errors.append('input SHA differs '+str(path))
        if path.name in actual:
            errors.append('ambiguous input basename '+path.name)
        actual[path.name]=path
    project=ET.parse(folder/(STEM+'.gprj')).getroot()
    device=project.find('Device')
    if device.attrib.get('pn')!=p['part'] or device.text!=p['device_id']:
        errors.append('GPRJ part/version differs from profile')
    nodes=list(project.find('FileList'))
    if len(nodes)!=47 or len({Path(n.attrib['path']).name for n in nodes})!=47:
        errors.append('profile source-count/order manifest needs explicit revision')
    if not all(Path(n.attrib['path']).name in actual for n in nodes):
        errors.append('GPRJ compile source not in frozen inputs')
    top=actual['audio_visual_coexistence_top.sv'].read_text(encoding='utf-8')
    clean=re.sub(r'/\*.*?\*/|//[^\n]*','',top,flags=re.S)
    values=re.findall(r'parameter\s+(?:int\s+unsigned|integer)\s+CLK_HZ\s*=\s*([\d_]+)',clean)
    if len(values)!=1 or int(values[0].replace('_',''))!=p['sys_hz']:
        errors.append('actual top CLK_HZ does not match operating profile')
    required_text=['.CLK_HZ(CLK_HZ)']
    if p['sys_hz']==40_000_000:
        required_text.append('phase_step_for(CLK_HZ, 2 * I2S_BCLK_HZ)')
    else:
        package=actual['audio_defs_pkg.sv'].read_text(encoding='utf-8')
        if not re.search(r"I2S_BCLK_PHASE_STEP\s*=\s*32'd527_765_581",package):
            errors.append('original50MHz fixed BCLK step changed')
        required_text.append('.BCLK_PHASE_STEP(I2S_BCLK_PHASE_STEP)')
    for required in required_text:
        if re.sub(r'\s+','',required) not in re.sub(r'\s+','',clean):
            errors.append('clock-dependent parameter propagation missing '+required)
    if p['sys_hz']==40_000_000:
        pll=actual['TMDS_PLL_800_600_60.v'].read_text(encoding='utf-8')
        if not re.search(r'ODIV2_SEL\s*=\s*25\s*;',pll) or not re.search(r'CLKOUT2_EN\s*=\s*"TRUE"',pll):
            errors.append('real PLL core40 output configuration absent')
        if '.clk(core_clk)' not in re.sub(r'\s+','',clean) or 'core_async_rst_n' not in clean:
            errors.append('system core clock/LOCK reset not connected in source')
        # The guard065 profile changes only the stronger hold guard and two
        # explicit diagnostic commands. No hidden false/multicycle relaxation.
        from_folder_root=Path(__file__).resolve().parents[2]
        old_source=from_folder_root/'code/rtl/138K_try/clock_trials_20261005/M3_138K_clock40_evidence_20261005.zip'
        import zipfile
        with zipfile.ZipFile(old_source) as z:
            old_sdc=z.read('H_pll_core40_route2/constraints/audio_visual_hold055.sdc').decode('utf-8')
        actual_sdc=actual['audio_visual_hold055.sdc'].read_text(encoding='utf-8')
        if p['hold_uncertainty_ns']==.650:
            before='set_clock_uncertainty -hold  0.550'
            # Whitespace normalization makes the exactly one guard change
            # independent of presentation without silently changing scopes.
            clean_line=lambda text: {re.sub(r'\s+',' ',s.strip()) for s in text.splitlines()
                                     if s.strip() and not s.lstrip().startswith('#')}
            allowed=clean_line(old_sdc)
            exact='set_clock_uncertainty -hold 0.550 -from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}]'
            assert exact in allowed
            allowed.remove(exact)
            allowed.add(exact.replace('0.550','0.650'))
            start='g_polyphonic.u_audio_core/u_bank/u_pitch_mod/g_lane[2].u_control/base_s1_18_s0'
            stop='g_polyphonic.u_audio_core/u_bank/u_pitch_mod/g_lane[2].u_control/base_s2_18_s0'
            for kind in ('setup','hold'):
                allowed.add(f'report_timing -{kind} -from [get_regs {{{start}}}] -to [get_regs {{{stop}}}] -max_paths 1')
            if clean_line(actual_sdc)!=allowed:
                errors.append('guard065 command difference outside provisional exact profile')
        elif actual_sdc!=old_sdc:
            errors.append('hold055 original SDC byte identity changed')
    return {'profile':name,'manifest_SHA256':hashlib.sha256(manifests[0].read_bytes()).hexdigest(),
            'input_count':len(entries),'parameters':p['parameters'],'errors':errors,
            'not_a_new_build':True,'board_release_allowed':False}


if __name__=='__main__':
    cli=argparse.ArgumentParser()
    cli.add_argument('profile')
    cli.add_argument('folder',type=Path)
    cli.add_argument('--json',type=Path)
    a=cli.parse_args()
    try:
        result=from_folder(a.profile,a.folder)
    except (OSError,ValueError,KeyError,IndexError,StopIteration) as error:
        result={'offline_timing_gate_pass':False,'errors':['missing or malformed evidence: '+str(error)],'board_release_allowed':False}
    if a.json:
        a.json.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['offline_timing_gate_pass'] else 1)
