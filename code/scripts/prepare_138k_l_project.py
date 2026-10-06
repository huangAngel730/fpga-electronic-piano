"""Materialize and audit the signed-off 138K L project with local paths."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = "L_locations_guard065"
TRIAL = ROOT / "code/rtl/138K_try/hold_trials_20261005"
ARCHIVE = TRIAL / "M3_138K_Hold修复证据_20261005.zip"
ARCHIVE_SHA256 = (
    "c4eeefac8c28e3ebc01475177601a65abfc0da6f314b1c80f94b223ee9fa5b50"
)
SOURCE_PROJECT = "audio_visual_coexistence_top.gprj"
SOURCE_PROJECT_SHA256 = (
    "c8a468df339b356df7bdbaa15cfffe46fc43e70bf0b4826ff3a8eb20ae826c1a"
)
BUILD_ROOT = ROOT / "code/build/138k_l"
DEFAULT_OUTPUT = BUILD_ROOT / "staged"
EXPECTED_DEVICE = {
    "name": "GW5AST-138C",
    "pn": "GW5AST-LV138PG484AC1/I0",
    "index": "gw5ast138c-007",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def require_output(path: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to(BUILD_ROOT.resolve())
    if resolved == BUILD_ROOT.resolve():
        raise ValueError("OUTPUT_MUST_BE_CHILD_OF_138K_BUILD_ROOT")
    return resolved


def archive_truth() -> dict[str, object]:
    if sha256(ARCHIVE.read_bytes()) != ARCHIVE_SHA256:
        raise ValueError("SEALED_ARCHIVE_SHA")
    manifest = json.loads(
        (TRIAL / CANDIDATE / "input_manifest.json").read_text(encoding="utf-8")
    )
    expected = {item["path"]: item["candidate_SHA256"] for item in manifest["inputs"]}
    if len(expected) != 56:
        raise ValueError("SEALED_INPUT_COUNT")
    prefix = CANDIDATE + "/"
    with zipfile.ZipFile(ARCHIVE) as archive:
        if archive.testzip() is not None:
            raise ValueError("SEALED_ARCHIVE_CRC")
        inputs = {}
        for relative, digest in expected.items():
            data = archive.read(prefix + relative)
            if sha256(data) != digest:
                raise ValueError("SEALED_INPUT_SHA " + relative)
            inputs[relative] = data
        project_data = archive.read(prefix + SOURCE_PROJECT)
        run_tcl = archive.read(prefix + "run.tcl")
    if sha256(project_data) != SOURCE_PROJECT_SHA256:
        raise ValueError("SEALED_PROJECT_SHA")
    return {
        "inputs": inputs,
        "project": project_data,
        "run_tcl": run_tcl,
    }


def project_description(project_data: bytes) -> tuple[ET.Element, list[ET.Element], str]:
    root = ET.fromstring(project_data)
    device = root.find("Device")
    file_list = root.find("FileList")
    if device is None or file_list is None:
        raise ValueError("PROJECT_STRUCTURE")
    if (
        device.attrib.get("name") != EXPECTED_DEVICE["name"]
        or device.attrib.get("pn") != EXPECTED_DEVICE["pn"]
        or (device.text or "").strip() != EXPECTED_DEVICE["index"]
    ):
        raise ValueError("PROJECT_DEVICE")
    files = list(file_list)
    if len(files) != 47:
        raise ValueError("PROJECT_FILE_COUNT")
    roots = {
        entry.attrib["path"].replace("\\", "/").split("/sources/")[0]
        for entry in files
        if "/sources/" in entry.attrib["path"].replace("\\", "/")
    }
    if len(roots) != 1:
        raise ValueError("PROJECT_SOURCE_ROOT")
    old_root = next(iter(roots))
    for entry in files:
        path = entry.attrib["path"].replace("\\", "/")
        if not path.startswith(old_root + "/"):
            raise ValueError("PROJECT_MIXED_ROOT " + path)
    return root, files, old_root


def adapted_inputs(
    inputs: dict[str, bytes], old_root: str, input_root: Path
) -> tuple[dict[str, bytes], dict[str, dict[str, object]]]:
    new_root = input_root.as_posix()
    adapted = {}
    records = {}
    for relative, original in inputs.items():
        data = original
        redirects = 0
        if relative.startswith("sources/"):
            text = original.decode("utf-8")
            redirects = text.count(old_root)
            if redirects:
                data = text.replace(old_root, new_root).encode("utf-8")
        adapted[relative] = data
        records[relative] = {
            "sealed_sha256": sha256(original),
            "adapted_sha256": sha256(data),
            "path_redirect_count": redirects,
        }
    if sum(record["path_redirect_count"] > 0 for record in records.values()) != 9:
        raise ValueError("PATH_REDIRECT_SOURCE_COUNT")
    return adapted, records


def generate(output: Path) -> dict[str, object]:
    output = require_output(output)
    truth = archive_truth()
    source_root, source_files, old_root = project_description(truth["project"])
    input_root = output / "inputs"
    adapted, records = adapted_inputs(truth["inputs"], old_root, input_root)

    expected_files = {
        (input_root / relative).resolve() for relative in adapted
    } | {
        (output / SOURCE_PROJECT).resolve(),
        (output / "run.tcl").resolve(),
        (output / "receipt.json").resolve(),
    }
    if output.exists():
        unexpected = {
            path.resolve() for path in output.rglob("*") if path.is_file()
        } - expected_files
        if unexpected:
            raise ValueError(
                "UNEXPECTED_STAGED_FILE "
                + ",".join(sorted(path.as_posix() for path in unexpected))
            )
    input_root.mkdir(parents=True, exist_ok=True)
    for relative, data in adapted.items():
        destination = input_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)

    for entry in source_files:
        original = entry.attrib["path"].replace("\\", "/")
        relative = original.removeprefix(old_root + "/")
        entry.attrib["path"] = (input_root / relative).resolve().as_posix()
    project_path = output / SOURCE_PROJECT
    ET.ElementTree(source_root).write(
        project_path, encoding="utf-8", xml_declaration=True
    )

    source_tcl = truth["run_tcl"].decode("utf-8")
    replaced_tcl, count = re.subn(
        r"open_project\s+\{[^}]+\}",
        "open_project {" + project_path.resolve().as_posix() + "}",
        source_tcl,
        count=1,
    )
    if count != 1 or old_root in replaced_tcl:
        raise ValueError("RUN_TCL_PATH_REWRITE")
    (output / "run.tcl").write_text(
        replaced_tcl, encoding="utf-8", newline="\n"
    )

    receipt = {
        "date": "2026-10-06",
        "source_commit": "0bb5c66862dcbd9dc3894b055d9703e2b3cd0e76",
        "source_archive_sha256": ARCHIVE_SHA256,
        "candidate": CANDIDATE,
        "source_project_sha256": SOURCE_PROJECT_SHA256,
        "device": EXPECTED_DEVICE,
        "input_count": len(adapted),
        "project_file_count": len(source_files),
        "path_adapted_source_count": sum(
            record["path_redirect_count"] > 0 for record in records.values()
        ),
        "exact_input_count": sum(
            record["sealed_sha256"] == record["adapted_sha256"]
            for record in records.values()
        ),
        "inputs": records,
        "generated_project_sha256": sha256(project_path.read_bytes()),
        "generated_run_tcl_sha256": sha256((output / "run.tcl").read_bytes()),
        "gowin_executed": False,
        "programmed": False,
    }
    write_json(output / "receipt.json", receipt)
    check(output)
    return receipt


def check(output: Path) -> dict[str, object]:
    output = require_output(output)
    truth = archive_truth()
    source_root, source_files, old_root = project_description(truth["project"])
    input_root = output / "inputs"
    adapted, records = adapted_inputs(truth["inputs"], old_root, input_root)
    project_path = output / SOURCE_PROJECT
    generated_root, generated_files, _ = project_description(project_path.read_bytes())
    source_device = source_root.find("Device")
    generated_device = generated_root.find("Device")
    if ET.tostring(source_device) != ET.tostring(generated_device):
        raise ValueError("GENERATED_DEVICE_DIFFERENCE")
    for source, generated in zip(source_files, generated_files, strict=True):
        source_path = source.attrib["path"].replace("\\", "/")
        relative = source_path.removeprefix(old_root + "/")
        expected_path = (input_root / relative).resolve()
        actual_path = Path(generated.attrib["path"]).resolve()
        if (
            source.attrib.get("type") != generated.attrib.get("type")
            or source.attrib.get("enable") != generated.attrib.get("enable")
            or actual_path != expected_path
        ):
            raise ValueError("GENERATED_PROJECT_FILE " + relative)
    for relative, expected in adapted.items():
        actual = (input_root / relative).read_bytes()
        if actual != expected:
            raise ValueError("GENERATED_INPUT " + relative)
    project_text = project_path.read_text(encoding="utf-8")
    tcl_text = (output / "run.tcl").read_text(encoding="utf-8")
    if old_root in project_text or old_root in tcl_text:
        raise ValueError("OLD_ROOT_REMAINS")
    receipt = json.loads((output / "receipt.json").read_text(encoding="utf-8"))
    if (
        receipt["source_archive_sha256"] != ARCHIVE_SHA256
        or receipt["input_count"] != 56
        or receipt["project_file_count"] != 47
        or receipt["path_adapted_source_count"] != 9
        or receipt["exact_input_count"] != 47
        or receipt["gowin_executed"] is not False
        or receipt["programmed"] is not False
    ):
        raise ValueError("RECEIPT_CONTRACT")
    for relative, record in records.items():
        if receipt["inputs"][relative] != record:
            raise ValueError("RECEIPT_INPUT " + relative)
    print(
        "PASS 138K L path adapter: 56 inputs, 47 project files, "
        "9 path-only source rewrites, no Gowin/programming"
    )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.prepare:
        generate(args.output)
    else:
        check(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
