"""Offline audit of the single native synthesis, without invoking FPGA tools."""
import argparse
import copy
import hashlib
import html
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
SYN = ROOT / 'code/output/m3_score_bram_syn_20261010_01'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mapping(tree, log, source):
    lanes = {node.get('name'): node for node in tree.findall('SubModule')
             if node.get('name', '').startswith('byte_lanes[')}
    if set(lanes) != {f'byte_lanes[{i}].storage' for i in range(8)}:
        raise ValueError('MISSING_BODY_LANE')
    for node in lanes.values():
        if node.get('Bsram') != '1' or node.get('T_Bsram') != '1(1)':
            raise ValueError('BODY_NOT_NATIVE_BSRAM')
    if not re.search(r"Extracting RAM for identifier 'memory'\([^\n]*score_byte_lane\.sv", log):
        raise ValueError('MISSING_NATIVE_BODY_MEMORY_LOG')
    if source.count('reg [7:0] memory [0:1023];') != 1:
        raise ValueError('BODY_SOURCE_SHAPE_CHANGED')
    if tree.get('T_Bsram') != '24(16)':
        raise ValueError('MODULE_RESOURCE_CHANGED')
    return 8


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    output.relative_to(ROOT / 'code/output')
    output.mkdir(parents=True, exist_ok=False)
    receipt = json.loads((SYN / 'receipt.json').read_text(encoding='utf-8'))
    assert receipt['exit_code'] == 0 and not receipt['timed_out']
    for name, digest in receipt['output_sha256'].items():
        assert sha(SYN / name) == digest, name
    for name, digest in receipt['source_sha256'].items():
        assert sha(ROOT / name) == digest, name
    tree = ET.parse(SYN / 'score_ram_syn_rsc.xml').getroot()
    log = (SYN / 'synthesis.stdout.bin').read_text(encoding='utf-8', errors='replace')
    source = (SYN / 'score_byte_lane.sv').read_text(encoding='utf-8')
    body_count = mapping(tree, log, source)
    report = (SYN / 'score_ram_syn.rpt.html').read_text(encoding='utf-8')
    rows = []
    for raw in re.findall(r'<tr>(.*?)</tr>', report, re.S):
        cells = [html.unescape(re.sub(r'<[^>]+>', '', cell)).strip()
                 for cell in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', raw, re.S)]
        rows.append(cells)

    def row(label):
        return next(cells for cells in rows if cells and cells[0] == label)

    assert row('Part Number')[1] == 'GW5AST-LV138PG484AC1/I0'
    assert row('Device Version')[1] == 'C'
    assert row('Tool Version')[1] == 'V1.9.11.03 Education'
    assert row('Logic')[1] == '7446(7211 LUT, 235 ALU) / 138240'
    assert any(cells and '--Register as Latch' in cells[0]
               and cells[1].startswith('0 /') for cells in rows)
    assert any(cells and cells[0] == 'DPB' and cells[1] == '24' for cells in rows)
    assert row('Slack')[1] == '-3.786'
    assert row('From')[1] == 'request_session_3_s0'
    assert row('To')[1] == 'reply[25]_4_s10'
    assert any(cells[1:5] == ['clk', '40.000(MHz)', '34.739(MHz)', '30']
               for cells in rows)
    negatives = []
    for name in ('body_zero', 'native_log_removed', 'global_total_only'):
        mutant = copy.deepcopy(tree)
        mutant_log = log
        if name == 'body_zero':
            mutant.findall('SubModule')[2].set('Bsram', '0')
        elif name == 'native_log_removed':
            mutant_log = log.replace("Extracting RAM for identifier 'memory'", 'REMOVED')
        else:
            for child in list(mutant):
                mutant.remove(child)
        try:
            mapping(mutant, mutant_log, source)
        except ValueError as error:
            negatives.append(dict(case=name, rejected_by=str(error)))
        else:
            raise AssertionError('AUDIT_MUTANT_ACCEPTED:' + name)
    result = dict(
        status='BODY_BSRAM_MAPPING_CONFIRMED_TIMING_NOT_PASSED',
        synthesis_receipt_sha256=sha(SYN / 'receipt.json'),
        resources=dict(register=3373, logic=7446, lut_equivalent=7211,
                       lut_cells=7199, inverter=12, alu=235, latch=0,
                       bsram_module=24, bsram_body=body_count, primitive='DPB',
                       ssram='NOT_LISTED: hierarchy HTML -, XML attribute absent'),
        timing=dict(required_mhz=40, synthesis_estimate_mhz=34.739,
                    slack_ns=-3.786, logic_levels=30,
                    start='request_session_3_s0', end='reply[25]_4_s10',
                    passed=False, physical_sta_executed=False),
        warnings=[line for line in log.splitlines() if 'WARN' in line],
        audit_negatives=negatives, additional_synthesis_executed=False,
        netlist='Gowin protected; internal primitive ports not decrypted/inspected',
        evidence_sha256={path.name: sha(path) for path in SYN.iterdir() if path.is_file()},
        reviewer_script_sha256=sha(Path(__file__)),
        complete_task=False, hardware_verified=False)
    (output / 'receipt.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)
                                       + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
