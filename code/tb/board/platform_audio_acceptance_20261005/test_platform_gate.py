"""Actual report based negative tests; no edited files or PnR."""
import copy
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'code/scripts'))
from check_platform_timing import review,from_folder
from platform_profiles import profile,PROFILE_POLICY


def payload(folder):
    p=folder/'impl/pnr'
    return [q.read_text(encoding='utf-8') for q in
            [p/'audio_visual_coexistence_top_tr_content.html',p/'audio_visual_coexistence_top.rpt.txt',
             p/'audio_visual_coexistence_top.pin.html',next((folder/'constraints').glob('*.sdc')),p/'cmd.do',p/'device.cfg']]


def main():
    c50=ROOT/'code/rtl/138K_try/m2_migration_20261005/output/C50_baseline'
    h40=ROOT/'code/output/platform_preparation_20261005/H40_reference'
    good=payload(c50)
    failed=payload(h40)
    cases=[]
    def check(name,data,selected='138k_c50',positive=False,reason=None):
        r=review(selected,*data)
        assert r['offline_timing_gate_pass']==positive,(name,r['errors'])
        if reason:
            assert any(reason in e for e in r['errors']),(name,r['errors'])
        cases.append({'name':name,'expected_success':positive,'actual_errors':r['errors']})
        print('PASS',name,flush=True)
    def changed(data,index,old,new):
        p=copy.deepcopy(data)
        assert old in p[index],old
        p[index]=p[index].replace(old,new,1)
        return p
    check('original C50 accepted',good,positive=True)
    check('H40 real negative-zero one endpoint rejected',failed,'138k_c40_hold055',reason='Hold Violated Endpoints')
    check('50MHz cannot be advertised40',good,'138k_c40_hold055',reason='clock')
    check('40MHz cannot be advertised50',failed,reason='clock')
    check('B version rejected for C',changed(good,1,'<Device Version>: C','<Device Version>: B'),reason='part/version')
    check('wrong physical chip',changed(good,1,'<Part Number>: GW5AST-LV138PG484AC1/I0','<Part Number>: GW5AT-LV60PG484AC1/I0'),reason='part/version')
    check('3.3V port claimed1.5V',changed(good,2,'LVCMOS33','LVCMOS15'),reason='pin electrical')
    check('MIDI wrong Bank',changed(good,2,'R17/4','R17/5'),reason='pin electrical')
    check('HDMI negative partner mismatch',changed(good,2,'G15,G16/3','G15,G17/3'),reason='pin electrical')
    check('hold065 must not accept055',failed,'138k_c40_hold065',reason='uncertainty')
    check('route0 not current profile',changed(good,4,'-route_option 1','-route_option 0'),reason='PnR option')
    check('Hold automatic correction disabled',changed(good,4,'-correct_hold 1','-correct_hold 0'),reason='PnR option')
    check('wrong VCCX profile',changed(good,5,'set vccx = 1.8','set vccx = 3.3'),reason='vccx')
    bad=copy.deepcopy(good)
    bad[3]+='\nset_clock_groups -asynchronous -group [get_clocks {sys_clk}] -group [get_clocks {video_pixel}]\n'
    check('broad clock cut rejected',bad,reason='clock-domain cut')
    bad=copy.deepcopy(good)
    bad[3]+='\nset_multicycle_path 2 -setup -from [get_clocks {sys_clk}]\n'
    check('unapproved multicycle rejected',bad,reason='multicycle')
    # Mutate one actual slack cell, not a printed summary or arbitrary number.
    data=copy.deepcopy(good)
    block=re.search(r'<a name="Setup_Slack_Table[^\"]*".*?(?=<h[12])',data[0],re.S)
    assert block is not None
    pattern=r'(<tr>\s*<td>\d+</td>\s*<td>)([-+\d.]+)(</td>)'
    sample=re.search(pattern,block[0],re.S)
    assert sample is not None
    modified=re.sub(pattern,lambda m:m[1]+'nan'+m[3],block[0],count=1,flags=re.S)
    data[0]=data[0][:block.start()]+modified+data[0][block.end():]
    check('NaN real path rejected',data,reason='nonfinite')
    data=copy.deepcopy(good)
    modified=re.sub(pattern,lambda m:m[1]+'-0.001'+m[3],block[0],count=1,flags=re.S)
    data[0]=data[0][:block.start()]+modified+data[0][block.end():]
    check('negative real path rejected',data,reason='negative')
    # Source-aware entry accepts final original C50 hashes and rejects real H40.
    source_good=from_folder('138k_c50',c50)
    assert source_good['offline_timing_gate_pass'],source_good['errors']
    source_bad=from_folder('138k_c40_hold055',h40)
    assert not source_bad['offline_timing_gate_pass'] and not source_bad['source_preflight']['errors']
    cases.append({'name':'source-manifest and clock parameter preflight C50/H40','passed':True})
    assert PROFILE_POLICY['future_expansion_sys_hz']==40_000_000
    assert profile('138k_c40_hold055')['parameters']['BCLK_NCO_step']==659706977
    assert profile('60k_b50')['parameters']['BCLK_NCO_step']==527765581
    cases.append({'name':'human40MHz policy and exact NCO steps','passed':True})
    out=ROOT/'code/output/platform_preparation_20261005'
    (out/'platform_gate_selftest.json').write_text(json.dumps({'checks':len(cases),'passed':True,
         'cases':cases,'source_reports_modified':False,'Gowin_runs':0},indent=2)+'\n',encoding='utf-8')
    print('PASS',len(cases),'explicit profile checks',flush=True)


if __name__=='__main__':
    main()
