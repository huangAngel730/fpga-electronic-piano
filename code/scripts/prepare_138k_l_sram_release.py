"""Create one non-overwriting SRAM-only release from the exact V0197 build."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile


sys.dont_write_bytecode = True
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import check_138k_l_sram_release as checker  # noqa: E402


RUN = ROOT / "code/build/138k_l/runs/run_20261006_a0cb805_exact"
PNR = RUN / "project/impl/pnr"
PROJECT = RUN / "project"
TRACKED_EVIDENCE = ROOT / "code/docs/evidence/t056_138k_l_exact_build_20261006.json"
FILES = {
    "bitstream/audio_visual_coexistence_top.fs": PNR / "audio_visual_coexistence_top.fs",
    "reports/audio_visual_coexistence_top_tr_content.html": PNR
    / "audio_visual_coexistence_top_tr_content.html",
    "reports/audio_visual_coexistence_top.rpt.txt": PNR
    / "audio_visual_coexistence_top.rpt.txt",
    "reports/audio_visual_coexistence_top.pin.html": PNR
    / "audio_visual_coexistence_top.pin.html",
    "reports/cmd.do": PNR / "cmd.do",
    "reports/device.cfg": PNR / "device.cfg",
    "constraints/audio_visual.cst": PROJECT / "inputs/constraints/audio_visual.cst",
    "constraints/audio_visual_hold055.sdc": PROJECT
    / "inputs/constraints/audio_visual_hold055.sdc",
    "evidence/assessment.json": RUN / "assessment.json",
    "evidence/build_receipt.json": RUN / "build_receipt.json",
    "evidence/frozen_project_receipt.json": PROJECT / "receipt.json",
    "evidence/t056_138k_l_exact_build_20261006.json": TRACKED_EVIDENCE,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def output_path(path: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to((ROOT / "code/output").resolve())
    if resolved.exists():
        raise FileExistsError("REFUSE_OVERWRITE " + str(resolved))
    return resolved


def prepare(output: Path) -> dict[str, object]:
    output = output_path(output)
    output.mkdir(parents=True)
    records = {}
    for relative, source in FILES.items():
        if not source.is_file():
            raise FileNotFoundError("SOURCE_MISSING " + str(source))
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        records[relative] = {
            "bytes": destination.stat().st_size,
            "sha256": sha256(destination),
        }
    readme = """# T056 Tang Mega 138K L SRAM-only release

This local bundle is prepared from the exact V0197 build. It is not a Flash
release and is not evidence of board testing. Before programming, run the
release checker and confirm the physical core board is Tang Mega 138K, the
Dock/wiring is unchanged, and there are no new 5 V signals or temporary wires.

Expected bitstream SHA256:
598ec9bdf4fe20718f0f0a79a94cc6daed518103c1c4007ce2fec6231f2fff48

Programming contract: device GW5AST-138C, operation_index 2 (SRAM Program).
Never use operation 5-15 or any Flash mode for this release.
"""
    recovery = """# Recovery

This release uses volatile SRAM only and does not modify external or embedded
Flash. To recover from a failed image, disconnect power from the board, wait
at least five seconds, and reconnect it. The previously stored Flash image, if
any, remains unchanged. Keep the Tang Mega 60K board and its existing bitstream
separate; a 60K bitstream must never be programmed into the 138K device.
"""
    write_text(output / "README.md", readme)
    write_text(output / "RECOVERY.md", recovery)
    for relative in ("README.md", "RECOVERY.md"):
        path = output / relative
        records[relative] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    manifest = {
        "date": "2026-10-06",
        "release_kind": "SRAM-only",
        "device": checker.EXPECTED_DEVICE,
        "part": checker.EXPECTED_PART,
        "source_commit": checker.EXPECTED_SOURCE_COMMIT,
        "build_runner_commit": checker.EXPECTED_BUILD_COMMIT,
        "repository_head_when_prepared": "f52a0704508b09579043dd3940b24b0fbf93f1aa",
        "bitstream": "bitstream/audio_visual_coexistence_top.fs",
        "bitstream_sha256": checker.EXPECTED_BITSTREAM_SHA256,
        "programmer_operation_index": 2,
        "programmed": False,
        "flash_modified": False,
        "board_release_allowed": False,
        "files": records,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    result = checker.check(output)
    if not result["passed"]:
        raise ValueError("GENERATED_RELEASE_FAILED_CHECK")
    archive = output.parent / (output.name + ".zip")
    if archive.exists():
        raise FileExistsError("REFUSE_OVERWRITE " + str(archive))
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(item for item in output.rglob("*") if item.is_file()):
            bundle.write(path, path.relative_to(output).as_posix())
    result.update(
        archive=str(archive),
        archive_bytes=archive.stat().st_size,
        archive_sha256=sha256(archive),
    )
    (output / "release_check.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = prepare(args.output)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("FAIL", error)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
