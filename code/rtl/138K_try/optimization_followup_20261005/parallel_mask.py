"""Fresh second method, derived from success rather than the rejected pipeline."""
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
import experiment as shared

HERE = Path(__file__).resolve().parent
shared.SCOPE = shared.REPO / 'code/tb/common/midi_pending_mask_candidate'
shared.LABEL = 'B_parallel_pending_mask'
shared.OUT = HERE / shared.LABEL
OUT = shared.OUT


def functional():
    raw = shared.REPO / 'code/scripts/run_midi_pending_mask_candidate.py'
    text = raw.read_text(encoding='utf-8')
    replacements = [
        ("ROOT=Path(__file__).resolve().parents[2]", f'ROOT=Path({shared.REPO.as_posix()!r})'),
        ("SCOPE=ROOT/'code/tb/common/midi_pending_mask_candidate'", f'SCOPE=Path({shared.SCOPE.as_posix()!r})'),
        ("CAD=Path('D:/Gowin/oss-cad-suite')", f'CAD=Path({shared.CAD.as_posix()!r})'),
        ("out.relative_to(ROOT/'code/output')", f'out.relative_to(Path({OUT.as_posix()!r}))'),
        ("original=subprocess.check_output(['git','show',manifest['frozen_commit']+':code/rtl/input/midi_input/midi_event_parser.sv'],cwd=ROOT)",
         f"original=Path({(shared.BASE / 'sources/midi_event_parser.sv').as_posix()!r}).read_bytes()"),
        ("candidate=SCOPE/'midi_event_parser.sv'", f"candidate=Path({(OUT / 'sources/midi_event_parser.sv').as_posix()!r})"),
        ("defs=ROOT/'code/rtl/common/audio_defs_pkg.sv'", f"defs=Path({(OUT / 'sources/audio_defs_pkg.sv').as_posix()!r})"),
        ("'-g2012'", "'-B',CAD/'lib/ivl','-g2012'"),
        ("'current_formal_SHA':sha(ROOT/'code/rtl/input/midi_input/midi_event_parser.sv')",
         f"'current_formal_SHA':sha(Path({(shared.BASE / 'sources/midi_event_parser.sv').as_posix()!r}))")]
    for before, after in replacements:
        assert text.count(before) >= 1, before
        text = text.replace(before, after)
    runner = OUT / 'run_mask_isolated.py'
    runner.write_text(text, encoding='utf-8')
    shared.write_json(OUT / 'runner_provenance.json', {
        'original': str(raw), 'original_SHA256': shared.sha(raw.read_bytes()),
        'adapted_SHA256': shared.sha(runner.read_bytes()), 'adaptations': replacements})
    env = dict(os.environ)
    env['TMP'] = env['TEMP'] = str(OUT / 'functional_tmp')
    (OUT / 'functional_tmp').mkdir()
    process = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(runner),
                              '--output', str(OUT / 'functional')],
                             cwd=OUT, env=env, timeout=1100)
    assert process.returncode == 0, 'No PnR without functional PASS'
    path = OUT / 'functional/functional_review.json'
    evidence = json.loads(path.read_text(encoding='utf-8'))
    evidence.update({'passed': True, 'candidate_SHA256': shared.sha((OUT / 'sources/midi_event_parser.sv').read_bytes())})
    shared.write_json(path, evidence)


if __name__ == '__main__':
    assert sys.argv[1:] == ['start']
    shared.preserve_check()
    try:
        shared.prepare()
        functional()
        shared.build()
    finally:
        shared.preserve_check()
