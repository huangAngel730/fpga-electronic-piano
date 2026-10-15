"""Seal existing B/D evidence only: no subprocess, EDA, simulation or Git."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DOC = REPO / "code/docs/test/m3_m2td_audio_endpoint_audit_20261015/successor_R03"
STAGE = REPO / "code/output/m3_m2td_endpoint_probe_20261015_r01"
DELIVERY = DOC / "delivery_night_r03"
D_DOC = REPO / "code/docs/test/m3_dual_slider_138k_candidate_20261015"
D_ZIP = D_DOC / "delivery_night_r02/DUAL_SLIDER_NIGHT_PARTIAL_20261016.zip"
D_SHA = "6cee5e409e0082f5590ca68f45f61933eab15c4700e272c4f1195316d81185bc"
REPORT = "impl/pnr/m2_fourvoice_timbre_delay_board_top_tr_content.html"
EXCLUDE_SUFFIXES = {".fs", ".bin", ".binx", ".db", ".p", ".pr"}


def identity(blob):
    return {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}


def file_identity(path):
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return {"bytes": size, "sha256": digest.hexdigest()}


def json_blob(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main():
    if DELIVERY.exists():
        raise ValueError("delivery already exists; no overwrite")
    run = json.loads((STAGE / "RUN_RECEIPT.json").read_bytes())
    check = json.loads((STAGE / "ENDPOINT_CHECK_R01.json").read_bytes())
    if (run["exit_code"] != 0 or run["tool_calls"] != 1
            or not run["input_unchanged"] or not run["tool_identities_unchanged"]
            or check["status"] != "EXACT_DIRECTED_PAIRS_SHOWN_CANDIDATE_ONLY"
            or len(check["observations"]) != 10):
        raise ValueError("actual evidence is not the claimed candidate result")
    if file_identity(STAGE / REPORT) != check["actual_report"]:
        raise ValueError("report identity drift")
    if file_identity(STAGE / "RUN_RECEIPT.json") != check["actual_run_receipt"]:
        raise ValueError("receipt identity drift")
    for name, expected in run["input_before"].items():
        if file_identity(Path(name)) != expected:
            raise ValueError("bound launch source/input changed: " + name)
    if file_identity(D_ZIP)["sha256"] != D_SHA:
        raise ValueError("D sealed original identity drift")
    with zipfile.ZipFile(D_ZIP) as archive:
        if archive.testzip() is not None:
            raise ValueError("D CRC failed")

    selected = {}
    excluded = {}

    def add(path):
        if path.is_symlink():
            raise ValueError("symlink evidence refused: " + str(path))
        name = path.relative_to(REPO).as_posix()
        selected[name] = path

    for root in (HERE, DOC):
        for path in sorted(root.rglob("*")):
            if (path.is_file() and "__pycache__" not in path.parts
                    and not any(part.startswith("delivery_") for part in path.relative_to(root).parts)):
                add(path)
    for path in sorted(STAGE.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() in EXCLUDE_SUFFIXES:
            excluded[path.relative_to(REPO).as_posix()] = {
                **file_identity(path), "body_included": False,
                "reason": "local-only bitstream or large implementation database; not released"}
        else:
            add(path)
    fixed = [
        "code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1TD_整机PnR_STA_20261015.zip",
        "code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1双音色延迟_ModelSim自包含输入_20261015.zip",
        "code/software/m3_m2td_audio_endpoint_audit_20261015/endpoint_audit.py",
        "code/software/t052_runner_acceptance_candidate_20261012/windows_job.py",
        "code/docs/M3_四项并行主责授权_2026-10-15.md",
        "code/docs/M3_并行接管M2_40MHz音频STA端点准备_2026-10-15.md",
        "code/docs/M3_夜间八小时任务单_2026-10-15.md",
        "code/docs/M3_夜间M2候选权限预授权_2026-10-15.md",
    ]
    for relative in fixed:
        add(REPO / relative)
    for path in (D_ZIP, D_ZIP.parent / "DELIVERY.json",
                 D_DOC / "NIGHT_HANDOFF_TO_PARENT.txt", D_DOC / "NIGHT_RUN_RECEIPT.json"):
        add(path)

    bodies = {name: path.read_bytes() for name, path in selected.items()}
    before = {name: identity(blob) for name, blob in bodies.items()}
    manifest = {
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "B directed STA candidate plus exact sealed D PARTIAL original",
        "b_status": "ISOLATED_DIRECTED_B_CANDIDATE_PASS_PENDING_M2",
        "d_status": "PARTIAL_TWO_GROUPS_EXHAUSTED_CURRENT_SOURCE_UNCOMPILED",
        "files": before, "excluded_local_files": excluded,
        "board_release_allowed": False, "git_writes_by_this_window": 0,
        "delivery_status": "WAIT_USER_FORWARD_NOT_DELIVERED",
        "tools_started_by_sealer": 0,
    }
    bodies["MANIFEST.json"] = json_blob(manifest)
    DELIVERY.mkdir(exist_ok=False)
    target = DELIVERY / "B_DIRECTED_STA_CANDIDATE_20261016.zip"
    with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, blob in sorted(bodies.items()):
            archive.writestr(name, blob)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != len(bodies):
            raise ValueError("archive integrity failed")
        for name, blob in bodies.items():
            if archive.read(name) != blob:
                raise ValueError("archive readback failed: " + name)
    for name, path in selected.items():
        if file_identity(path) != before[name]:
            raise ValueError("input changed while sealing: " + name)
    receipt = {
        "archive": target.name, **file_identity(target), "members": len(bodies),
        "crc_verified": True, "all_member_bytes_sha_verified": True,
        "source_unchanged_during_seal": True, "physical_tool_calls": 1,
        "b_rounds_consumed": 1, "d_groups_consumed": 2,
        "b_status": manifest["b_status"], "d_status": manifest["d_status"],
        "published": False, "publisher": "总控 only",
        "board_release_allowed": False, "tools_started_by_sealer": 0,
        "excluded_local_files": excluded,
        "manifest_sha256": identity(bodies["MANIFEST.json"])["sha256"],
        "sealing_command": ["Python", "-I", "-S", "-B", "-X", "utf8", str(Path(__file__).resolve())],
        "cwd": str(REPO), "delivery_status": "WAIT_USER_FORWARD_NOT_DELIVERED",
    }
    with (DELIVERY / "DELIVERY.json").open("xb") as stream:
        stream.write(json_blob(receipt))
    print(json.dumps({k: v for k, v in receipt.items() if k not in ("excluded_local_files", "sealing_command")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
