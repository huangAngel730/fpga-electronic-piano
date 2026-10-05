"""Reject capture corruption independently of DUT; no simulation rerun."""
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'code/scripts'))
from run_platform_audio_capture import audit_pair


def main():
    out=ROOT/'code/output/platform_preparation_20261005'
    obs=out/'capture2/audio_observation.jsonl'
    raw=out/'capture2/midi_pcm.capture'
    text=obs.read_text(encoding='ascii')
    rows=text.splitlines()
    original_read=Path.read_text
    def record_change(tag,change):
        copy=rows.copy()
        for i,line in enumerate(copy):
            r=json.loads(line)
            if r['tag']==tag:
                change(r)
                copy[i]=json.dumps(r)
                return '\n'.join(copy)+'\n'
        raise AssertionError('missing actual record '+tag)
    cases={'empty':'','truncated':'\n'.join(rows[:-1])+'\n',
           'wrong system frequency':record_change('META',lambda r:r.update(sys_hz=50_000_000)),
           'wrong request tag':record_change('COMMIT',lambda r:r.update(request_id=r['request_id']+100000)),
           'PCM one LSB corrupted':record_change('COMMIT',lambda r:r.update(pcm_left=r['pcm_left']^1)),
           'voice velocity width':record_change('STATE',lambda r:r.update(velocity=1024)),
           'unknown fixed-point value':record_change('STATE',lambda r:r.update(level_q16='xxxxxxxx')),
           'wrong final counts':record_change('END',lambda r:r['counts'].update(COMMIT=r['counts']['COMMIT']+1))}
    # Repeat an actual transaction without inventing a toy-only fixture.
    for tag in ('REQUEST','COMMIT'):
        i=next(i for i,l in enumerate(rows) if json.loads(l)['tag']==tag)
        cases['duplicate '+tag]='\n'.join(rows[:i+1]+[rows[i]]+rows[i+1:])+'\n'
    receipt={'actual_positive':audit_pair(obs,raw,40_000_000),'negative_cases':{}}
    print('PASS actual captured pair',flush=True)
    for name,mutant in cases.items():
        def reader(p,*a,**kw):
            return mutant if p==obs else original_read(p,*a,**kw)
        try:
            with patch.object(Path,'read_text',reader):
                audit_pair(obs,raw,40_000_000)
        except (ValueError,KeyError,IndexError) as error:
            receipt['negative_cases'][name]={'rejected':True,'reason':str(error)}
            print('PASS rejected',name,flush=True)
        else:
            raise AssertionError('invalid actual capture accepted '+name)
    receipt.update(checks=1+len(cases),passed=True,original_files_modified=False,simulation_rerun=False)
    (out/'observation_checker_selftest.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print('PASS',receipt['checks'],'actual-observation checks')


if __name__=='__main__':
    main()
