"""Independently check 24 newly executed fragment commands against old plan."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "code/docs/hardware/score_ble_v1"
TEST = ROOT / "code/software/score_ble_test_candidate/acceptance.py"
OLD_PLAN = "6d87ea3bef47e080a5cef49105b76ecc725b9d55b49bed5e88942102fbacb6d1"
NEW_PLAN = "bf83514bc7a7d4cde2b3073d912cfd0ca55e0c01423ba6e9ef13a72c94924441"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def plan_hash(rows):
    plan = [{k: v for k, v in row.items() if k != "actual"} for row in rows[:-1]]
    return sha(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode("ascii"))


def damage_commands():
    # Separate byte-level reference: protocol header + binascii CCITT-FALSE.
    import binascii
    body = struct.pack("<BBHHHH", 1, 2, 37, 9, 128, 128) + bytes(range(128))
    request = b"\xa5\x5a" + body + struct.pack("<H", binascii.crc_hqx(body, 0xffff))
    streams = {
        "MISSING_FRAGMENT": request[:20] + request[40:],
        "DUPLICATE_FRAGMENT": request[:20] + request[:20] + request[20:],
        "OUT_OF_ORDER": request[20:40] + request[:20] + request[40:],
    }
    return {tag: ["G 0 " + data[i:i+20].hex() for i in range(0, len(data), 20)]
            for tag, data in streams.items()}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--run", type=Path, required=True)
    args = cli.parse_args()
    source = args.run.resolve()
    if not source.is_relative_to((ROOT / "code/output").resolve()):
        cli.error("run must be inside code/output")
    out = source / "fragment_audit"
    if out.exists():
        cli.error("refusing to overwrite audit")
    out.mkdir()
    receipt = {"passed": False, "newly_executed_bytes_only": True,
               "old_24_bytes_claimed": False, "wireless_or_devices": False}
    try:
        sealed = base64.b64decode((DOCS / "evidence.zip.b64").read_bytes())
        meta = json.loads((DOCS / "raw_manifest.json").read_text(encoding="utf-8"))
        if sha(sealed) != meta["archive_sha256"]:
            raise ValueError("OLD_ARCHIVE_IDENTITY")
        with zipfile.ZipFile(io.BytesIO(sealed)) as archive:
            if set(archive.namelist()) != set(meta["files"]):
                raise ValueError("OLD_ARCHIVE_MEMBERS")
            for name, info in meta["files"].items():
                data = archive.read(name)
                if sha(data) != info["sha256"] or len(data) != info["bytes"]:
                    raise ValueError("OLD_RAW_IDENTITY " + name)
            original = json.loads(archive.read("receipt.json"))
            old_rows = [json.loads(line) for line in archive.read("positive.jsonl").decode("utf-8").splitlines()]
        if plan_hash(old_rows) != OLD_PLAN:
            raise ValueError("OLD_PLAN_IDENTITY")
        receipt["original_source_sha256"] = original["source_sha256"]
        legacy = subprocess.run(["git", "show", "dd689ec:code/software/score_ble_test_candidate/acceptance.py"],
                                cwd=ROOT, capture_output=True, timeout=30, check=False)
        old_source = original["source_sha256"][TEST.relative_to(ROOT).as_posix()]
        if legacy.returncode or sha(legacy.stdout) != old_source:
            raise ValueError("LEGACY_TEST_SOURCE_IDENTITY")
        (out / "legacy_acceptance.py").write_bytes(legacy.stdout)
        receipt["legacy_snapshot_sha256"] = sha(legacy.stdout)
        frozen_count = 0
        for path, expected in original["source_sha256"].items():
            # The original test driver and its newly added test descendants are
            # not business sources; all originally executed other files freeze.
            if path == TEST.relative_to(ROOT).as_posix():
                continue
            if sha((ROOT / path).read_bytes()) != expected:
                raise ValueError("FROZEN_SOURCE_IDENTITY " + path)
            frozen_count += 1
        new = [json.loads(line) for line in (source / "positive.jsonl").read_text(encoding="utf-8").splitlines()]
        commands = [json.loads(line) for line in (source / "positive.commands.jsonl").read_text(encoding="utf-8").splitlines()]
        run = json.loads((source / "receipt.json").read_text(encoding="utf-8"))
        if not run["desktop_passed"] or run["complete_t059_passed"]:
            raise ValueError("DESKTOP_ONLY_RECEIPT")
        if len(new) != 8523 or len(commands) != 8523 or new[-1] != old_rows[-1]:
            raise ValueError("CAPTURE_OR_COMMAND_COUNT")
        expected = damage_commands()
        observed = {tag: [] for tag in expected}
        fragment_rows = []
        same = 0
        for index, (old, row, sent) in enumerate(zip(old_rows[:-1], new[:-1], commands[:-1])):
            if sent != {"command": row["command"], "answer": row["actual"]}:
                raise ValueError("EXECUTED_COMMAND_CAPTURE_BINDING")
            if old["command"] == "damage fragment":
                tag = old["tag"]
                copy = dict(row, command="damage fragment")
                if copy != old or tag not in observed:
                    raise ValueError("DAMAGE_CHANGED_SEMANTICS")
                observed[tag].append(row["command"])
                fragment_rows.append({"id": index, "tag": tag, "command": row["command"],
                                      "actual": row["actual"], "input_bytes": len(bytes.fromhex(row["command"].split()[2]))})
            elif row != old:
                raise ValueError("UNRELATED_CAPTURE_CHANGED")
            else:
                same += 1
        if observed != expected or len(fragment_rows) != 24 or same != 8498:
            raise ValueError("FRAGMENT_BYTE_REFERENCE")
        if commands[-1] != {"command": "Q", "answer": []} or plan_hash(new) != NEW_PLAN:
            raise ValueError("NEW_PLAN_OR_COMMAND_END")
        receipt.update({"frozen_sources_verified": frozen_count, "unchanged_commands": same,
                        "new_fragment_commands": fragment_rows, "old_plan_sha256": OLD_PLAN,
                        "new_plan_sha256": NEW_PLAN, "source_sha256": {
                            TEST.relative_to(ROOT).as_posix(): sha(TEST.read_bytes()),
                            Path(__file__).resolve().relative_to(ROOT).as_posix(): sha(Path(__file__).read_bytes())}})
        receipt["input_artifact_sha256"] = {name: sha((source / name).read_bytes()) for name in
                                             ("positive.jsonl", "positive.commands.jsonl", "receipt.json")}
        # Specific corruption of each of the formerly label-only command bytes
        # must fail the public CLI, even when outputs/expectations are unchanged.
        tests = []
        for row in fragment_rows:
            damaged = [dict(item) for item in new]
            index = row["id"]
            parts = damaged[index]["command"].split()
            raw = bytearray.fromhex(parts[2])
            raw[-1] ^= 1
            damaged[index]["command"] = "G 0 " + raw.hex()
            cap = out / ("wrong_fragment_" + str(index) + ".jsonl")
            cap.write_text("".join(json.dumps(item) + "\n" for item in damaged), encoding="utf-8", newline="\n")
            command = [sys.executable, "-B", "-X", "utf8", str(TEST), "check", "--capture", str(cap)]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=30, check=False)
            label = cap.stem
            for stream, data in (("stdout", result.stdout), ("stderr", result.stderr)):
                (out / (label + "." + stream + ".log")).write_bytes(data)
            if result.returncode != 1 or b"PUBLIC_REFERENCE_PLAN_CHANGED" not in result.stderr:
                raise ValueError("FRAGMENT_CORRUPTION_FALSE_PASS")
            tests.append({"id": index, "command": command, "exit": result.returncode,
                          "capture_sha256": sha(cap.read_bytes()), "stdout_sha256": sha(result.stdout),
                          "stderr_sha256": sha(result.stderr)})
        receipt["24_byte_corruptions_rejected"] = tests
        receipt["passed"] = True
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError) as error:
        receipt["error"] = str(error)
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("PASS 24 new executed fragment bytes / 8498 unchanged" if receipt["passed"] else "FAIL " + receipt["error"])
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
