"""Hand-authored control/pin/publication examples, not oracle-generated outputs."""
import argparse
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from publication import DUT_SHA, SCHEMA


def row(cycle, **changes):
    value = dict(cycle=cycle, rst_n=1, frame=0, cancel=0, sample_req=0,
                 req_id=0, enable=1, mask=15, fcw=[1, 2, 3, 4], result_ready=0)
    value.update(changes)
    return value


def fixture(which):
    meta = dict(type='META', schema=SCHEMA, source_sha=DUT_SHA, sampling='PRE_NBA',
                reset_scope='NO_UNOBSERVED_ASYNC_PULSE', origin='HANDWRITTEN_SOFTWARE_FIXTURE')
    if which == 'normal_repeated_id':
        controls = [row(c) for c in range(12)]
        controls[0]['rst_n'] = 0
        controls[1].update(sample_req=1, req_id=7)
        controls[5]['result_ready'] = 1
        controls[7].update(sample_req=1, req_id=7)
        controls[10]['result_ready'] = 1
        # Explicit PRE_NBA triples (ready, valid, id), independent of calendar().
        triples = [(1, 0, 0), (1, 0, 0), (0, 0, 0), (0, 0, 0),
                   (0, 1, 7), (0, 1, 7), (1, 0, 7), (1, 0, 7),
                   (0, 0, 7), (0, 0, 7), (0, 1, 7), (1, 0, 7)]
        pubs = [dict(cycle=5, key=[1, 1, 7]), dict(cycle=10, key=[1, 2, 7]),
                dict(type='END', accepted=2, published=2, cancelled=0, open=0)]
    elif which == 'cancel_frame_reset':
        controls = [row(c) for c in range(18)]
        controls[0]['rst_n'] = 0
        controls[1].update(sample_req=1, req_id=11)
        controls[2]['cancel'] = 1
        controls[3].update(frame=1, sample_req=1, req_id=99)
        controls[4].update(sample_req=1, req_id=12)
        controls[7].update(frame=1, result_ready=1)
        controls[8].update(sample_req=1, req_id=13)
        controls[12]['rst_n'] = 0
        controls[13].update(sample_req=1, req_id=11)
        controls[16]['result_ready'] = 1
        triples = [(1, 0, 0), (1, 0, 0), (0, 0, 0), (1, 0, 0),
                   (1, 0, 0), (0, 0, 0), (0, 0, 0), (0, 1, 12),
                   (1, 0, 0), (0, 0, 0), (0, 0, 0), (0, 1, 13),
                   (1, 0, 0), (1, 0, 0), (0, 0, 0), (0, 0, 0),
                   (0, 1, 11), (1, 0, 11)]
        pubs = [dict(cycle=16, key=[2, 1, 11]),
                dict(type='END', accepted=4, published=1, cancelled=3, open=0)]
    else:
        raise ValueError('UNKNOWN_HAND_FIXTURE')
    end = dict(type='END', last_cycle=len(controls) - 1)
    pins = [dict(cycle=c, calc_ready=a, result_valid=b, result_id=d)
            for c, (a, b, d) in enumerate(triples)] + [end]
    return [meta, *controls, end], pins, pubs


def corpus():
    normal, cancel = fixture('normal_repeated_id'), fixture('cancel_frame_reset')
    result = {name: (copy.deepcopy(value), 0, None) for name, value in
              [('normal_repeated_id', normal), ('cancel_frame_reset', cancel)]}

    def negative(name, original, edit, diagnostic):
        value = copy.deepcopy(original)
        edit(value)
        result[name] = (value, 1, diagnostic)

    def lost(value):
        value[2].pop(0)
        value[2][-1]['published'] = 1
    negative('lost_result_self_consistent_END', normal, lost, 'PUBLICATION_LEDGER_MISMATCH')
    negative('duplicate_publication', normal, lambda v: v[2].insert(1, dict(v[2][0])),
             'DUPLICATE_PUBLICATION')
    negative('stale_epoch_same_id', cancel, lambda v: v[2][0].update(key=[1, 1, 11]),
             'PUBLICATION_LEDGER_MISMATCH')
    negative('same_id_wrong_generation', normal, lambda v: v[2][1].update(key=[1, 1, 7]),
             'DUPLICATE_PUBLICATION')
    negative('publish_on_frame_priority', cancel,
             lambda v: v[2].insert(0, dict(cycle=7, key=[1, 2, 12])),
             'PUBLICATION_LEDGER_MISMATCH')
    negative('valid_one_edge_early', normal, lambda v: v[1][3].update(result_valid=1),
             'SOURCE_CALENDAR_PINS:3')
    negative('ready_without_true_accept', normal, lambda v: v[0][2].update(sample_req=0),
             'SOURCE_CALENDAR_PINS:2')
    negative('forged_cancel_END', normal, lambda v: v[2][-1].update(cancelled=1),
             'INDEPENDENT_END_COUNT')
    return result


def write_rows(path, rows):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        for record in rows:
            stream.write(json.dumps(record, sort_keys=True) + '\n')


def generate(out):
    if out.exists():
        raise ValueError('CORPUS_OUTPUT_EXISTS')
    out.mkdir(parents=True)
    manifest = {}
    for name, (value, code, diagnostic) in corpus().items():
        directory = out / name
        directory.mkdir()
        for label, rows in zip(('controls', 'observations', 'publications'), value):
            write_rows(directory / (label + '.jsonl'), rows)
        manifest[name] = dict(expected_exit=code, diagnostic=diagnostic,
                              origin='HANDWRITTEN_SOFTWARE_ONLY')
    with (out / 'manifest.json').open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    generate(parser.parse_args().output)
