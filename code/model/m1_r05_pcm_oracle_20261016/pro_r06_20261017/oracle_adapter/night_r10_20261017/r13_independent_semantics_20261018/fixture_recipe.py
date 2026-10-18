"""Independent synthetic schedules and req7 clip mutations; NOT_RUN candidate.

Recipe construction carries no claim of physical timing or observed activity.
The signed Reference/ROM, not the new consumer, supplies expected mathematics.
"""
import hashlib
import json

REQ7_RESULT_CYCLE = 421
REQ7_CANCEL_CYCLE = 700


def sample_schedule(cancel=False):
    for frame, request in zip((100, 400, 700), (0, 7, 4294967295)):
        yield dict(request_id=request, frame=frame, accept=frame+1,
                   advance=frame+10, snapshot=frame+15, fx=frame+17,
                   result_first=frame+21,
                   accept_result=None if cancel and request == 7 else frame+21,
                   commit=None if cancel and request == 7 else frame+22,
                   cancel=700 if cancel and request == 7 else None)


def independent_expected(reference, *, cancel):
    """Reference is an independently pinned settled Reference object."""
    reference.event(15, 'note_on', note=60, velocity=1023)
    reference.config_accept(30, True, 1, 32767, 32767, 32767)
    for item in sample_schedule(cancel):
        result = reference.sample(item['advance'], item['request_id'], effect_accepted=True,
            publish=item['commit'] is not None, postprocess_accept_cycle=item['fx'])
        # sample() advances FX history even when publish=False.
        yield {**item, 'golden': result}


def mutate_req7(rows, field):
    """Mutate one result row in the CANCEL fixture, preserving post-cancel FX."""
    if field not in ('effect_clip_mask', 'feedback_clip_mask'):
        raise ValueError('INDEPENDENT_CLIP_MUTATION_FIELD')
    mutated, frame_seen, following_fx = False, False, False
    for original in rows:
        row = dict(original)
        if row['cycle'] == REQ7_RESULT_CYCLE:
            if not (row['result_valid'] == 1 and row['result_ready'] == 0 and row['result_id'] == 7):
                raise ValueError('REQ7_UNACCEPTED_RESULT_FIXTURE_REQUIRED')
            row[field] ^= 1  # left-side clip only, no PCM/other clip corruption
            mutated = True
        if row['cycle'] == REQ7_CANCEL_CYCLE:
            if row['frame_tick'] != 1:
                raise ValueError('FRAME700_CANCEL_MISSING')
            frame_seen = True
        if row['cycle'] == 717 and row['effect_input_id'] == 4294967295:
            following_fx = row['effect_input_valid'] == row['effect_input_ready'] == 1
        yield row
    if not (mutated and frame_seen and following_fx):
        raise ValueError('COMPLETE_REQ7_POST_CANCEL_FIXTURE_REQUIRED')


def fixture_identity(plan, rows_sha256, independent_golden_sha256, mutation=None):
    descriptor = dict(schema='M1_R13_INDEPENDENT_FIXTURE_V1', origin='SYNTHETIC_ONLY',
        plan=plan, rows_sha256=rows_sha256, independent_golden_sha256=independent_golden_sha256,
        mutation=mutation, golden_from_new_consumer=False, real_verified=False)
    raw = json.dumps(descriptor, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return descriptor, hashlib.sha256(raw).hexdigest()


def expected_clip_difference(field, expected, actual):
    return dict(source_line=422, cycle=421, epoch=0, request_id=7,
                independent_event_seq=101, router_sequence=0, layer='clip', field=field,
                expected=expected, actual=actual, expected_code='MATH_OR_IDENTITY_MISMATCH',
                result_accepted=False, eventual_cancel_cycle=700,
                required_post_cancel_fx_request_id=4294967295)


def iter_b1024(reference, required_fields, *, cancel=False):
    """All1024 synthetic pre-NBA fields; golden Reference is independently frozen."""
    scheduled = list(independent_expected(reference, cancel=cancel))
    on_word = (1 << 57) | (60 << 46) | (1023 << 36)
    off_word = (1 << 61) | (1 << 57) | (60 << 46)
    payload = (1 << 61) | (1 << 45) | (32767 << 30) | (32767 << 15) | 32767
    for cycle in range(1024):
        row = {name: 0 for name in required_fields}
        row.update(cycle=cycle, epoch=0, rst_n=int(cycle > 1),
                   event_ready=1, req_ready=1, result_ready=1,
                   apply_event_seq=None, tx_req_id=None, pll_locked=1, audio_stable=1,
                   finish=int(cycle == 1023), occupied_mask=int(cycle > 11),
                   releasing_mask=int(cycle > 813), slot_sources=int(cycle > 11),
                   slot_notes=60 if cycle > 11 else 0,
                   slot_generations=int(cycle > 11))
        if cycle in (8, 808):
            row.update(event_valid=1, event_data=on_word if cycle == 8 else off_word)
        for at, kind, seq, word in ((11, 1, 0, on_word), (15, 2, 0, on_word),
                                    (811, 6, 1, off_word), (813, 3, 0, 0), (814, 4, 0, 0)):
            if cycle == at:
                row.update(apply_valid=1, apply_kind=kind, apply_mask=1, apply_data=word,
                           router_apply_seq=seq, router_apply_seq_valid=int(kind in (1, 2, 6)),
                           note_on_mask=int(kind == 2), note_off_mask=int(kind == 4))
        if cycle == 30:
            row.update(config_valid=1, config_ready=1, config_take=1, config_payload=payload)
        for item in scheduled:
            req, golden = item['request_id'], item['golden']
            if cycle == item['frame']:
                row.update(frame_tick=1, cancel=1, req_ready=0, result_ready=0)
            if cycle == item['accept']:
                row.update(req_valid=1, req_id=req)
            if cycle == item['advance']:
                row.update(advance_mask=15, advance_frame_req_id=req)
            if cycle == item['fx']:
                row.update(effect_input_valid=1, effect_input_ready=1, effect_input_id=req,
                           effect_input_left=golden['mixed_left'], effect_input_right=golden['mixed_right'],
                           effect_input_clip_mask=3 if golden['upstream_clip'] else 0)
            result_last = 699 if cancel and req == 7 else item['result_first']
            if item['result_first'] <= cycle <= result_last:
                row.update(result_valid=1, result_ready=int(not (cancel and req == 7)), result_id=req,
                    result_left=golden['left'], result_right=golden['right'],
                    result_clip_mask=sum(int(x) << i for i, x in enumerate(golden['clipped'])),
                    upstream_clip_mask=3 if golden['upstream_clip'] else 0,
                    effect_clip_mask=sum(int(x) << i for i, x in enumerate(golden['effect_clip'])),
                    feedback_clip_mask=sum(int(x) << i for i, x in enumerate(golden['feedback_clip'])))
            if cycle == item['commit']:
                row.update(commit=1, commit_id=req, commit_left=golden['left'],
                           commit_right=golden['right'], commit_clip=int(any(golden['clipped'])))
        yield row
