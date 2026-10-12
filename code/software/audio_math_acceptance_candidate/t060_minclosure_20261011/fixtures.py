"""Input-only plans and software expectations; never consumes RTL observations."""
import json

from fsm_oracle import Oracle, event_word, observable, require
from strict_capture import object_pairs


META = dict(tag='META', schema=1, baseline='H_pll_core40_route2', region='pre_NBA',
            sys_hz=40000000, sample_hz=48000)


def initial_plan(group, end):
    return dict(schema=1, group=group, end_cycle=end, trace_all=group == 2,
                inputs={'6': {'rst_n': 1}, '60': {'event': event_word(0, 900)}},
                cases=[], new_RTL_execution_authorized=False)


def add(plan, cycle, **values):
    entry = plan['inputs'].setdefault(str(cycle), {})
    require(not set(entry).intersection(values), 'PLAN_DUPLICATE_INPUT')
    entry.update(values)


def lifecycle_plan():
    plan = initial_plan(1, 4095000)
    # Same 833/833/834 cadence as original H capture, never accelerate Release.
    n = 0
    while (cycle := 100 + n * 2500 // 3) <= plan['end_cycle']:
        add(plan, cycle, frame=1)
        n += 1
    for cycle, word in ((27300, event_word(1)), (4060400, event_word(0, 900)),
                        (4064400, event_word(4, control=6, value=4095)),
                        (4068400, event_word(1)), (4072400, event_word(5))):
        add(plan, cycle, event=word)
    plan['cases'] = ['normal_off_4800_ticks_retire_same_identity_reallocate',
                     'CC64_deferred_accepted_global_panic_release']
    return plan


def cancel_plan(roms):
    plan = initial_plan(2, 1600)
    model = Oracle(roms)
    rst_n = 0
    consumer = 1
    targets = {100: 'before_math', 400: 'advance_same_edge',
               700: 'after_advance', 1000: 'held_backpressure'}
    current, age, held_edges = None, 0, 0
    for cycle in range(1, plan['end_cycle'] + 1):
        if cycle in targets:
            current, age, held_edges = targets[cycle], 0, 0
            add(plan, cycle, frame=1)
        if cycle == 999:
            add(plan, cycle, consumer=0)
        if cycle == 1500:
            add(plan, cycle, frame=1)
        hit = False
        if current:
            age += 1
            if current == 'before_math':
                hit = model.phase == 'SETTLE' and age >= 6
            elif current == 'advance_same_edge':
                hit = model.phase == 'ADVANCE'
            elif current == 'after_advance':
                hit = model.phase == 'SNAPSHOT' and model.delay == 4
            elif current == 'held_backpressure' and model.bank_valid:
                held_edges += 1
                hit = held_edges == 4
        if hit:
            add(plan, cycle, frame=1)
            plan['cases'].append(dict(name=current, cycle=cycle, old_id=model.req_id,
                                      expected_phase=model.phase))
            if current == 'held_backpressure':
                add(plan, cycle + 2, consumer=1)
            current = None
        inp = plan['inputs'].get(str(cycle), {})
        rst_n, consumer = inp.get('rst_n', rst_n), inp.get('consumer', consumer)
        model.edge(rst_n=rst_n, consumer=consumer, frame=inp.get('frame', 0),
                   event_valid=int('event' in inp), event=inp.get('event', 0))
    require(len(plan['cases']) == 4, 'PLAN_FOUR_SOURCE_CALENDAR_TARGETS')
    # M2 V0295 follow-up: only append a reset/restart after the four frozen
    # cancellation cases. End1600 and all inputs before1510 remain unchanged.
    add(plan, 1510, rst_n=0)
    add(plan, 1514, rst_n=1)
    add(plan, 1518, event=event_word(0, 900))
    add(plan, 1540, frame=1)
    return plan


def validate_plan(plan):
    require(set(plan) == {'schema', 'group', 'end_cycle', 'trace_all', 'inputs',
                         'cases', 'new_RTL_execution_authorized'}, 'PLAN_FIELDS')
    require(type(plan['schema']) is int and plan['schema'] == 1
            and type(plan['group']) is int and plan['group'] in (1, 2)
            and type(plan['end_cycle']) is int and 10 <= plan['end_cycle'] <= 4200000
            and type(plan['trace_all']) is bool and plan['trace_all'] == (plan['group'] == 2)
            and plan['new_RTL_execution_authorized'] is False, 'PLAN_PROFILE')
    require(type(plan['inputs']) is dict and type(plan['cases']) is list, 'PLAN_TYPES')
    for cycle, entry in plan['inputs'].items():
        require(type(cycle) is str and cycle.isdecimal() and str(int(cycle)) == cycle
                and 2 <= int(cycle) <= plan['end_cycle'] and type(entry) is dict
                and bool(entry) and set(entry) <= {'rst_n', 'frame', 'consumer', 'event'}, 'PLAN_INPUT')
        for key, value in entry.items():
            require(type(value) is int and (0 <= value < 1 << 64 if key == 'event'
                                          else value in (0, 1)), 'PLAN_INPUT_VALUE:' + key)


def rows(plan, roms, origin):
    validate_plan(plan)
    require(origin in ('RTL', 'SYNTHETIC_SOFTWARE_TEST'), 'CAPTURE_ORIGIN')
    yield dict(META, group=plan['group'], origin=origin)
    model = Oracle(roms)
    rst_n, consumer, reset_count, edge_count, previous_reset = 0, 1, 0, 0, False
    changes = sorted(map(int, plan['inputs']))
    # Fixed point skip is valid only with trace disabled and before the next
    # input. The full active pipeline and true retirement edges still execute.
    index = 0
    while model.cycle < plan['end_cycle']:
        cycle = model.cycle + 1
        inp = plan['inputs'].get(str(cycle), {})
        rst_n, consumer = inp.get('rst_n', rst_n), inp.get('consumer', consumer)
        row = model.edge(rst_n=rst_n, consumer=consumer, frame=inp.get('frame', 0),
                         event_valid=int('event' in inp), event=inp.get('event', 0))
        if not rst_n and not previous_reset:
            reset_count += 1
            yield dict(tag='RESET', epoch=model.epoch, cycle=cycle)
        previous_reset = not rst_n
        if row is not None and observable(row, plan['trace_all']):
            edge_count += 1
            yield row
        if rst_n and not plan['trace_all']:
            while index < len(changes) and changes[index] <= model.cycle:
                index += 1
            next_input = changes[index] if index < len(changes) else plan['end_cycle'] + 1
            # Do not skip retired/lane/control/transport observations. idle_skip
            # executes hidden quiet clocks but must not skip the first RETIRE.
            if (model.phase == 'IDLE' and not model.router.busy()
                    and not (model.router.on | model.router.off) and not model.req
                    and not model.bank_valid and not model.pcm_valid
                    and not any(s['occupied'] and s['releasing'] and e.state == 0
                                for s, e in zip(model.router.slots, model.env))):
                model.idle_skip(next_input)
    yield dict(tag='END', cycle=plan['end_cycle'], counts=dict(EDGE=edge_count, RESET=reset_count))


def diagnostic(field):
    if field in ('generations', 'sources', 'channels', 'notes', 'occupied'):
        return 'MINCLOSURE_RETIRE_IDENTITY'
    if field in ('off', 'keys', 'deferred', 'releasing', 'pedal', 'release_done'):
        return 'MINCLOSURE_PANIC_RELEASE'
    if field in ('commit', 'pcm_id', 'bank_id', 'bank_ready', 'pcm_ready'):
        return 'MINCLOSURE_CANCEL_OLD_ID'
    if field in ('dds_phase', 'lfo_phase', 'env_state', 'env_level', 'bank_waves',
                 'bank_envelopes', 'pcm_left', 'pcm_right', 'play_left', 'play_right', 'tick'):
        return 'MINCLOSURE_ADVANCE_NONROLLBACK_MATH'
    return 'MINCLOSURE_SOURCE_CALENDAR'


def compare(lines, plan, roms, software_fixture=False):
    """Compare the whole input-bound stream, including END and no trailing rows."""
    iterator = iter(lines)
    origin = 'SYNTHETIC_SOFTWARE_TEST' if software_fixture else 'RTL'
    count = 0
    for expected in rows(plan, roms, origin):
        try:
            line = next(iterator)
        except StopIteration as error:
            raise ValueError('MINCLOSURE_TRUNCATED') from error
        actual = json.loads(line, object_pairs_hook=object_pairs,
                            parse_constant=lambda _: require(False, 'MINCLOSURE_NONFINITE'))
        require(type(actual) is dict and set(actual) == set(expected), 'MINCLOSURE_SCHEMA')
        for field, value in expected.items():
            require(type(actual[field]) is type(value), 'MINCLOSURE_TYPE:' + field)
            if field == 'counts':
                require(type(actual[field]) is dict and set(actual[field]) == set(value)
                        and all(type(v) is int for v in actual[field].values()), 'MINCLOSURE_END_TYPES')
            require(actual[field] == value, diagnostic(field) + ':' + field)
        count += 1
    require(next(iterator, None) is None, 'MINCLOSURE_RECORD_AFTER_END')
    return dict(status='SOFTWARE_FIXTURE_ONLY' if software_fixture else 'MINCLOSURE_EXACT_FIXTURE_MATCH',
                records=count, new_RTL_run=False, t060_complete=False, physical_verified=False)


def schedule_text(plan):
    validate_plan(plan)
    rst_n, consumer, lines = 0, 1, []
    for cycle, inp in sorted((int(c), v) for c, v in plan['inputs'].items()):
        rst_n, consumer = inp.get('rst_n', rst_n), inp.get('consumer', consumer)
        flags = rst_n | (inp.get('frame', 0) << 1) | (int('event' in inp) << 2) | (consumer << 3)
        lines.append(f"{cycle} {flags:x} {inp.get('event', 0):016x}\n")
    return ''.join(lines)
