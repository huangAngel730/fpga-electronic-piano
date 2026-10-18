"""Run a bounded C9 mathematics job. Exit 0=software/real match, 1=FAIL,
2=rejected/unsupported, 3=pending. No child processes or HDL tools are invoked.
"""
import argparse
import json
from pathlib import Path

from c9_inputs import load_job
from c9_math import ClockedMath, MathIssue, known


def evaluate(job_path):
    engine=None
    result=dict(schema='M1_C9_MATH_RESULT_V1',board_release_allowed=False,
                real_verified=False,HDL_EDA_device_called=False)
    try:
        job,docs,rows,pending=load_job(job_path)
        result.update(capture_id=job['capture_id'],mode=job['mode'],profile=job['profile'])
        if pending:
            return {**result,**pending}
        engine=ClockedMath(docs['independent_plan'])
        for record in rows:
            values=dict(record['fields'])
            values['cycle']=known(values,'cycle',64)
            values['epoch']=known(values,'epoch',32)
            engine.row(values)
        result.update(engine.finish())
        if not engine.counts['result_accepts']:
            result['status']='PENDING_NO_MATH_SAMPLES'
            result['missing']=['No accepted public PCM sample to compare']
            return result
        result['status']='SOFTWARE_MATCH' if job['mode']=='SYNTHETIC' else 'REAL_MATH_MATCH'
        result['real_verified']=job['mode']=='REAL'
        result['level']='L1_SOFTWARE' if job['mode']=='SYNTHETIC' else 'REAL_MATH_ONLY_REQUIRES_M2_ACCEPTANCE'
        return result
    except MathIssue as error:
        result.update(status=error.status,error=dict(code=error.code,where=error.where,
                      expected=error.expected,actual=error.actual))
        if engine is not None:
            result.update(counts=dict(engine.counts),first_difference=engine.first_difference,
                          last_cycle=engine.cycle,last_epoch=engine.epoch)
        return result
    except (OSError,KeyError,TypeError,ValueError) as error:
        result.update(status='CONTRACT_REJECTED',error=dict(code='MALFORMED_INPUT',detail=str(error)))
        return result


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--job',required=True,type=Path)
    cli.add_argument('--output',required=True,type=Path)
    args=cli.parse_args()
    if args.output.exists():
        cli.error('Output exists; choose a new result path to preserve original evidence')
    result=evaluate(args.job.resolve())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:result[k] for k in ('schema','status','capture_id') if k in result},ensure_ascii=False))
    return 0 if result['status'] in ('SOFTWARE_MATCH','REAL_MATH_MATCH') else 1 if result['status']=='FAIL' else 3 if result['status'].startswith('PENDING') else 2


if __name__=='__main__':
    raise SystemExit(main())
