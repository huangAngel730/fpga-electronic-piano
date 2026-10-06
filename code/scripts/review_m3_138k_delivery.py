"""Audit M3 hold ZIP and expanded Git evidence; no source edits or tool reruns."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from check_platform_timing import review

ROOT=Path(__file__).resolve().parents[2]
HOLD=ROOT/'code/rtl/138K_try/hold_trials_20261005'
STEM='audio_visual_coexistence_top'
ARM_NAMES=('I_hold_locations','L_locations_guard065')
PAIR='g_polyphonic.u_audio_core/u_bank/u_pitch_mod/g_lane[2].u_control/'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def commands(text):
    return [re.sub(r'\s+',' ',line.strip()) for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith(('#','//'))]


def paths_prefix(project):
    tree=ET.fromstring(project)
    nodes=list(tree.find('FileList'))
    assert len(nodes)==47
    roots={n.attrib['path'].split('/sources/')[0] for n in nodes if '/sources/' in n.attrib['path']}
    assert len(roots)==1
    return tree,nodes,next(iter(roots))


def audit(output):
    output=Path(output).resolve()
    output.relative_to(ROOT/'code/output')
    assert not output.exists(),'Preserve previous evidence; choose new output'
    output.mkdir(parents=True)
    archive=HOLD/'M3_138K_Hold修复证据_20261005.zip'
    receipt=json.loads((HOLD/'archive_receipt.json').read_text(encoding='utf-8'))
    assert sha(archive.read_bytes())==receipt['SHA256']
    original_H=ROOT/'code/rtl/138K_try/clock_trials_20261005/M3_138K_clock40_evidence_20261005.zip'
    zipinfo=[]
    source_counts={'exact':0,'newline_only':0,'zip_only':0,'different':0}
    differences=[]
    with zipfile.ZipFile(archive) as z,zipfile.ZipFile(original_H) as h:
        assert z.testzip() is None
        assert set(z.namelist())==set(receipt['members'])
        for member in z.infolist():
            rel=Path(member.filename)
            assert not rel.is_absolute() and '..' not in rel.parts and ':' not in member.filename
            assert not member.filename.lower().endswith(('.exe','.dll','.obj','.pyc','.vvp','.fs','.bin','.vg','.pr','.db'))
            data=z.read(member.filename)
            assert sha(data)==receipt['members'][member.filename]
            destination=(output/'original'/rel).resolve()
            assert destination.is_relative_to((output/'original').resolve())
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(data)
            expanded=HOLD/rel
            if not expanded.is_file():
                kind='zip_only'
            elif expanded.read_bytes()==data:
                kind='exact'
            elif expanded.read_bytes().replace(b'\r\n',b'\n')==data.replace(b'\r\n',b'\n'):
                kind='newline_only'
            else:
                kind='different'
            source_counts[kind]+=1
            if kind!='exact':
                differences.append({'path':member.filename,'kind':kind})
            zipinfo.append({'path':member.filename,'bytes':len(data),'sha256':sha(data)})
        assert source_counts['different']==0,'expanded source changed beyond newline normalization'
        _,hnodes,hprefix=paths_prefix(h.read('H_pll_core40_route2/'+STEM+'.gprj'))
        results={}
        for arm in ARM_NAMES:
            base=output/'original'/arm
            manifest=json.loads((base/'input_manifest.json').read_text(encoding='utf-8'))
            assert len(manifest['inputs'])==56
            tree,nodes,prefix=paths_prefix((base/(STEM+'.gprj')).read_bytes())
            assert tree.find('Device').attrib=={'name':'GW5AST-138C','pn':'GW5AST-LV138PG484AC1/I0'}
            assert tree.find('Device').text=='gw5ast138c-007'
            assert [n.attrib['path'].replace(prefix,'<arm>') for n in nodes]==[n.attrib['path'].replace(hprefix,'<arm>') for n in hnodes]
            actual_changes=[]
            entries=[]
            for item in manifest['inputs']:
                rel=item['path'].replace('\\','/')
                data=(base/rel).read_bytes()
                assert sha(data)==item['candidate_SHA256'],rel
                old=h.read('H_pll_core40_route2/'+rel)
                if data.replace(prefix.encode(),b'<arm>')!=old.replace(hprefix.encode(),b'<arm>'):
                    actual_changes.append(rel)
                entries.append({'path':rel,'SHA_matches_original_manifest':True})
            assert actual_changes==['constraints/audio_visual.cst','constraints/audio_visual_hold055.sdc'] or set(actual_changes)=={'constraints/audio_visual.cst','constraints/audio_visual_hold055.sdc'}
            old_cst=h.read('H_pll_core40_route2/constraints/audio_visual.cst').decode('utf-8')
            new_cst=(base/'constraints/audio_visual.cst').read_text(encoding='utf-8')
            added=[f'INS_LOC "{PAIR}base_s1_18_s0" R83C99[1][B];',f'INS_LOC "{PAIR}base_s2_18_s0" R87C101[0][A];']
            assert commands(new_cst)==commands(old_cst)+added,'unexpected CST change'
            old_sdc=h.read('H_pll_core40_route2/constraints/audio_visual_hold055.sdc').decode('utf-8')
            new_sdc=(base/'constraints/audio_visual_hold055.sdc').read_text(encoding='utf-8')
            expected=commands(old_sdc)
            if arm.startswith('L_'):
                old_guard='set_clock_uncertainty -hold 0.550 -from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}]'
                assert expected.count(old_guard)==1
                expected[expected.index(old_guard)]=old_guard.replace('0.550','0.650')
            expected+=[f'report_timing -{kind} -from [get_regs {{{PAIR}base_s1_18_s0}}] -to [get_regs {{{PAIR}base_s2_18_s0}}] -max_paths 1' for kind in ('setup','hold')]
            assert commands(new_sdc)==expected,'unexpected/nonexact SDC change'
            bound=json.loads((base/'build_receipt.json').read_text(encoding='utf-8'))
            assert bound['state']=='finished' and bound['exit_code']==0
            log=(base/'build.log').read_bytes()
            assert sha(log)==bound['build_log_SHA256']
            for marker in (b'GowinSynthesis finish',b'Placement and routing completed',b'Timing analysis completed',b'Bitstream generation completed'):
                assert marker in log,marker
            functional=json.loads((base/'functional_v6_CDC_state_check/functional_review.json').read_text(encoding='utf-8'))
            assert functional['passed']
            for name,r in functional['runs'].items():
                source=base/'functional_v6_CDC_state_check'/(name+'.log')
                assert source.is_file() and sha(source.read_bytes())==r['log_SHA256'],name
                assert r['exit']==0 if r['expected_success'] else r['exit']!=0
            assert 'PASS full clock40 integration checks=1855' in (base/'functional_v6_CDC_state_check/top.log').read_text(encoding='utf-8')
            pnr=base/'impl/pnr'
            payload=[pnr/(STEM+'_tr_content.html'),pnr/(STEM+'.rpt.txt'),pnr/(STEM+'.pin.html'),base/'constraints/audio_visual_hold055.sdc',pnr/'cmd.do',pnr/'device.cfg']
            name='138k_c40_hold065' if arm.startswith('L_') else '138k_c40_hold055'
            result=review(name,*(p.read_text(encoding='utf-8') for p in payload))
            assert result['offline_timing_gate_pass'],result['errors']
            # Both I/L have the reviewed two fixed FFs, even though hold055
            # general profile also covers the original H without those LOCs.
            from check_hdmi_link_report import ReportParser
            parser=ReportParser()
            parser.feed(payload[0].read_text(encoding='utf-8'))
            fixed={PAIR+'base_s1_18_s0':'R83C99[1][B]',PAIR+'base_s2_18_s0':'R87C101[0][A]'}
            locations={}
            for cell,loc in fixed.items():
                seen={r[5] for section,r in parser.rows if 'Analysis' in section and len(r)==7 and r[6] in (cell+'/CLK',cell+'/Q',cell+'/D')}
                assert seen=={loc},(cell,seen)
                locations[cell]=loc
            assert (pnr/'device.cfg').read_bytes()==h.read('H_pll_core40_route2/impl/pnr/device.cfg')
            def options(data):
                return [l.split(' ',1)[0]+' <path>' if l.startswith(('-d ','-cst ','-sdc ','-cfg ')) else l for l in data.decode('utf-8').splitlines()]
            assert options((pnr/'cmd.do').read_bytes())==options(h.read('H_pll_core40_route2/impl/pnr/cmd.do'))
            result.update(input_SHA56_passed=True,exact_scope_changes=actual_changes,
                          source_logic_identical_to_H_after_path_rebinding=True,
                          actual_hold_fixed_locations=locations,functional_logs_SHA_passed=True,
                          reviewed_original_STA_not_reexecuted=True,
                          Setup_floor_0p5_passed=result['slacks']['Setup']>=.5,
                          board_release_allowed=False)
            assert result['Setup_floor_0p5_passed']
            results[arm]=result
    changed=subprocess.run(['git','diff','--name-status','-z','7b1662b..0bb5c66'],cwd=ROOT,capture_output=True,check=True).stdout.split(b'\0')
    statuses=[(changed[i].decode(),changed[i+1].decode('utf-8')) for i in range(0,len(changed)-1,2)]
    assert all(s=='A' and p.startswith('code/rtl/138K_try/') for s,p in statuses)
    shared=[]
    for name in ('任务看板.md','当前状态.md','验证记录.md','技术决策记录.md'):
        rel='code/docs/'+name
        old=subprocess.run(['git','show','7b1662b:'+rel],cwd=ROOT,capture_output=True,check=True).stdout
        new=(ROOT/rel).read_bytes()
        assert new==old
        assert not re.search(rb'^(<<<<<<< |=======$|>>>>>>> )',new,re.M)
        shared.append({'path':rel,'M2_progress_kept_byte_exact':True,'conflict_markers':False})
    tracked=subprocess.run(['git','ls-tree','-r','-l','-z','0bb5c66','--','code/rtl/138K_try'],cwd=ROOT,capture_output=True,check=True).stdout.split(b'\0')
    tracked_entries=[]
    binaries=[]
    vector_cleanup=[]
    archive_inventory=[]
    forbidden_suffix=('.exe','.dll','.obj','.pyc','.vvp','.pr','.db','.fs','.bin','.vg','.wlf','.vcd')
    for entry in tracked:
        if not entry:
            continue
        meta,name=entry.split(b'\t',1)
        path=name.decode('utf-8')
        size=int(meta.split()[3])
        tracked_entries.append((path,size))
        if path.lower().endswith(forbidden_suffix) or path.startswith('code/rtl/138K_try/tools/'):
            binaries.append(path)
        if size>5*1024*1024 and (path.endswith('.txt') or '/generated/' in path or '/functional' in path):
            vector_cleanup.append({'path':path,'bytes':size})
        if path.endswith('.zip'):
            original_blob=subprocess.run(['git','cat-file','blob',meta.split()[2].decode()],cwd=ROOT,capture_output=True,check=True).stdout
            import io
            with zipfile.ZipFile(io.BytesIO(original_blob)) as contents:
                bad=[name for name in contents.namelist() if name.lower().endswith(forbidden_suffix) or name.lower().startswith('tools/')]
                assert not bad,(path,bad)
                assert contents.testzip() is None,path
                archive_inventory.append({'path':path,'members':len(contents.infolist()),'CRC_pass':True,'executable_or_bitstream_members':bad})
    assert not binaries,binaries
    summary={'date':'2026-10-06','reviewed_commit':'0bb5c66862dcbd9dc3894b055d9703e2b3cd0e76',
             'new_files':len(statuses),'only_138k_additions':True,'shared_state':shared,
             'ZIP_sha256':receipt['SHA256'],'ZIP_CRC201_all_payload_SHA_passed':True,
             'original_payload_inventory':zipinfo,'expanded_comparison':source_counts,
             'expanded_differences':differences,'candidates':results,
             'preferred_candidate':'L_locations_guard065','fallback_candidate':'I_hold_locations',
             'candidate_scope_signed_off':True,'formal_integration_or_board_not_signed_off':True,
             'global_hold_not_measured_positive_0p1':True,'new_Gowin_runs':0,
             'source_directory_generated_files_cleanup_pending_M3':True,
             'tracked_hygiene':{'file_count':len(tracked_entries),'bytes':sum(s for p,s in tracked_entries),
                               'tool_binaries_bitstreams':binaries,'regeneratable_large_vectors':vector_cleanup,
                               'ZIP_inventory':archive_inventory}}
    (output/'review.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('original_payload_inventory','expanded_differences','candidates')},indent=2))
    for label,r in results.items():
        print(label,'PASS candidate',r['slacks'],'fixedLOC',r['actual_hold_fixed_locations'])
    return 0


if __name__=='__main__':
    cli=argparse.ArgumentParser()
    cli.add_argument('--output',type=Path,required=True)
    a=cli.parse_args()
    raise SystemExit(audit(a.output))
