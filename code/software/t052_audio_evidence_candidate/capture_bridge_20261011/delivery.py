"""Bounded bridge-only qualify/seal/isolated verify and forwarding pack.

No simulator, old WAV tests, mathematical model or EDA is executed.
"""

import argparse
import base64
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DOC = ROOT / "code/docs/hardware/t052_audio_evidence_v1/CAPTURE_BRIDGE_20261011"
ORIGINAL = "original/T052_repair_v2_pkg/"
CAP_MEMBER = ORIGINAL + "logs/tb_t052_polyphony.capture"
REQ_MEMBER = ORIGINAL + "logs/tb_t052_requests.log"
TB_MEMBER = ORIGINAL + "code/tb/audio/t052_polyphony/tb_t052_polyphony.sv"
EVIDENCE = ROOT / "code/docs/evidence/m2_t052_modelsim_delivery_review_20261011"
spec = importlib.util.spec_from_file_location("bridge", HERE / "bridge.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


def fresh(path):
    path = path.resolve()
    path.relative_to(ROOT / "code/output")
    path.mkdir(parents=True, exist_ok=False)
    return path


class Bounded:
    def __init__(self, output):
        self.start = time.monotonic()
        self.output = output
        self.steps = []

    def call(self, label, argv, expected=0, diagnostic=None):
        remaining = 300 - (time.monotonic() - self.start)
        b.require(remaining > 0, "TOTAL_TIMEOUT")
        begin = time.monotonic()
        try:
            result = subprocess.run(argv, capture_output=True,
                                    timeout=min(90, remaining), cwd=self.output)
            code, stdout, stderr = result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired as error:
            code, stdout, stderr = -1, error.stdout or b"", error.stderr or b""
        (self.output / (label + ".stdout.bin")).write_bytes(stdout)
        (self.output / (label + ".stderr.bin")).write_bytes(stderr)
        step = dict(label=label, command=argv, exit_code=code, expected_exit=expected,
                    diagnostic=diagnostic, stdout_sha256=b.sha(stdout),
                    stderr_sha256=b.sha(stderr), elapsed_seconds=time.monotonic() - begin)
        self.steps.append(step)
        b.dump(self.output / "steps.json", self.steps)
        b.require(code == expected, "UNEXPECTED_EXIT:" + label)
        if diagnostic:
            b.require(diagnostic.encode() in stdout + stderr, "MISSING_DIAGNOSTIC:" + label)
        print(label + ": exit " + str(code), flush=True)


def bridge_command(script, cap, req, config, output):
    return [sys.executable, "-I", "-S", "-B", str(script), "--capture", str(cap),
            "--requests", str(req), "--config", str(config), "--output", str(output)]


def qualify(output):
    out = fresh(output)
    run = Bounded(out)
    source_names = ("bridge.py", "test_bridge.py", "delivery.py")
    before = {name: b.sha((HERE / name).read_bytes()) for name in source_names}
    try:
        sources = out / "sources"
        sources.mkdir()
        for name in source_names:
            (sources / name).write_bytes((HERE / name).read_bytes())
        archive_raw = (EVIDENCE / "RAW_REVIEW.zip").read_bytes()
        archive = zipfile.ZipFile(io.BytesIO(archive_raw))
        b.require(len(archive.namelist()) == len(set(archive.namelist())), "DUPLICATE_MEMBERS")
        evidence = out / "reference_evidence"
        evidence.mkdir()
        input_members = [name for name in archive.namelist()
                         if name.startswith((ORIGINAL, "readonly_dependencies/"))
                         or name in ("capture_review.json", "original_members.json")]
        input_identity = {}
        for name in input_members:
            safe = PurePosixPath(name)
            b.require(not safe.is_absolute() and ".." not in safe.parts, "UNSAFE_MEMBER")
            path = evidence / name
            path.parent.mkdir(parents=True, exist_ok=True)
            data = archive.read(name)
            path.write_bytes(data)
            input_identity[name] = dict(bytes=len(data), sha256=b.sha(data),
                                       use="read-only reference; not executed/imported")
        cap, req = evidence / CAP_MEMBER, evidence / REQ_MEMBER
        b.require(b.sha(cap.read_bytes()) == b.CAP_SHA
                  and b.sha(req.read_bytes()) == b.REQ_SHA
                  and b.sha((evidence / TB_MEMBER).read_bytes()) == b.TB_SHA,
                  "REFERENCE_INPUT_IDENTITY")
        b.dump(out / "reference_inputs.json", dict(
            original_review_zip_sha256=b.sha(archive_raw), members=input_identity,
            ModelSim_execution_identity_verified=False,
            ROM_mathematics="REUSED M2 V0289 only; bridge does not recompute ROM"))
        config = out / "config.json"
        b.dump(config, b.config_for(cap.read_bytes(), req.read_bytes(), 4137))
        run.call("new_bridge_tests", [sys.executable, "-I", "-S", "-B",
                                      str(sources / "test_bridge.py")])
        run.call("original_4137_export", bridge_command(sources / "bridge.py", cap, req,
                                                       config, out / "export"))
        negatives = out / "negative_inputs"
        negatives.mkdir()
        sc = b"ID=0 PCM v0=-32768 v1=-1 v2=0 v3=32767 ACT=4 CLIP=1\n"
        sr = b"REQ 0 04b17e4d 00000000 00000000 ffffffff 15\n"
        cases = [
            ("unknown_tag", sc, sr.replace(b"REQ", b"UNKNOWN"), "REQUEST_SCHEMA"),
            ("bad_mask", sc, sr.replace(b"15\n", b"17\n"), "MASK_RANGE"),
            ("bad_act", sc.replace(b"ACT=4", b"ACT=2"), sr, "ACT_MASK"),
            ("bad_id", sc.replace(b"ID=0", b"ID=2"), sr, "PAIRED_ID"),
            ("bad_pcm", sc.replace(b"32767", b"32768"), sr, "PCM16_RANGE"),
            ("bad_clip", sc.replace(b"CLIP=1", b"CLIP=2"), sr, "CAPTURE_SCHEMA"),
            ("truncated", b"", b"", "ROW_COUNT"),
            ("unknown_tail", sc, sr + b"UNKNOWN\n", "ROW_COUNT")]
        for label, cdata, rdata, diagnostic in cases:
            folder = negatives / label
            folder.mkdir()
            (folder / "cap").write_bytes(cdata)
            (folder / "req").write_bytes(rdata)
            b.dump(folder / "config", b.config_for(cdata, rdata, 1,
                                                   "SYNTHETIC_SOFTWARE_TEST"))
            run.call(label, bridge_command(sources / "bridge.py", folder / "cap",
                     folder / "req", folder / "config", folder / "export"), 1, diagnostic)
        for label, changes, diagnostic in [
                ("frozen_truncation_repin", {"expected_rows": 4096}, "FROZEN_ROW_COUNT"),
                ("frozen_bad_sha", {"capture_sha256": "0" * 64}, "FROZEN_INPUT_SHA"),
                ("physical_mapping", {"rate_mode": "physical_time"},
                 "PHYSICAL_TIME_MAPPING_BLOCKED")]:
            cfg = b.load_json(config.read_bytes())
            cfg.update(changes)
            path = negatives / (label + ".json")
            b.dump(path, cfg)
            run.call(label, bridge_command(sources / "bridge.py", cap, req, path,
                     out / (label + "_export")), 1, diagnostic)
        run.call("overwrite", bridge_command(sources / "bridge.py", cap, req, config,
                                              out / "export"), 1, "OUTPUT_EXISTS")
        after = {name: b.sha((HERE / name).read_bytes()) for name in source_names}
        b.require(before == after, "EXECUTION_SOURCE_CHANGED")
        b.require((EVIDENCE / "RAW_REVIEW.zip").read_bytes() == archive_raw,
                  "ORIGINAL_EVIDENCE_CHANGED")
        receipt = dict(status="NEW_BRIDGE_SOFTWARE_QUALIFICATION_PASS", exit_code=0,
                       validation_level="L0/L1 structure and exact WAV integer readback only",
                       elapsed_seconds=time.monotonic() - run.start, steps=run.steps,
                       execution_sources_before=before, execution_sources_after=after,
                       runtime_imports="Python standard library only; -I -S",
                       python_executable_sha256=b.sha(Path(sys.executable).read_bytes()),
                       source_capture_rows=4137, wav_samples=16548,
                       new_RTL_run=False, Gowin_run=False,
                       old_WAV_tests_run=False, old_mathematical_checker_run=False,
                       **b.FALSE_CLAIMS)
        b.dump(out / "qualification.json", receipt)
        seal(out)
    except Exception as error:
        b.dump(out / "failure.json", dict(status="FAIL", exit_code=1,
                                          error=str(error), steps=run.steps))
        raise


def seal(out):
    payload = {p.relative_to(out).as_posix(): p.read_bytes()
               for p in out.rglob("*") if p.is_file()}
    manifest = {name: dict(bytes=len(data), sha256=b.sha(data))
                for name, data in sorted(payload.items())}
    raw_manifest = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(payload.items()):
            archive.writestr(name, data)
        archive.writestr("MANIFEST.json", raw_manifest)
    raw = stream.getvalue()
    (out / "BRIDGE_EVIDENCE.zip").write_bytes(raw)
    b.dump(out / "seal.json", dict(schema="T052_BRIDGE_SEAL_1", zip_sha256=b.sha(raw),
                                   zip_bytes=len(raw), manifest_sha256=b.sha(raw_manifest),
                                   members=len(payload) + 1))


def verify(sealed, output):
    out = fresh(output)
    run = Bounded(out)
    try:
        raw = (sealed / "BRIDGE_EVIDENCE.zip").read_bytes() if (
            sealed / "BRIDGE_EVIDENCE.zip").exists() else base64.b64decode(
                (sealed / "BRIDGE_EVIDENCE.zip.b64").read_bytes(), validate=False)
        receipt = b.load_json((sealed / "seal.json").read_bytes())
        b.require(b.sha(raw) == receipt["zip_sha256"]
                  and len(raw) == receipt["zip_bytes"], "SEALED_ZIP_SHA")
        archive = zipfile.ZipFile(io.BytesIO(raw))
        names = archive.namelist()
        b.require(len(names) == len(set(names)) == receipt["members"], "SEALED_MEMBERS")
        manifest_raw = archive.read("MANIFEST.json")
        b.require(b.sha(manifest_raw) == receipt["manifest_sha256"], "SEALED_MANIFEST_SHA")
        manifest = b.load_json(manifest_raw)
        b.require(set(names) == set(manifest) | {"MANIFEST.json"}, "SEALED_MEMBER_SET")
        for name, identity in manifest.items():
            safe = PurePosixPath(name)
            b.require(not safe.is_absolute() and ".." not in safe.parts
                      and "\\" not in name and ":" not in name, "UNSAFE_MEMBER")
            data = archive.read(name)
            b.require(len(data) == identity["bytes"]
                      and b.sha(data) == identity["sha256"], "SEALED_MEMBER_SHA")
            path = out / "isolated" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        isolated = out / "isolated"
        run.call("isolated_export", bridge_command(isolated / "sources/bridge.py",
                 isolated / "export/original.capture", isolated / "export/original.requests",
                 isolated / "config.json", out / "reexport"))
        for name in ("lane0.wav", "lane1.wav", "lane2.wav", "lane3.wav",
                     "sample_mapping.jsonl", "receipt.json"):
            b.require((out / "reexport" / name).read_bytes()
                      == (isolated / "export" / name).read_bytes(), "ISOLATED_OUTPUT:" + name)
        b.dump(out / "verify.json", dict(status="ISOLATED_BUNDLE_VERIFY_PASS", exit_code=0,
                                         seal=receipt, steps=run.steps,
                                         working_tree_models_used=False,
                                         **b.FALSE_CLAIMS))
    except Exception as error:
        b.dump(out / "failure.json", dict(status="FAIL", exit_code=1,
                                          error=str(error), steps=run.steps))
        raise


def publish(sealed, verified, output):
    out = fresh(output)
    b.require(b.load_json((verified / "verify.json").read_bytes())["status"]
              == "ISOLATED_BUNDLE_VERIFY_PASS", "VERIFY_REQUIRED")
    raw = (sealed / "BRIDGE_EVIDENCE.zip").read_bytes()
    sealed_identity = b.load_json((sealed / "seal.json").read_bytes())
    verification = b.load_json((verified / "verify.json").read_bytes())
    b.require(verification["seal"] == sealed_identity
              and b.sha(raw) == sealed_identity["zip_sha256"], "VERIFY_SEAL_BINDING")
    target = DOC / "SEALED_20261012_01"
    target.mkdir(parents=True, exist_ok=False)
    encoded = base64.encodebytes(raw)
    (target / "BRIDGE_EVIDENCE.zip.b64").write_bytes(encoded)
    (target / "seal.json").write_bytes((sealed / "seal.json").read_bytes())
    (target / "verify.json").write_bytes((verified / "verify.json").read_bytes())
    b.dump(out / "publication.json", dict(status="SEALED_DOC_ARTIFACT_WRITTEN",
                                         seal=b.load_json((sealed / "seal.json").read_bytes()),
                                         target=str(target)))


def forward(gate, output):
    out = fresh(output)
    run = Bounded(out)
    for label, args in [("head", ["rev-parse", "HEAD"]),
                        ("tree", ["rev-parse", "HEAD^{tree}"]),
                        ("branch", ["branch", "--show-current"]),
                        ("status", ["status", "--short"]),
                        ("remote", ["ls-remote", "origin", "refs/heads/develop"])]:
        run.call(label, ["git", "-C", str(ROOT), *args])
    read = lambda label: (out / (label + ".stdout.bin")).read_text().strip()
    gated = b.load_json((gate / "receipt.json").read_bytes())
    b.require(read("branch") == "develop" and not read("status")
              and read("head") == read("remote").split()[0]
              and read("tree") == gated["tree"]
              and gated["status"] == "EXACT_INDEX_NINE_GATES_PASS", "PUBLICATION_NOT_VERIFIED")
    b.dump(out / "git_delivery.json", dict(status="GATED_DEVELOP_PUSH_VERIFIED",
                                           commit=read("head"), tree=read("tree"),
                                           gate=str(gate), steps=run.steps,
                                           private_notice="awaiting_user_forward_not_delivered"))
    paths = [p for folder in (HERE, DOC) for p in folder.rglob("*") if p.is_file()]
    payload = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in paths}
    sealed = DOC / "SEALED_20261012_01"
    payload["BRIDGE_EVIDENCE.zip"] = base64.b64decode(
        (sealed / "BRIDGE_EVIDENCE.zip.b64").read_bytes())
    for folder, prefix in [(gate, "publication_gate"), (out, "publication")]:
        for path in folder.iterdir():
            if path.is_file():
                payload[prefix + "/" + path.name] = path.read_bytes()
    manifest = {name: dict(bytes=len(data), sha256=b.sha(data))
                for name, data in payload.items()}
    path = out / "M3_T052_CAPTURE_BRIDGE_M2_20261012.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(payload.items()):
            archive.writestr(name, data)
        archive.writestr("FORWARD_MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
    with zipfile.ZipFile(path) as archive:
        b.require(archive.testzip() is None, "FORWARD_CRC")
        for name, identity in manifest.items():
            b.require(b.sha(archive.read(name)) == identity["sha256"], "FORWARD_MEMBER_SHA")
    b.dump(out / "forward_receipt.json", dict(status="FORWARD_ZIP_VERIFIED", file=str(path),
                                              sha256=b.sha(path.read_bytes()),
                                              bytes=path.stat().st_size, members=len(payload) + 1))
    print(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("qualify", "verify", "publish", "forward"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sealed", type=Path)
    parser.add_argument("--verified", type=Path)
    parser.add_argument("--gate", type=Path)
    args = parser.parse_args()
    if args.mode == "qualify":
        qualify(args.output)
    elif args.mode == "verify":
        verify(args.sealed, args.output)
    elif args.mode == "publish":
        publish(args.sealed, args.verified, args.output)
    else:
        forward(args.gate, args.output)


if __name__ == "__main__":
    main()
