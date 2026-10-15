"""One bounded Gowin build of an exact, staged M1 four-voice 138K board graph.

A successful process is only a candidate for report assessment; it is never a board release.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'code/output'
TOOL = Path('D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe')
JOB = ROOT / 'code/software/t052_runner_acceptance_candidate_20261012/windows_job.py'
TOP = 'm2_fourvoice_timbre_delay_board_top'
MAX_SECONDS = 1800


def digest(path):
    raw = path.read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prepared', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--timeout-seconds', type=int, default=MAX_SECONDS)
    a = ap.parse_args()
    stage, out = a.prepared.resolve(), a.output.resolve()
    output_root = OUTPUT.resolve()
    if not (1 <= a.timeout_seconds <= MAX_SECONDS):
        ap.error('TIMEOUT_OUT_OF_RANGE')
    if (not stage.is_relative_to(output_root) or out == output_root
            or not out.is_relative_to(output_root) or out.exists()):
        ap.error('STAGE_AND_NEW_OUTPUT_MUST_BE_UNDER_CODE_OUTPUT')
    receipt_path = stage / 'PREPARATION_RECEIPT.json'
    project = stage / (TOP + '.gprj')
    prep = json.loads(receipt_path.read_text(encoding='utf-8'))
    if (prep.get('status') != 'PREPARED_NOT_PHYSICALLY_ADMITTED'
            or prep.get('error') is not None or not TOOL.is_file()):
        ap.error('PREPARATION_OR_TOOL_NOT_VALID')
    if (stage / 'impl').exists() or (stage / 'run.tcl').exists():
        ap.error('STAGE_ALREADY_EXECUTED')
    if digest(project)['sha256'] != prep['project_sha256']:
        ap.error('PROJECT_SHA_MISMATCH')
    expected = {k.replace('\\', '/'): v for k, v in prep['input_files'].items()}
    files = [stage / k for k in expected]
    if not files or any(digest(p) != expected[p.relative_to(stage).as_posix()] for p in files):
        ap.error('PREPARED_INPUT_DRIFT')
    tree = ET.parse(project)
    configured = [Path(x.attrib['path']) for x in tree.getroot().iter('File')]
    if (not configured or any(not p.is_relative_to(stage) or p not in files for p in configured)):
        ap.error('PROJECT_FILE_SCOPE')
    protected = files + [project, receipt_path, TOOL, JOB, Path(__file__).resolve()]
    before = {str(p): digest(p) for p in protected}
    out.mkdir(parents=True)
    tcl = out / 'run.tcl'
    tcl.write_text('open_project {' + project.as_posix() + '}\n'
                   'set_option -top_module ' + TOP + '\n'
                   'set_option -verilog_std sysv2017\n'
                   'set_option -place_option 0\n'
                   'set_option -route_option 2\n'
                   'set_option -ireg_in_iob 1\n'
                   'set_option -oreg_in_iob 1\n'
                   'set_option -ioreg_in_iob 1\n'
                   'set_option -correct_hold_violation 1\n'
                   'set_option -clock_route_order 0\n'
                   'set_option -route_maxfan 23\n'
                   'run all\n', encoding='ascii', newline='\n')
    cmd = [str(TOOL), str(tcl)]
    record = {'status': 'FAIL_PARTIAL', 'board_release_allowed': False,
              'tool_calls': 0, 'command': cmd, 'cwd': str(stage),
              'timeout_seconds': a.timeout_seconds, 'timed_out': False,
              'exit_code': None, 'error': None, 'input_before': before,
              'tcl': digest(tcl), 'preparation_receipt': digest(receipt_path),
              'project': digest(project)}
    write_json(out / 'receipt.json', record)
    started = time.monotonic()
    job = None
    proc = None
    try:
        spec = importlib.util.spec_from_file_location('m2_windows_job', JOB)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        job = module.WindowsJob()
        with (out / 'stdout.log').open('xb') as stdout, (out / 'stderr.log').open('xb') as stderr:
            proc = subprocess.Popen(cmd, cwd=stage, stdout=stdout, stderr=stderr,
                                    creationflags=4)
            record['tool_calls'] = 1
            write_json(out / 'receipt.json', record)
            job.attach_and_resume(proc)
            try:
                record['exit_code'] = proc.wait(timeout=a.timeout_seconds)
            except subprocess.TimeoutExpired:
                record['timed_out'] = True
                job.terminate()
                record['exit_code'] = proc.wait(timeout=10)
    except Exception as exc:
        record['error'] = type(exc).__name__ + ': ' + str(exc)
        if proc is not None and proc.poll() is None and job is not None:
            job.terminate()
            proc.wait(timeout=10)
    finally:
        if job is not None:
            job.close()
        record['seconds'] = round(time.monotonic() - started, 3)
        record['input_after'] = {str(p): digest(p) for p in protected}
        record['input_unchanged'] = record['input_after'] == before
        record['log_sha256'] = {name: digest(out / name) for name in ('stdout.log', 'stderr.log')
                                if (out / name).is_file()}
        report_dir = stage / 'impl/pnr'
        record['pnr_artifacts'] = ({p.name: digest(p) for p in sorted(report_dir.iterdir())
                                    if p.is_file() and p.suffix.lower() in ('.html', '.txt', '.fs')}
                                   if report_dir.is_dir() else {})
        if record['exit_code'] == 0 and not record['timed_out'] and record['input_unchanged']:
            record['status'] = 'TOOL_EXIT0_REPORTS_REQUIRE_INDEPENDENT_REVIEW'
        else:
            record['status'] = 'FAIL_PARTIAL'
        write_json(out / 'receipt.json', record)
    print(json.dumps({k: record[k] for k in ('status', 'exit_code', 'timed_out', 'seconds', 'error',
                                               'input_unchanged', 'tool_calls')}, ensure_ascii=False))
    return 0 if record['status'].startswith('TOOL_EXIT0') else 1


if __name__ == '__main__':
    raise SystemExit(main())
