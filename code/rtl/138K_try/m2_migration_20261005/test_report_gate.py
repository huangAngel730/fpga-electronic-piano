"""In-memory report negative tests; no report/source rewrite or tool rerun."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('m2_138k_migration',HERE/'migrate.py')
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
read_text=Path.read_text
pnr=m.OUT/'impl/pnr'
results=[]


def exercise(name, target=None, before=None, after=None, expected_error=None):
    collected={}
    def reader(path,*args,**kwargs):
        text=read_text(path,*args,**kwargs)
        if target is not None and path==target:
            assert before in text, name+' negative anchor missing'
            text=text.replace(before,after,1)
        return text
    def capture(path,data):
        collected.update(data)
    with patch.object(Path,'read_text',reader),patch.object(m,'write_json',capture):
        with contextlib.redirect_stdout(io.StringIO()):
            code=m.assess()
    if target is None:
        assert code==0 and collected['offline_STA_pass'], name
    else:
        assert code==1 and not collected['offline_STA_pass'], name
        assert any(expected_error in e for e in collected['errors']), collected['errors']
    results.append({'case':name,'passed':True,'errors':collected['errors']})
    print('PASS',name)


exercise('actual completed report')
exercise('wrong B version',pnr/(m.STEM+'.rpt.txt'),'<Device Version>: C','<Device Version>: B','exact 138K part')
exercise('wrong part',pnr/(m.STEM+'.rpt.txt'),'<Part Number>: GW5AST-LV138PG484AC1/I0','<Part Number>: GW5AT-LV60PG484AC1/I0','exact 138K part')
exercise('wrong tool',pnr/(m.STEM+'.rpt.txt'),'<Tool Version>: V1.9.11.03 Education','<Tool Version>: unknown','exact 138K part')
exercise('wrong pin ball',pnr/(m.STEM+'.pin.html'),'R17/4','R18/4','pin')
exercise('wrong IO voltage',pnr/(m.STEM+'.pin.html'),'LVCMOS33','LVCMOS15','pin')
exercise('wrong differential pair',pnr/(m.STEM+'.pin.html'),'<td>G15,G16/3</td>','<td>G15,G17/3</td>','pins')
exercise('route0 not approved profile',pnr/'cmd.do','-route_option 1','-route_option 0','nonpath PnR')
receipt=m.ROOT/'code/output/138k_migration_20261005/report_gate_selftest.json'
receipt.write_text(json.dumps({'checks':len(results),'passed':True,'cases':results,
                               'reports_mutated':False,'Gowin_rerun':False},indent=2)+'\n',encoding='utf-8')
print('PASS',len(results),'report checks; raw measured reports untouched')
