"""Fixed input schedules, complete synthetic traces and one-target corruptions."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from frame_reference import FrameReference, U32, default_input, require  # noqa: E402
from trace_check import META_FIXED  # noqa: E402


def schedule(length=40, reset=True, initial_id=0, initial_clip=0):
    inputs = [default_input() for _ in range(length)]
    if reset:
        inputs[0]['rst_n'] = inputs[1]['rst_n'] = 0
    return dict(initial=dict(current_id=initial_id, clip_count=initial_clip), inputs=inputs)


def at(plan, cycles, **fields):
    for cycle in ([cycles] if type(cycles) is int else cycles):
        plan['inputs'][cycle-1].update(fields)


def result(plan, cycles, ident, epoch=1, left=111, right=-222, clipped=0):
    at(plan, cycles, result_valid=1, result_id=ident, result_epoch=epoch,
       left=left, right=right, clipped=clipped)


def plans():
    cases = {}
    p = schedule(1700)
    at(p, [4, 837, 1671], frame_tick=1)
    result(p, 20, 1)
    result(p, 850, 2, left=-8388608, right=8388607)
    result(p, 1680, 3, left=17, right=-19)
    cases['normal_833_834'] = p
    p = schedule()
    at(p, [4, 10, 25], frame_tick=1)
    result(p, 10, 1)
    result(p, 17, 2, left=300, right=400)
    result(p, 28, 1)
    cases['frame_coincident_result'] = p
    p = schedule()
    at(p, [4, 20], frame_tick=1)
    at(p, range(5, 8), backend_ready=0)
    result(p, 10, 1)
    cases['delayed_dispatch_success'] = p
    p = schedule()
    at(p, [4, 8, 22], frame_tick=1)
    at(p, range(5, 8), backend_ready=0)
    result(p, 12, 2)
    cases['delayed_dispatch_expiry'] = p
    p = schedule()
    at(p, [4, 22, 30], frame_tick=1)
    result(p, range(8, 13), 1, clipped=1)
    at(p, range(8, 12), result_sink_ready=0)
    at(p, range(13, 16), pcm_sink_ready=0)
    cases['result_HOLD_and_PCM_backpressure'] = p
    p = schedule()
    at(p, [4, 20, 30], frame_tick=1)
    result(p, range(8, 13), 1, clipped=1)
    cases['always_ready_and_duplicate'] = p
    p = schedule()
    at(p, [4, 11, 22], frame_tick=1)
    at(p, [5, 6], backend_ready=0)
    at(p, [7, 8], rst_n=0)
    result(p, 13, 1, epoch=1)
    result(p, 15, 1, epoch=2, left=17, right=-19)
    cases['reset_pending_old_epoch'] = p
    p = schedule()
    at(p, [4, 12, 20, 30], frame_tick=1)
    result(p, 8, 1)
    at(p, [15, 16], rst_n=0)
    result(p, 24, 1, epoch=2, left=123, right=-456)
    cases['reset_held'] = p
    p = schedule(reset=False, initial_id=U32-2)
    at(p, [2, 10, 18, 26], frame_tick=1)
    for cycle, ident in [(6, U32-1), (14, U32), (22, 0)]:
        result(p, cycle, ident, epoch=0, left=ident % 100, right=-7)
    cases['ID32_wrap_entry_fixture'] = p
    p = schedule(reset=False, initial_clip=U32-1)
    at(p, [2, 15, 28, 38], frame_tick=1)
    result(p, range(6, 11), 1, epoch=0, clipped=1)
    at(p, range(6, 10), result_sink_ready=0)
    result(p, 19, 2, epoch=0, clipped=1)
    # Exact PCM limits with clipped=0 prove the model never guesses metadata.
    result(p, 32, 3, epoch=0, left=8388607, right=-8388608, clipped=0)
    cases['clip_once_saturating_entry_fixture'] = p
    p = schedule()
    at(p, [4, 9, 20], frame_tick=1)
    result(p, [8, 9], 1, clipped=1)
    result(p, 13, 2)
    cases['frame_cancels_uncommitted_PCM'] = p
    return cases


def records(name, plan):
    model = FrameReference(plan['initial'])
    output = [dict(META_FIXED, case=name, initial=plan['initial'])]
    ledger = dict(dispatch=0, result=0, commit=0, discard=0, reset=0)
    resets = 0
    for cycle, inp in enumerate(plan['inputs'], 1):
        if not inp['rst_n'] and not model.was_reset:
            output.append(dict(tag='RESET', cycle=cycle, epoch=model.epoch+1))
            resets += 1
            ledger['reset'] += 1
        pre, post = model.edge(inp)
        output.append(dict(tag='EDGE', cycle=cycle, epoch=model.epoch, inputs=deepcopy(inp), pre=pre, post=post))
        for key, field in (('dispatch', 'dispatch_accept'), ('result', 'result_accept'), ('commit', 'commit'), ('discard', 'discard_result')):
            ledger[key] += pre[field]
    output.append(dict(tag='END', cycle=len(plan['inputs']), epoch=model.epoch,
                       counts=dict(EDGE=len(plan['inputs']), RESET=resets), ledger=ledger))
    return output


BAD = [
    ('ready_without_valid', 'normal_833_834', 30, 'pre', 'dispatch_accept', 1, 'DISPATCH_VALID_READY'),
    ('frame_accepts_old_result', 'frame_coincident_result', 10, 'pre', 'result_accept', 1, 'FRAME_OLD_RESULT_REJECT'),
    ('reset_epoch_stale_accept', 'reset_pending_old_epoch', 13, 'pre', 'result_accept', 1, 'RESULT_CURRENT_EPOCH_ID'),
    ('held_payload_changes', 'result_HOLD_and_PCM_backpressure', 9, 'pre', 'result_payload',
        dict(epoch=1, id=1, left=112, right=-222, clipped=1), 'RESULT_HOLD_STABILITY'),
    ('duplicate_commit', 'always_ready_and_duplicate', 11, 'pre', 'commit', 1, 'COMMIT_CURRENT_ONCE'),
    ('clip_grows_without_commit', 'result_HOLD_and_PCM_backpressure', 10, 'post', 'clip_count', 1, 'CLIP_COMMIT_EXACTLY_ONCE'),
]


def encoded(rows):
    return ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows).encode('utf-8')


def generate(out):
    require(not out.exists(), 'VECTORS_REFUSE_OVERWRITE')
    out.mkdir(parents=True)
    corpus = {name: records(name, plan) for name, plan in plans().items()}
    manifest = dict(origin='SYNTHETIC_SOFTWARE_TEST', positives={}, negatives={})
    for name, data in corpus.items():
        raw = encoded(data)
        (out / (name + '.jsonl')).write_bytes(raw)
        manifest['positives'][name] = dict(file=name+'.jsonl', bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
            counts=data[-1]['counts'], ledger=data[-1]['ledger'])
    for name, base, cycle, region, field, value, diagnostic in BAD:
        data = deepcopy(corpus[base])
        target = next(r for r in data if r.get('tag') == 'EDGE' and r['cycle'] == cycle)
        require(target[region][field] != value, 'MUTANT_NO_CHANGE')
        target[region][field] = value
        raw = encoded(data)
        (out / (name + '.jsonl')).write_bytes(raw)
        manifest['negatives'][name] = dict(file=name+'.jsonl', base=base, cycle=cycle, region=region, field=field,
            diagnostic=diagnostic, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
            complete_END_unchanged=True, inputs_unchanged=True, changed_observation_fields=1)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    result_manifest = generate(parser.parse_args().output.resolve())
    print(json.dumps(dict(positive=len(result_manifest['positives']), negative=len(result_manifest['negatives']),
                         origin=result_manifest['origin'])))
