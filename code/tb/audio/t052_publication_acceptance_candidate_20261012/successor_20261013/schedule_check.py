"""Bounded source-schedule audit; never invokes HDL/EDA tools.

This accepts one documented procedural subset, not arbitrary SystemVerilog.
An unsupported scheduler is rejected instead of guessed to be equivalent.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
PLAN = ROOT / ('code/docs/test/t052_publication_acceptance_20261012/'
               'M2_CONTROL_PLAN_20261012/controls_proposed.jsonl')
PLAN_SHA = 'b2d0cb1ba0bf3cd4b2d636f3d4cb7ac286558238ae2b52c3e9e43ba54ee5ef02'
MEM = HERE.parent / 'controls_128.hex'
TB = HERE / 'tb_t052_control_128_v2.sv'
OBSERVER = HERE / 't052_public_observer_v2.sv'
FIELDS = [('rst_n', 1), ('frame', 1), ('cancel', 1), ('sample_req', 1),
          ('req_id', 32), ('enable', 1), ('mask', 4),
          ('fcw0', 32), ('fcw1', 32), ('fcw2', 32), ('fcw3', 32),
          ('result_ready', 1)]


def need(ok, diagnostic):
    if not ok:
        raise ValueError(diagnostic)


def identity(path):
    data = Path(path).read_bytes()
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def clean(text):
    return re.sub(r'//[^\n]*|/\*.*?\*/', '', text, flags=re.S)


def unpack(word):
    need(re.fullmatch(r'[0-9a-f]{43}', word) is not None, 'MEM_HEX_FORMAT')
    value = int(word, 16)
    need(value < (1 << 170), 'MEM_WIDTH')
    fields = {}
    for key, width in reversed(FIELDS):
        fields[key] = value & ((1 << width) - 1)
        value >>= width
    fields['fcw'] = [fields.pop('fcw' + str(i)) for i in range(4)]
    return fields


def parse_schedule(text):
    need(text.count('// SCHEDULE_BEGIN') == text.count('// SCHEDULE_END') == 1,
         'SCHEDULE_MARKERS')
    region = text.split('// SCHEDULE_BEGIN', 1)[1].split('\n', 1)[1].split('// SCHEDULE_END', 1)[0]
    region = clean(region)
    grammar = r'''
        \s*initial\s+begin
        \s*\$timeformat\(-9,\s*0,\s*"",\s*0\);
        \s*clk\s*=\s*1'b0;
        \s*driver_index\s*=\s*(?P<driver_start>\d+);
        \s*observer_cycle\s*=\s*(?P<cycle_start>\d+);
        \s*\$readmemh\(CONTROL_FILE,\s*controls\);
        \s*apply_control\(controls\[driver_index\]\);
        \s*forever\s+\#(?P<half>\d+)\s+clk\s*=\s*~clk;
        \s*end
        \s*always\s*@\(negedge\s+clk\)\s+begin
        \s*if\s*\(driver_index\s*<\s*(?P<driver_last>\d+)\)\s+begin
        \s*driver_index\s*=\s*driver_index\s*\+\s*(?P<driver_step>\d+);
        \s*apply_control\(controls\[driver_index(?P<offset>\s*\+\s*\d+)?\]\);
        \s*end\s*end
        \s*always\s*@\(posedge\s+clk\)\s+begin
        \s*if\s*\(observer_cycle\s*==\s*(?P<cycle_last>\d+)\)\s+begin
        \s*\#(?P<finish_delay>\d+)\s+\$finish\(0\);
        \s*end\s+else\s+begin
        \s*observer_cycle\s*<=\s*observer_cycle\s*\+\s*(?P<cycle_step>\d+);
        \s*end\s*end\s*
    '''
    match = re.fullmatch(grammar, region, flags=re.X)
    need(match is not None, 'UNSUPPORTED_SCHEDULE_SOURCE')
    result = {key: int(value) for key, value in match.groupdict().items()
              if key != 'offset'}
    result['offset'] = int(match['offset'].replace(' ', '').lstrip('+')) if match['offset'] else 0
    outside = clean(text.split('// SCHEDULE_BEGIN', 1)[0]
                    + text.split('// SCHEDULE_END', 1)[1])
    # No second driver, hidden input write or control task is accepted outside
    # the fixed task/instance/declaration/guard envelope.
    need(len(re.findall(r'\bapply_control\s*\(', outside)) == 1,
         'EXTRA_CONTROL_DRIVER')
    need(not re.search(r'\b(?:driver_index|observer_cycle)\s*(?:<=|=(?!=))', outside),
         'EXTRA_COUNTER_DRIVER')
    need(not re.search(r'\b(?:force|release|fork)\b|\bdut\s*\.', clean(text)),
         'DRIVER_PUBLIC_ONLY')
    need(re.search(r'`timescale\s+1ns/1ps', text) is not None, 'DRIVER_TIME_UNIT')
    need(result['half'] == 10 and result['finish_delay'] == 1, 'CLOCK_50MHZ')
    ports = ('rst_n frame_tick cancel sample_req req_id enable voice_enable_mask '
             'fcw_lane0 fcw_lane1 fcw_lane2 fcw_lane3 result_ready').split()
    task = re.search(r'task automatic apply_control.*?endtask', clean(text), re.S)
    need(task is not None, 'CONTROL_TASK_MISSING')
    need(re.sub(r'\s+', '', task[0]) ==
         'taskautomaticapply_control(inputlogic[CONTROL_WIDTH-1:0]word);'
         'begin{' + ','.join(ports) + '}=word;endendtask', 'CONTROL_TASK_LAYOUT')
    envelope = outside.replace(task[0], '')
    need(not re.search(r'\b(?:always\w*|assign)\b', envelope), 'EXTRA_CONTROL_DRIVER')
    need(not re.search(r'\b(?:' + '|'.join(ports + ['clk'])
                       + r')\s*(?:<=|=(?!=))', envelope), 'EXTRA_CONTROL_DRIVER')
    guards = re.findall(r'initial\s+begin.*?end', envelope, re.S)
    need(len(guards) == 1 and re.sub(r'\s+', '', guards[0]) ==
         'initialbegin#3000;$fatal(1,"T052_CONTROL_WINDOW_TIMEOUT");end',
         'UNSUPPORTED_OUTSIDE_SCHEDULER')
    return result


def check_observer(text):
    source = clean(text)
    need(re.search(r'`timescale\s+1ns/1ps', source) is not None, 'OBSERVER_TIME_UNIT')
    need('$timeformat(-9, 0, "", 0)' in source, 'OBSERVER_TIME_FORMAT')
    need('%0t' not in source and '%t' not in source, 'OBSERVER_TIME_AMBIGUOUS')
    need(not re.search(r'\bdut\s*\.|\$root|\b(?:force|release)\b', source),
         'OBSERVER_PUBLIC_ONLY')
    need('always @(rst_n)' in source and '#0;' in source,
         'ASYNC_RESET_OBSERVER_REQUIRED')
    need('always @(posedge clk)' in source and '$strobe' not in source,
         'PRE_NBA_OBSERVER_REQUIRED')
    need(not re.search(r'@\(posedge clk\)\s*begin\s*#', source),
         'POST_NBA_OBSERVER')
    for name in ('controls_file', 'observations_file', 'publications_file', 'reset_file'):
        need(re.search(r'write_meta\(' + name + r',', source) is not None,
             'META_MISSING:' + name)
    need('$isunknown' in source and 'T052_RESET_UNKNOWN' in source,
         'FOUR_STATE_REJECTION_REQUIRED')
    return {'sampling': 'PRE_NBA', 'time_unit': '1ns', 'time_precision': '1ps',
            'async_reset_transition_observation': True,
            'note': 'Source checks only, not HDL elaboration or runtime proof.'}


def reproduce_legacy(text):
    """Read the old expressions and model its active/NBA/negedge ordering."""
    source = clean(text)
    initial = re.search(r'apply_control\(controls\[(\d+)\]\);', source)
    increment = re.search(r'cycle\s*<=\s*cycle\s*\+\s*(\d+);', source)
    next_index = re.search(r'if\s*\(cycle\s*<\s*(\d+)\)\s*'
                           r'apply_control\(controls\[cycle\s*\+\s*(\d+)\]\);', source)
    need(all((initial, increment, next_index)), 'UNSUPPORTED_LEGACY_REPRODUCTION')
    cycle, selected, indices = 0, int(initial[1]), []
    for _ in range(128):
        indices.append(selected)
        if cycle == 127:
            break
        cycle += int(increment[1])
        if cycle < int(next_index[1]):
            selected = cycle + int(next_index[2])
    need(indices == [0, *range(2, 128), 127], 'LEGACY_REGRESSION_CHANGED')
    return {'kind': 'SOFTWARE_SOURCE_RECONSTRUCTION_ONLY',
            'memory_indices': indices, 'first_mismatch_cycle': 1,
            'missing_plan_rows': [1], 'repeated_plan_rows': [127]}


def audit(tb_text, observer_text, rows, words):
    spec = parse_schedule(tb_text)
    observer = check_observer(observer_text)
    need(len(rows) == len(words) == 128, 'PLAN_AND_MEM_128')
    decoded = [unpack(word) for word in words]
    for index, (row, actual) in enumerate(zip(rows, decoded)):
        need(row['cycle'] == index and actual == {k: v for k, v in row.items() if k != 'cycle'},
             'MEM_PLAN_MISMATCH:' + str(index))
    di, cycle, selected, changed_at = spec['driver_start'], spec['cycle_start'], spec['driver_start'], 0
    schedule, resets = [], []
    previous_reset = None
    for step in range(128):
        need(0 <= selected < 128, 'SOURCE_INDEX_RANGE:' + str(step))
        actual = decoded[selected]
        now = spec['half'] + step * spec['half'] * 2
        need(cycle == step, 'SOURCE_CYCLE_MISMATCH:' + str(step))
        need(selected == step and actual == {k: v for k, v in rows[step].items() if k != 'cycle'},
             'SOURCE_SCHEDULE_MISMATCH:' + str(step))
        schedule.append(dict(cycle=cycle, time=now, memory_index=selected,
                             stable_since_ns=changed_at, **actual))
        if actual['rst_n'] != previous_reset:
            resets.append(dict(event='RESET_EDGE', time=changed_at,
                               cycle_visible_next=cycle, rst_n=actual['rst_n']))
            previous_reset = actual['rst_n']
        if cycle == spec['cycle_last']:
            need(step == 127, 'EARLY_WINDOW_FINISH')
            break
        # Active posedge samples first; the observer counter then changes in NBA.
        cycle += spec['cycle_step']
        # The next negedge is a separate event, independent of output pins.
        if di < spec['driver_last']:
            di += spec['driver_step']
            selected = di + spec['offset']
            changed_at = now + spec['half']
    need(len(schedule) == 128 and cycle == spec['cycle_last'], 'WINDOW_END')
    expected_resets = [dict(event='RESET_EDGE', time=i * 20,
                            cycle_visible_next=i, rst_n=row['rst_n'])
                       for i, row in enumerate(rows)
                       if i == 0 or row['rst_n'] != rows[i - 1]['rst_n']]
    need(resets == expected_resets, 'RESET_SCHEDULE_MISMATCH')
    return dict(status='STATIC_SOURCE_SCHEDULE_PASS', exit_code=0,
                software_prediction_only=True, HDL_compiles=0, RTL_runs=0,
                T052_complete=False, scheduler=spec, observer=observer,
                schedule=schedule, reset_events=resets,
                terminal_time_ns=2551)


def check():
    need(identity(PLAN)['sha256'] == PLAN_SHA, 'FROZEN_PLAN_SHA')
    plan = [json.loads(line) for line in PLAN.read_text(encoding='utf-8').splitlines()]
    result = audit(TB.read_text(encoding='utf-8'), OBSERVER.read_text(encoding='utf-8'),
                   plan[1:-1], MEM.read_text(encoding='ascii').splitlines())
    result['legacy_source_reconstruction'] = reproduce_legacy(
        (HERE.parent / 'tb_t052_publication_control_128.sv').read_text(encoding='utf-8'))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    need(not args.output.exists(), 'OUTPUT_EXISTS')
    paths = [Path(__file__), TB, OBSERVER, PLAN, MEM,
             HERE.parent / 'tb_t052_publication_control_128.sv']
    before = {str(path): identity(path) for path in paths}
    result = check()
    need(before == {str(path): identity(path) for path in paths}, 'INPUT_DRIFT')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump({'inputs': before, **result}, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('schedule', 'reset_events')},
                     sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
