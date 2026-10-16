"""Create exclusive copies; never modify the staged earlier D delivery."""
import hashlib
import json
from pathlib import Path
import difflib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
OLD = HERE.parent
NEW_TB = ROOT / "code/tb/input/visualizer/m3_dual_slider_138k_candidate_20261015/night_20261016/RESUME_R01/tb_slider_audio_coexist.sv"
OLD_TB = NEW_TB.parent.parent / NEW_TB.name


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError("AMBIGUOUS_REPLACEMENT:" + old[:80])
    return text.replace(old, new)


def put(path, content):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def main():
    NEW_TB.parent.mkdir(exist_ok=False)
    NEW_TB.write_bytes(OLD_TB.read_bytes())
    old_checker = (OLD / "check_coexist.py").read_text(encoding="utf-8")
    checker = replace_once(old_checker, "Path(__file__).resolve().parents[5]", "Path(__file__).resolve().parents[6]")
    put(HERE / "check_coexist.py", checker)
    old_runner = (OLD / "run_coexist.py").read_text(encoding="utf-8")
    runner = replace_once(old_runner, "ROOT = HERE.parents[4]", "ROOT = HERE.parents[5]")
    runner = replace_once(runner, "night_20261016/tb_slider_audio_coexist.sv", "night_20261016/RESUME_R01/tb_slider_audio_coexist.sv")
    runner = replace_once(runner, "night_20261016/DISPATCH.md", "night_20261016/RESUME_R01/AUTHORIZATION_AND_DISPATCH.md")
    runner = replace_once(runner, "HERE.parent / \"repair_run_02/before.json\"", "HERE.parent.parent / \"repair_run_02/before.json\"")
    runner = replace_once(runner, 'inputs = sources + [JOB, DECODER, AUTH, Path(__file__).resolve(), HERE / "check_coexist.py", Path(sys.executable)]',
        'inputs = sources + [JOB, DECODER, AUTH, Path(__file__).resolve(), HERE / "check_coexist.py", Path(sys.executable), OLD_NORMAL, OLD_TB, OLD_CHECKER, OLD_RUNNER]')
    runner = replace_once(runner, 'ORIGINALS = [', '''OLD_NORMAL = HERE.parent / "RUN_03/positive/capture.csv"
OLD_TB = TB.parent.parent / TB.name
OLD_CHECKER = HERE.parent / "check_coexist.py"
OLD_RUNNER = HERE.parent / "run_coexist.py"
EXPECTED = {1: "UNEXPECTED_UNDERFLOW", 2: "SERIAL_PCM_LSBJ_OR_STEREO",
            3: "SERIAL_PCM_LSBJ_OR_STEREO", 4: "SERIAL_PCM_LSBJ_OR_STEREO"}
ORIGINALS = [''')
    runner = replace_once(runner, 'write(out / "before.json", before)', '''write(out / "before.json", before)
    old_seal = json.loads((HERE.parent / "MANIFEST.json").read_text())['files']
    for path in (OLD_NORMAL, OLD_TB, OLD_CHECKER, OLD_RUNNER):
        entry = old_seal[path.relative_to(ROOT).as_posix()]
        if entry['sha256'] != sha(path):
            raise RuntimeError("OLD_SEALED_INPUT_DRIFT:" + str(path))
    if TB.read_bytes() != OLD_TB.read_bytes():
        raise RuntimeError("RESUME_TB_MUST_MATCH_PASSED_NORMAL_SOURCE")
    if (HERE / "check_coexist.py").read_text().replace("parents[6]", "parents[5]") != OLD_CHECKER.read_text():
        raise RuntimeError("CHECKER_LOGIC_DRIFT")''')
    runner = replace_once(runner, '"tools_byte_bound_to_old_repair": True, "board_release_allowed": False}',
        '"tools_byte_bound_to_old_repair": True, "board_release_allowed": False, "expected_rejections": EXPECTED, "positive_group_rerun": False, "new_authorization_batch": "RESUME_R01"}')
    runner = replace_once(runner, '''for mutation, expected_diagnostic in [(0, None), (1, "UNEXPECTED_UNDERFLOW"),
                (2, "SERIAL_PCM_LSBJ_OR_STEREO"), (3, "SERIAL_PCM_LSBJ_OR_STEREO"),
                (4, "SERIAL_PCM_LSBJ_OR_STEREO")]:''', 'for mutation, expected_diagnostic in EXPECTED.items():')
    runner = replace_once(runner, '"passed": error is None and before == after', '"passed": error is None and before == after and len(results) == 4')
    runner = replace_once(runner, '"level": "L2_ISOLATED_DIAGNOSTIC_PCM_VISUAL_COEXISTENCE"', '"level": "L2_FOUR_RTL_BEHAVIORAL_NEGATIVE_REJECTIONS"')
    put(HERE / "run_negatives.py", runner)
    changes = {}
    for name, old, new in (("runner", old_runner, runner), ("checker", old_checker, checker)):
        diff = "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile="sealed/"+name, tofile="RESUME_R01/"+name))
        put(HERE / (name + ".diff"), diff)
        changes[name] = {"original_sha256": hashlib.sha256(old.encode()).hexdigest(),
                         "copy_sha256": hashlib.sha256(new.encode()).hexdigest()}
    changes["tb"] = {"bytes_equal_to_prior_passed_positive": True, "sha256": hashlib.sha256(NEW_TB.read_bytes()).hexdigest()}
    put(HERE / "COPY_MAP.json", json.dumps(changes, indent=2)+"\n")
    print(json.dumps(changes))


if __name__ == "__main__":
    main()
