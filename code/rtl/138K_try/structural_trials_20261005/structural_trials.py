"""Two bounded, same-cycle parser structure trials; old artifacts are read-only."""
from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
assert HERE == Path('E:/FPGA/GAOYUNFPGA/138K_try/structural_trials_20261005')
LABELS = ['E_fixed_slot_next', 'F_absolute_rr']


def imported(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


shared = imported('structural_shared', ROOT / 'optimization_followup_20261005/experiment.py')
assessor = imported('structural_assessor', ROOT / 'optimization_followup_20261005/assess.py')
shared.HERE = assessor.HERE = HERE


def protected():
    result = shared.protected_hashes()
    for directory in ['optimization_followup_20261005', 'pipeline_trials_20261005']:
        result.update({str(p): shared.sha(p.read_bytes()) for p in (ROOT / directory).rglob('*') if p.is_file()})
    return result


def protect(check=False):
    before = HERE / 'preservation_before.json'
    if not check:
        assert not before.exists(), 'Do not overwrite protection receipt'
        shared.write_json(before, protected())
        print('Frozen old artifact hashes', flush=True)
        return
    frozen = json.loads(before.read_text(encoding='utf-8'))
    actual = protected()
    changes = [p for p in set(frozen) | set(actual) if frozen.get(p) != actual.get(p)]
    shared.write_json(HERE / 'preservation_verification.json', {
        'time': datetime.now().astimezone().isoformat(), 'files': len(frozen),
        'changed_added_removed': changes, 'passed': not changes})
    assert not changes, changes
    print('Old baseline/documents/evidence protected', len(frozen), 'files PASS', flush=True)


def identity(source):
    baseline = (shared.BASE / 'sources/midi_event_parser.sv').read_text(encoding='utf-8')
    # Entire public declaration and all decode/FIFO/counter blocks unchanged.
    assert source[:source.index('    import audio_defs_pkg::*;')] == baseline[:baseline.index('    import audio_defs_pkg::*;')]
    a, b = '    integer comb_fifo_index;', '    // Apply the current byte before arbitration.'
    assert source[source.index(a):source.index(b)] == baseline[baseline.index(a):baseline.index(b)]
    if 'ISOLATED F:' in source:
        a = '    // At most one locked control event;'
        assert source[source.index(a):] == baseline[baseline.index(a):]


def functional(label, folder_name='functional'):
    out = shared.OUT / folder_name
    out.mkdir()
    (out / 'tmp').mkdir()
    env = dict(os.environ)
    env['PATH'] = str(shared.CAD / 'bin') + ';' + env['PATH']
    env['TMP'] = env['TEMP'] = str(out / 'tmp')
    source = (shared.OUT / 'sources/midi_event_parser.sv').read_text(encoding='utf-8')
    identity(source)
    runs = {}

    def run(name, command, good=True, marker=None, timeout=240):
        log = out / (name + '.log')
        with log.open('wb') as stream:
            process = subprocess.run([str(x) for x in command], cwd=out, env=env,
                                     stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
        body = log.read_text(encoding='utf-8', errors='replace')
        runs[name] = {'command': [str(x) for x in command], 'exit': process.returncode,
                      'expected_success': good, 'log_SHA256': shared.sha(log.read_bytes())}
        shared.write_json(out / 'run_status.json', runs)
        print(name, 'exit', process.returncode, body[-750:], flush=True)
        assert (process.returncode == 0) == good, name
        assert marker is None or marker in body, name

    defs = shared.OUT / 'sources/audio_defs_pkg.sv'
    candidate = shared.OUT / 'sources/midi_event_parser.sv'
    reference = out / 'reference.sv'
    original = (shared.BASE / 'sources/midi_event_parser.sv').read_bytes()
    reference.write_bytes(original.replace(b'module midi_event_parser #(', b'module midi_event_parser_frozen #(', 1))
    old_tb = ROOT / 'pipeline_trials_20261005/fixtures/C/code/tb/common/midi_scheduler_setup_review/tb_m2_parser_miter.sv'
    tb_body = old_tb.read_text(encoding='utf-8')
    a = tb_body.index('  if(rst_n)begin\n   if(dut.first_prepared_valid')
    b = tb_body.index('  if({nv,nd,nl,np,no,ne}', a)
    tb_body = tb_body[:a] + tb_body[b:]
    tb_body = tb_body.replace('i==3?3:8', 'i==3?16:8')
    # Deterministic cancellation while the immutable CC1 event is locked.
    # Random streams alone did not detect the missing-cancellation mutant.
    before = 'repeat(5)drive(0,0,0,0);rst_n=1;'
    after = '''repeat(5)drive(0,0,0,0);rst_n=1;
 msg(8'hB0,7'd1,7'd20);msg(8'hB0,7'd1,7'd70);msg(8'hB0,7'd1,7'd20);
 @(posedge clk);#2;rst_n=0;repeat(3)drive(0,0,0,0);rst_n=1;'''
    assert tb_body.count(before) == 1
    tb_body = tb_body.replace(before, after, 1)
    tb_body = tb_body.replace('integer accepts[0:3],controls[0:3],stalls[0:3];',
                              'integer accepts[0:3],controls[0:3],stalls[0:3],cancellations[0:3];')
    tb_body = tb_body.replace('   if(was_stalled)stalls[i]++;', '''   if(was_stalled)stalls[i]++;
   if(ref_dut.parsed_control && !ref_dut.parsed_control_keep_pending && ref_dut.control_locked &&
      ref_dut.locked_index==ref_dut.parsed_control_index)cancellations[i]++;''')
    tb_body = tb_body.replace('stalls[i]=0;end', 'stalls[i]=0;cancellations[i]=0;end')
    tb_body = tb_body.replace('  if(accepts[i]<100', '  if(cancellations[i]<1)$fatal(1,"vacuous locked cancellation lane=%0d",i);\n  if(accepts[i]<100')
    tb_body = tb_body.replace('  $display("PASS M2 full', '  $display("PASS directed locked cancellation lane=%0d cases=%0d",i,cancellations[i]);\n  $display("PASS M2 full')
    # Selector comparison is meaningful only when valid; invalid index is don't-care.
    a = '  if({nv,nd,nl,np,no,ne}'
    b = '''  if({dut.selected_valid,dut.grant_control} !== {ref_dut.selected_valid,ref_dut.grant_control} ||
     (dut.selected_valid && {dut.selected_index,dut.selected_value} !== {ref_dut.selected_index,ref_dut.selected_value}))
    $fatal(1,"full parser combinational selector mismatch lane=%0d cycle=%0d",i,cycles);
'''
    tb_body = tb_body.replace(a, b + a, 1)
    tb = out / 'tb.sv'
    tb.write_text(tb_body, encoding='utf-8')
    compiler = [shared.CAD / 'bin/iverilog.exe', '-B', shared.CAD / 'lib/ivl', '-g2012']

    def miter(name, body=None, good=True):
        src = candidate
        if body is not None:
            src = out / (name + '.sv')
            src.write_text(body, encoding='utf-8')
        image = out / (name + '.vvp')
        run(name + '_compile', compiler + ['-s', 'tb_m2_parser_miter', '-o', image, defs, src, reference, tb], timeout=45)
        run(name, [shared.CAD / 'bin/vvp.exe', image], good,
            'PASS M2 full original parser miter lane=3' if good else 'full parser')

    miter('positive')
    if label.startswith('E_'):
        mutations = [
            ('missing_grant_clear', '!granted_here;', "1'b1;"),
            ('missing_parse_cancel', 'parsed_here ? parsed_control_keep_pending', "parsed_here ? 1'b1")]
        start = source.index('    wire [31:0] control_pending_next;')
        end = source.index('    integer comb_fifo_index;', start)
        probe = '''module structure_probe(input wire [31:0] control_pending,
input wire parsed_control,input wire [4:0] parsed_control_index,
input wire parsed_control_keep_pending,input wire grant_control,
input wire [4:0] selected_index,output wire [31:0] observed);
''' + source[start:end] + '\nassign observed=control_pending_next;\nendmodule\n'
        vectors = out / 'transition_vectors.txt'
        count = 0
        with vectors.open('w', encoding='ascii') as stream:
            patterns = [0, 0xffffffff, 0xaaaaaaaa, 0x55555555, 0x80000001] + [1 << k for k in range(32)]
            for pending in patterns:
                for parsed_index in range(32):
                    for grant_index in range(32):
                        for flags in range(8):
                            parsed, grant, keep = bool(flags & 1), bool(flags & 2), bool(flags & 4)
                            expected = pending
                            # Independent imperative oracle: exact original NBA priority.
                            if grant:
                                expected &= ~(1 << grant_index)
                            if parsed:
                                if (grant and grant_index == parsed_index) or not keep:
                                    expected &= ~(1 << parsed_index)
                                else:
                                    expected |= 1 << parsed_index
                            stream.write(f'{pending:x} {int(parsed):x} {parsed_index:x} {int(keep):x} {int(grant):x} {grant_index:x} {expected:x}\n')
                            count += 1
        oracle_tb = f'''module tb_structure;
reg[31:0]p=0,expect_bits;reg parsed=0,keep=0,grant=0;reg[4:0]pi=0,gi=0;
wire[31:0]observed;structure_probe dut(p,parsed,pi,keep,grant,gi,observed);
integer fd,n=0,rc;
initial begin
fd=$fopen("transition_vectors.txt","r");if(!fd)$fatal(1,"missing vectors");
while(!$feof(fd))begin
rc=$fscanf(fd,"%h %h %h %h %h %h %h\\n",p,parsed,pi,keep,grant,gi,expect_bits);
if(rc!=7)$fatal(1,"truncated vector");#1;
if(observed!==expect_bits)$fatal(1,"transition mismatch case=%0d",n);n++;
end
if(n!={count})$fatal(1,"empty/truncated vector count");
$display("PASS transition oracle cases=%0d",n);$finish;end
endmodule
'''
    else:
        mutations = [
            ('linear_not_cyclic', 'parsed_precedes_first)) begin', '(parsed_control_index <= old_first_index))) begin'),
            ('wrong_second_wrap', '(suffix_first_valid[1] ? prefix_first_index[1] : prefix_second_index[1]);', '(suffix_first_valid[1] ? prefix_second_index[1] : prefix_first_index[1]);')]
        start = source.index('    // ISOLATED F:')
        end = source.index('    integer comb_fifo_index;', start)
        a = source.index('    always_comb begin\n        parsed_control_keep_pending')
        b = source.index('    // At most one locked control event;', a)
        probe = '''module structure_probe(input wire [31:0]control_pending,
input wire[4:0]round_robin_index,input wire parsed_control,
input wire[4:0]parsed_control_index,input wire[11:0]value_in,
output logic selected_valid,output logic[4:0]selected_index,output logic[11:0]selected_value);
import audio_defs_pkg::*;
performance_event_t parsed_event_data;
wire performance_event_t locked_event='0;
wire control_locked=0;wire[4:0]locked_index=0;
wire[15:0]mod_sent_valid=16'hffff;wire[11:0]mod_sent_value[0:15];
wire[11:0]pending_value[0:31];
for(genvar k=0;k<16;k++)assign mod_sent_value[k]=0;
for(genvar k=0;k<32;k++)assign pending_value[k]=12'(k+1);
always_comb begin parsed_event_data='0;parsed_event_data.control_value=value_in;end
logic parsed_control_keep_pending,grant_control;
wire[15:0]control_cooldown=1;wire[3:0]fifo_count=0;
wire parsed_discrete=0,discrete_handshake=0,burst_limit_reached=0;
''' + source[start:end] + source[a:b] + '\nendmodule\n'
        vectors = out / 'selector_vectors.txt'
        patterns = [0, 0xffffffff, 0xaaaaaaaa, 0x55555555]
        patterns += [1 << k for k in range(32)]
        patterns += [(1 << k) | (1 << ((k + offset) % 32)) for k in range(32) for offset in (1, 17)]
        rng = random.Random(0x1382026)
        patterns += [rng.getrandbits(32) for _ in range(32)]
        count = 0
        with vectors.open('w', encoding='ascii') as stream:
            for pending in patterns:
                for rr in range(32):
                    for update in range(65):
                        parsed = update != 0
                        ix = (update - 1) // 2 if parsed else 0
                        value = 371 if parsed and update % 2 else 0
                        # Scan actual absolute slots in circular order; no RTL tree replica.
                        bitmap = pending
                        if parsed:
                            if ix % 2 and value == 0:
                                bitmap &= ~(1 << ix)
                            else:
                                bitmap |= 1 << ix
                        winner = next(((rr + k) % 32 for k in range(32) if bitmap & (1 << ((rr + k) % 32))), None)
                        valid = winner is not None
                        index = winner if valid else 0
                        payload = (value if parsed and index == ix else index + 1) if valid else 0
                        stream.write(f'{pending:x} {rr:x} {int(parsed):x} {ix:x} {value:x} {int(valid):x} {index:x} {payload:x}\n')
                        count += 1
        oracle_tb = f'''module tb_structure;
reg[31:0]p=0;reg[4:0]rr=0,ix=0,expected_index;reg parsed=0,expected_valid;
reg[11:0]value_in=0,expected_value;wire v;wire[4:0]index_out;wire[11:0]value_out;
structure_probe dut(p,rr,parsed,ix,value_in,v,index_out,value_out);
integer fd,n=0,rc;
initial begin
fd=$fopen("selector_vectors.txt","r");if(!fd)$fatal(1,"missing vectors");
while(!$feof(fd))begin
rc=$fscanf(fd,"%h %h %h %h %h %h %h %h\\n",p,rr,parsed,ix,value_in,expected_valid,expected_index,expected_value);
if(rc!=8)$fatal(1,"truncated vector");#1;
if(v!==expected_valid || (v && {{index_out,value_out}}!=={{expected_index,expected_value}}))
$fatal(1,"selector mismatch case=%0d",n);n++;
end
if(n!={count})$fatal(1,"empty/truncated vector count");
$display("PASS selector oracle cases=%0d",n);$finish;end
endmodule
'''
    for name, before, after in mutations:
        assert source.count(before) == 1, name
        if label.startswith('E_'):
            miter(name, source.replace(before, after, 1), good=False)
    probe_path = out / 'probe.sv'
    probe_tb = out / 'tb_structure.sv'
    probe_path.write_text(probe, encoding='utf-8')
    probe_tb.write_text(oracle_tb, encoding='utf-8')
    image = out / 'oracle.vvp'
    run('oracle_compile', compiler + ['-s', 'tb_structure', '-o', image, defs, probe_path, probe_tb], timeout=45)
    run('oracle', [shared.CAD / 'bin/vvp.exe', image], marker=f'oracle cases={count}')
    for name, before, after in mutations:
        assert probe.count(before) == 1, name
        bad = out / (name + '_probe.sv')
        bad.write_text(probe.replace(before, after, 1), encoding='utf-8')
        bad_image = out / (name + '_probe.vvp')
        run(name + '_probe_compile', compiler + ['-s', 'tb_structure', '-o', bad_image, defs, bad, probe_tb], timeout=45)
        run(name + '_probe', [shared.CAD / 'bin/vvp.exe', bad_image], good=False, marker='mismatch')
    # Guard against empty or truncated evidence. No fake PASS from an empty file.
    original_vectors = vectors.read_bytes()
    for name, bad in [('empty_vectors', b''), ('truncated_vectors', original_vectors[:original_vectors.index(b'\n') + 1])]:
        vectors.write_bytes(bad)
        run(name, [shared.CAD / 'bin/vvp.exe', image], good=False, marker='vector')
    vectors.write_bytes(original_vectors)
    review = {
        'passed': True, 'candidate_SHA256': shared.sha(candidate.read_bytes()),
        'frozen_reference_SHA256': shared.sha(original), 'runs': runs,
        'oracle_cases': count, 'oracle_vectors_SHA256': shared.sha(original_vectors),
        'original_TB_SHA256': shared.sha(old_tb.read_bytes()), 'adapted_TB_SHA256': shared.sha(tb.read_bytes()),
        'coverage': 'Four configs x 256205 cycles, all public outputs and all original registered state; same-cycle selection/grant; directed CC1 locked-excursion-cancellation; two compiled behavioral mutants rejected; independent imperative oracle; empty/truncated vector guards',
        'interface_decode_FIFO_counters_literal_unchanged': True,
        'new_registers': 0, 'public_latency_cycles_added': 0, 'formal_repo_written': False,
        'actual_evidence_directory': str(out), 'run_driver_SHA256': shared.sha(Path(__file__).read_bytes())}
    shared.write_json(out / 'functional_review.json', review)
    if folder_name != 'functional':
        assert not (shared.OUT / 'functional/functional_review.json').exists()
        shared.write_json(shared.OUT / 'functional/functional_review.json', review)


def execute(label, physical=True):
    assert label in LABELS
    shared.LABEL = label
    shared.OUT = HERE / label
    shared.SCOPE = HERE / 'candidates' / label
    manifest_path = shared.SCOPE / 'manifest.json'
    assert not manifest_path.exists(), 'Never overwrite earlier trial'
    source = (shared.SCOPE / 'midi_event_parser.sv').read_bytes()
    shared.write_json(manifest_path, {'frozen_parser_SHA': shared.sha((shared.BASE / 'sources/midi_event_parser.sv').read_bytes()),
                                    'candidate_SHA': shared.sha(source), 'origin': str(shared.BASE),
                                    'method': label, 'physical_trial_limit': 1,
                                    'new_registers': 0, 'public_latency_cycles_added': 0})
    shared.prepare()
    functional(label)
    if physical:
        shared.build()


def collect():
    results, pending = [], []
    for label in LABELS:
        path = HERE / label / 'build_receipt.json'
        if not path.exists():
            pending.append({'label': label, 'state': 'not_built'})
            continue
        receipt = json.loads(path.read_text(encoding='utf-8'))
        if receipt['state'] != 'finished' or receipt['exit_code'] != 0:
            pending.append({'label': label, 'receipt': receipt})
            continue
        result = assessor.evaluate(label)
        results.append(result)
        print(label, 'GATE', result['offline_report_gate_passed'], 'ERRORS', result['errors'],
              'PATHS', result['global_worst_paths'], result['recovery_removal_worst_paths'],
              'RESOURCES', result['resources'], flush=True)
    shared.write_json(HERE / 'results.json', {'baseline': assessor.report(shared.BASE), 'results': results, 'pending': pending})


def analyze_baseline():
    rows = assessor.parsed(assessor.read(shared.BASE / 'impl/pnr/audio_visual_coexistence_top_tr_content.html'))
    start = next(i for i, (_, row) in enumerate(rows) if len(row) == 7 and
                 row[-1] == 'u_midi_input/u_midi_event_parser/control_pending_28_s1/Q')
    end = next(i for i in range(start + 1, len(rows)) if len(rows[i][1]) == 7 and
               rows[i][1][-1] == 'u_midi_input/u_midi_event_parser/control_pending_4_s1/CE')
    path = [row for _, row in rows[start:end + 1] if len(row) == 7]
    result = {'baseline': str(shared.BASE), 'setup_slack_ns': 0.025,
              'path_steps': path, 'cell_or_ALU_steps': sum(row[2] == 'tINS' for row in path),
              'delay_ns': {kind: round(sum(float(row[1]) for row in path if row[2] == kind), 3)
                           for kind in ['tC2Q', 'tNET', 'tINS']},
              'hypothesis_not_result': 'Remove variable-bit feedback or rotation/rank arithmetic without extra pipeline state',
              'global_routing_utilization_known': False}
    target = HERE / 'baseline_path_analysis.json'
    assert not target.exists()
    shared.write_json(target, result)
    print('BASELINE', result['cell_or_ALU_steps'], 'cell/ALU steps', result['delay_ns'])


if __name__ == '__main__':
    args = sys.argv[1:]
    if args == ['init']:
        protect()
    elif len(args) == 2 and args[0] in ['run', 'prepare-functional']:
        protect(check=True)
        try:
            execute(args[1], physical=args[0] == 'run')
        finally:
            protect(check=True)
    elif len(args) == 2 and args[0] == 'build':
        assert args[1] in LABELS
        shared.OUT = HERE / args[1]
        protect(check=True)
        try:
            shared.build()
        finally:
            protect(check=True)
    elif args == ['collect']:
        collect()
        protect(check=True)
    elif args == ['analysis']:
        analyze_baseline()
    elif args in [['repair-E-coverage'], ['repair-E-coverage-v3']]:
        shared.OUT = HERE / LABELS[0]
        assert not (shared.OUT / 'build_receipt.json').exists()
        protect(check=True)
        try:
            functional(LABELS[0], 'functional_v3_directed' if args[0].endswith('-v3') else 'functional_v2_directed')
            shared.build()
        finally:
            protect(check=True)
    elif args == ['selftest']:
        suite = unittest.TestLoader().loadTestsFromTestCase(assessor.FullReportTests)
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(assessor.BaselineTests))
        with (HERE / 'report_selftest.log').open('w', encoding='utf-8') as stream:
            outcome = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        print('Report checker', outcome.testsRun, 'PASS' if outcome.wasSuccessful() else 'FAIL')
        assert outcome.wasSuccessful()
    else:
        raise ValueError('Choose init, run LABEL, collect, selftest')
