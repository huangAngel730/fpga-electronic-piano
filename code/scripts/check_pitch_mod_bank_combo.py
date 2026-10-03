"""Fail-closed timing review of isolated actual bank Pitch/Mod audio+visual.

Keeps original timing/interface failures. Only exact, intended experimental
uncertainty and added-control-ROM footprint differences are validated separately;
raw reports remain unchanged. A tool exit0 or generated .fs is not timing PASS.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from check_audio_visual_probe import check as original_check
from check_hdmi_link_report import ReportParser


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assess(folder):
    manifest=json.loads((folder/'input_manifest.json').read_text(encoding='utf-8'))
    changed=[]
    for item in manifest['source_builds']:
        source=Path(item.get('actual_source',item.get('actual','')))
        expected=item.get('actual_sha',item.get('actual_sha256'))
        if not source.is_file() or digest(source)!=expected:changed.append(str(source))
    for name,expected in manifest['roms'].items():
        if not Path(name).is_file() or digest(Path(name))!=expected:changed.append(name)
    if changed:raise ValueError('input manifest mismatch: '+repr(changed))
    errors,facts=original_check(folder)
    raw_errors=errors.copy()
    parser=ReportParser()
    timing=folder/'impl/pnr/audio_visual_coexistence_top_tr_content.html'
    parser.feed(timing.read_text(encoding='utf-8'))
    active={r[2] for s,r in parser.rows if s=='SDC_Report' and len(r)==3 and r[1]=='Actived'}
    intended='set_clock_uncertainty -hold 0.550 -from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}]'
    if intended in active:
        errors=[e for e in errors if e!='formal audio clock uncertainty missing: hold']
    else:errors.append('missing exact stricter 0.550ns Hold constraint')
    # Four lanes: original 8 waveform/envelope blocks + 3 control ROMs/lane.
    # Actual 20 must appear in the tool report; never set unknown footprints0.
    if facts['resources'].get('BSRAM')==20:
        errors=[e for e in errors if e!='audio ROM footprint is not 8 BSRAM']
    else:errors.append('actual 8+12 BSRAM control/waveform footprint not proven')
    if int((folder/'build_exit.txt').read_text())!=0:errors.append('Gowin flow failed')
    worst={};all_paths={}
    for kind in ('Setup','Hold','Recovery','Removal'):
        rows=[r for s,r in parser.rows if s.startswith(kind+'_Slack_Table') and len(r)>=9 and r[0].isdigit()]
        by_clock={}
        for r in rows:
            pair=(r[4].split(':')[0],r[5].split(':')[0])
            if pair[0]==pair[1] and (pair[0] not in by_clock or float(r[1])<float(by_clock[pair[0]][1])):by_clock[pair[0]]=r
        worst[kind]=by_clock
        all_paths[kind]=min(rows,key=lambda r:float(r[1])) if rows else None
    tns=[r for s,r in parser.rows if s=='Total_Negative_Slack_Report' and len(r)==4 and r[0] in ('sys_clk','video_pixel','video_serial')]
    if len(tns)!=6 or any(float(r[2])<0 or r[3]!='0' for r in tns):errors.append('per-domain timing endpoints/TNS failed')
    pulse=[r for s,r in parser.rows if s=='MIN_PULSE_WIDTH_TABLE' and len(r)>6 and r[0].isdigit()]
    pulse_min=min(float(r[1]) for r in pulse) if pulse else None
    if pulse_min is None or pulse_min<0:errors.append('minimum pulse-width gate failed')
    artifacts={str(p.relative_to(folder)):digest(p) for p in [timing,folder/'build.log',folder/'impl/pnr/audio_visual_coexistence_top.rpt.txt',folder/'impl/pnr/audio_visual_coexistence_top.pin.html',folder/'impl/pnr/cmd.do']}
    bitstream=folder/'impl/pnr/audio_visual_coexistence_top.fs'
    if bitstream.exists():artifacts['FAILED_OR_RESEARCH_ONLY.fs']=digest(bitstream)
    return {'scope':'isolated integration of actual four-voice bank/V1/CC64/PitchMod + latest MIDI + strict visual',
            'raw_original_gate_errors':raw_errors,'validated_intended_changes':{'Hold_uncertainty_ns':0.550,'BSRAM_expected':20},
            'errors':errors,'timing_pass':not errors,'facts':facts,'per_clock_worst':worst,'global_worst_paths':all_paths,
            'per_clock_TNS':tns,'min_pulse_width_slack':pulse_min,'artifact_sha256':artifacts,
            'manifest_sha256':digest(folder/'input_manifest.json'),
            'formal_RTL_modified':False,'board_bitstream_released':False,'programmed':False,
            'disposition':'experimental timing candidate only; formal notice/acceptance still required' if not errors else 'FAIL: retain previous approved production; do not program generated .fs'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    args=parser.parse_args();folder=args.folder.resolve()
    result=assess(folder)
    (folder/'timing_review.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'timing_pass':result['timing_pass'],'errors':result['errors'],'resources':result['facts']['resources'],'fmax':result['facts']['fmax_mhz'],'slacks':result['facts']['exported_min_slack_ns']},indent=2))
    return 0 if result['timing_pass'] else 1


if __name__=='__main__':raise SystemExit(main())
