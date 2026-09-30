"""T024/T025 formal report gate; no board or stability claim from STA alone."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('sta_rows',ROOT/'code/scripts/check_t009_fusion_report.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('build',type=Path);args=parser.parse_args()
    folder=args.build/'impl/pnr';name='electronic_piano'
    rows=module.Rows();rows.feed((folder/(name+'_tr_content.html')).read_text(encoding='utf-8'))
    summary={r[0]:r[1] for sec,r in rows.rows if sec=='STA_Tool_Run_Summary' and len(r)==2}
    errors=[]
    for kind in ['Setup','Hold']:
        if summary.get('Numbers of '+kind+' Violated Endpoints')!='0':errors.append(kind+' violated endpoints not zero')
    for field in ['Numbers of Paths Analyzed','Numbers of Endpoints Analyzed']:
        if not summary.get(field,'').isdigit() or int(summary[field])==0:errors.append('Missing analyzed paths/endpoints')
    clock=[r for sec,r in rows.rows if sec=='Clock_Report' and len(r)>4 and r[1]=='sys_clk']
    if len(clock)!=1 or clock[0][3:5]!=['20.000','50.000']:errors.append('Wrong active 50MHz clock')
    slack={}
    for kind in ['Setup','Hold','Recovery','Removal']:
        values=[float(r[1]) for sec,r in rows.rows if sec==kind+'_Slack_Table' and len(r)>1 and r[0].isdigit()]
        slack[kind]=min(values) if values else None
        if not values or min(values)<0:errors.append('Missing/negative '+kind+' slack')
    fmax=[r[3] for sec,r in rows.rows if sec=='Max_Frequency_Report' and len(r)>3 and r[1]=='sys_clk']
    if len(fmax)!=1 or float(fmax[0].replace('(MHz)',''))<50:errors.append('Fmax below50MHz/missing')
    usage=(folder/(name+'.rpt.txt')).read_text(encoding='utf-8');resources={}
    if 'GW5AT-LV60PG484AC1/I0' not in usage:errors.append('Wrong device')
    for kind in ['Logic','Register','DSP','BSRAM']:
        found=re.findall(r'^\s*'+kind+r'\s*\|\s*(\d+)/(\d+)',usage,re.M)
        if len(found)!=1:errors.append('Missing resource '+kind)
        else:resources[kind]=int(found[0][0])
    # Current unshared 4-DDS/4-envelope/4-gain structure. Future resource
    # optimization needs reviewed expectations, not blindly reused thresholds.
    if resources.get('BSRAM',0)!=8 or resources.get('DSP',0)!=24:errors.append('Unexpected four-lane ROM/multiplier footprint; reject missing-ROM optimization')
    found=re.search(r'--Logic Register as Latch\s*\|\s*(\d+)/',usage)
    if not found or found[1]!='0':errors.append('Latch-free not proven')
    pins=module.Rows();pins.feed((folder/(name+'.pin.html')).read_text(encoding='utf-8'))
    expected={'sys_clk':('V22','LVCMOS33','3.3'),'sys_rst_n':('AA13','LVCMOS15','1.5'),
       'key_n[0]':('AB13','LVCMOS15','1.5'),'key_n[1]':('Y12','LVCMOS15','1.5'),
       'midi_rx':('R17','LVCMOS33','3.3'),'uart_tx':('U15','LVCMOS33','3.3'),
       'i2s_bclk':('Y17','LVCMOS33','3.3'),'i2s_lrck':('AB17','LVCMOS33','3.3'),
       'i2s_din':('AA16','LVCMOS33','3.3'),'pa_en':('AB16','LVCMOS33','3.3')}
    for port,(ball,standard,voltage) in expected.items():
        actual=[r for _,r in pins.rows if len(r)>17 and r[0]==port]
        if len(actual)!=1 or actual[0][2].split('/')[0]!=ball or actual[0][7]!=standard or actual[0][17]!=voltage:errors.append('Pin/IO standard mismatch '+port)
    if not (folder/(name+'.fs')).is_file():errors.append('Missing FS')
    info={'resources':resources,'fmax_mhz':fmax,'worst_slack_ns':slack,'setup_hold_violated_endpoints':0 if not errors else None,'pins_checked':len(expected),'scope':'formal audio/STAT STA only; no hardware verification'}
    for error in errors:print('FAIL formal T024:',error)
    if errors:return 1
    (args.build/'checked_summary.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
    print('PASS formal T024/T025 report:',info)
    return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,IndexError) as exc:print('FAIL formal T024 report:',exc);raise SystemExit(1)