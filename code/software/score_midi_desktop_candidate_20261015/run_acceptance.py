"""Bounded new desktop tests and actual Tk smoke with immutable evidence."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from desktop_controller import run_owned_child
from preview_model import FROZEN,ROOT


def info(path):
    raw=Path(path).read_bytes()
    return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def paths_to_bind():
    paths=set(HERE.glob('*.py'))|set(HERE.glob('*.txt'))|set(FROZEN)
    original=ROOT/'code/software/score_midi_real_input_acceptance_20261015'
    paths.update([original/'SOURCE_RIGHTS.txt',original/'inputs/MIDI_sample_2018-03-21.mid',
                  original/'inputs/charge.mid',original/'inputs/beatscribe_README_original.txt',
                  ROOT/'code/software/score_midi_import_candidate_20261014/midi_fixtures.py'])
    # Preserve exact runtime/native/Tcl identities, not merely Python.exe.
    runtime=Path(sys.executable).resolve().parent
    paths.add(Path(sys.executable).resolve())
    paths.update(p for p in runtime.rglob('*') if p.is_file() and p.suffix.lower() in
                 ('.exe','.dll','.pyd','.zip','.tcl','.tm'))
    return sorted(paths)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    output=args.output.resolve()
    if output.parent!=ROOT/'code/output' or not output.name.startswith('score_midi_desktop_'):
        parser.error('fresh exclusive score_midi_desktop_* output under code/output required')
    output.mkdir(exist_ok=False)
    started=time.monotonic()
    receipt=dict(schema=1,scope='DESKTOP_OFFLINE_IMPORT_PREVIEW_EXPORT',passed=False,
                 outer_bound_seconds=300,step_bound_seconds=90,stages=[],
                 serial_calls=0,network_calls=0,hardware_pass_claim=False,
                 native_picker_tested=False,external_review_messages=0)
    before={};paths=[]
    try:
        for source in HERE.iterdir():
            if source.is_file() and source.suffix in ('.py','.txt'):
                target=output/'source_before'/source.name
                target.parent.mkdir(exist_ok=True);shutil.copyfile(source,target)
        paths=paths_to_bind()
        before={str(p):info(p) for p in paths}
        for p,expected in FROZEN.items():
            if before[str(p)]['sha256']!=expected:raise ValueError('FROZEN_DEPENDENCY_CHANGED: '+str(p))
        suite_bootstrap=("import os,sys,unittest;sys.path.insert(0,sys.argv[1]);"
                         "os.environ['DESKTOP_TEST_OUTPUT']=sys.argv[2];"
                         "suite=unittest.defaultTestLoader.discover(sys.argv[1],pattern='test_desktop.py');"
                         "result=unittest.TextTestRunner(verbosity=2).run(suite);"
                         "raise SystemExit(not result.wasSuccessful())")
        commands=[('software_tests',[sys.executable,'-I','-S','-B','-X','utf8','-c',suite_bootstrap,str(HERE),str(output/'cases')]),
                  ('tk_smoke',[sys.executable,'-I','-S','-B','-X','utf8',str(HERE/'tk_smoke.py'),'--output',str(output/'tk_case')])]
        for name,argv in commands:
            remaining=300-(time.monotonic()-started)
            if remaining<=0:raise TimeoutError('OUTER_BUDGET_BEFORE_LAUNCH')
            execution=run_owned_child(argv,ROOT,output/(name+'_logs'),threading.Event(),min(90,remaining))
            receipt['stages'].append(dict(name=name,execution=execution))
            if execution.get('exit_code')!=0 or execution.get('error') or execution.get('timed_out') or execution.get('cancelled'):
                raise ValueError('STAGE_FAILED: '+name)
        tk_result=json.loads((output/'tk_case/receipt.json').read_text(encoding='utf-8'))
        if not tk_result.get('passed'):raise ValueError('TK_SMOKE_REJECTED')
        receipt['tk_smoke']=tk_result
        receipt['passed']=True
    except Exception as error:
        receipt['error']=type(error).__name__+': '+str(error)
    finally:
        after={};errors=[]
        for p in paths:
            try:after[str(p)]=info(p)
            except Exception as error:after[str(p)]=None;errors.append(str(p)+': '+str(error))
        receipt.update(before=before,after=after,identity_errors=errors,seconds=time.monotonic()-started)
        if errors or before!=after or receipt['seconds']>300:receipt['passed']=False
        receipt['runner_exit']=0 if receipt['passed'] else 1
        receipts=[]
        for p in output.rglob('process_receipt.json'):
            try:
                d=json.loads(p.read_text(encoding='utf-8'))
                receipts.append(dict(path=str(p.relative_to(output)),argv=d.get('argv'),
                                     exit_code=d.get('exit_code'),tool_calls=d.get('tool_calls'),
                                     timed_out=d.get('timed_out'),cancelled=d.get('cancelled'),identity=info(p)))
            except Exception as error:receipts.append(dict(path=str(p),error=str(error)))
        receipt['actual_processes']=receipts
        (output/'receipt.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({key:receipt.get(key) for key in ('passed','runner_exit','error','seconds')},ensure_ascii=False))
    print('Receipt:',output/'receipt.json')
    return receipt['runner_exit']


if __name__=='__main__':raise SystemExit(main())
