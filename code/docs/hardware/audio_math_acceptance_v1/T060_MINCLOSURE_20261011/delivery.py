"""Record new scope software checks, seal receipts, forward an exact gated push.

No math replay, original RTL workflow, EDA, Git mutation or device operation.
"""

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[5]
DOC = Path(__file__).resolve().parent
B2M = ROOT / "code/docs/hardware/polyphony_scaling_v1/B2M_CLOSURE_20261012"
SOFTWARE = ROOT / "code/software/audio_math_acceptance_candidate/t060_minclosure_20261011"
SOURCE_PATHS = [SOFTWARE / "scope.py", SOFTWARE / "test_scope.py", DOC / "README.md",
                Path(__file__).resolve()]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def info(raw):
    return dict(bytes=len(raw), sha256=sha(raw))


def require(value, reason):
    if not value:
        raise ValueError(reason)


def dump(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def fresh(path):
    path = path.resolve()
    require(path != ROOT / "code/output" and path.is_relative_to(ROOT / "code/output"),
            "DELIVERY_OUTPUT_SCOPE")
    path.mkdir(parents=True, exist_ok=False)
    return path


def verify_seal():
    carrier = (DOC / "software_execution.zip.b64").read_bytes()
    manifest = json.loads((DOC / "software_manifest.json").read_text(encoding="utf-8"))
    raw = base64.b64decode(carrier, validate=True)
    require(sha(raw) == manifest["zip_sha256"] and sha(carrier) == manifest["carrier_sha256"],
            "DELIVERY_SEAL_SHA")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(archive.testzip() is None and set(archive.namelist()) == set(manifest["members"]),
                "DELIVERY_SEAL_MEMBERS")
        for name, item in manifest["members"].items():
            require(info(archive.read(name)) == item, "DELIVERY_SEAL_MEMBER_SHA")
    return manifest


def prepare(args):
    args.b2m_verify = args.b2m_verify.resolve()
    out = fresh(args.output)
    require(not (DOC / "software_execution.zip.b64").exists()
            and not (DOC / "software_manifest.json").exists(), "DELIVERY_REFUSE_OVERWRITE")
    start, steps = time.monotonic(), []
    before = {p.relative_to(ROOT).as_posix(): info(p.read_bytes()) for p in SOURCE_PATHS}
    for label, argv in (
        ("scope", [sys.executable, "-B", "-X", "utf8", str(SOFTWARE / "scope.py"),
                   "--output", str(out / "scope_run")]),
        ("scope_units5", [sys.executable, "-B", "-X", "utf8", str(SOFTWARE / "test_scope.py"), "-v"])):
        timeout = min(90, 300 - (time.monotonic() - start))
        require(timeout > 0, "DELIVERY_TOTAL_TIMEOUT")
        begin = time.monotonic()
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=timeout)
        for suffix, raw in (("stdout", result.stdout), ("stderr", result.stderr)):
            (out / (label + "." + suffix + ".bin")).write_bytes(raw)
        step = dict(label=label, command=argv, exit_code=result.returncode,
                    elapsed_seconds=time.monotonic() - begin, timeout_seconds=timeout,
                    stdout=info(result.stdout), stderr=info(result.stderr))
        dump(out / (label + ".execution.json"), step)
        steps.append(step)
        require(result.returncode == 0, "DELIVERY_STEP:" + label)
    after = {p.relative_to(ROOT).as_posix(): info(p.read_bytes()) for p in SOURCE_PATHS}
    require(before == after, "DELIVERY_SOURCE_DRIFT")
    verified = json.loads((args.b2m_verify / "receipt.json").read_text(encoding="utf-8"))
    b2m_manifest = json.loads((B2M / "manifest.json").read_text(encoding="utf-8"))
    require(verified["status"] == "B2M_CLOSURE_ISOLATED_PACKAGE_VERIFIED"
            and verified["exit_code"] == 0 and verified["new_math_replays"] == 0
            and verified["zip_sha256"] == b2m_manifest["zip_sha256"]
            and len(verified["imported"]) == 9, "DELIVERY_B2M_VERIFY")
    scope = json.loads((out / "scope_run/scope.json").read_text(encoding="utf-8"))
    report = dict(status="B2M_CLOSURE_AND_T060_SCOPE_SOFTWARE_ONLY", exit_code=0,
        steps=steps, sources_before=before, sources_after=after, t060_complete=False,
        t061_complete=False, new_math_replays=0, new_audio_RTL=False, new_EDA=False,
        elapsed_seconds=time.monotonic() - start, total_limit_seconds=300,
        b2m_verify_sha256=sha((args.b2m_verify / "receipt.json").read_bytes()),
        remaining="T060 thin TB/observer/source-calendar oracle static preparation, then M2 precheck")
    dump(out / "receipt.json", report)
    paths = [p for p in out.rglob("*") if p.is_file()] + SOURCE_PATHS
    paths += [ROOT / p for p in scope["reused_sources"]]
    paths += [p for p in args.b2m_verify.iterdir() if p.is_file()]
    payload = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in paths}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(payload.items()):
            archive.writestr(name, raw)
    raw = buffer.getvalue()
    carrier = base64.b64encode(raw)
    (DOC / "software_execution.zip.b64").write_bytes(carrier)
    dump(DOC / "software_manifest.json", dict(status=report["status"],
         zip_sha256=sha(raw), carrier_sha256=sha(carrier),
         members={n: info(d) for n, d in payload.items()},
         committed_at_seal=False, pushed_at_seal=False,
         t060_complete=False, t061_complete=False))
    manifest = verify_seal()
    print(json.dumps(dict(exit_code=0, members=len(payload), zip_sha256=manifest["zip_sha256"])))


def forward(args):
    args.gate = args.gate.resolve()
    out = fresh(args.output)
    manifest = verify_seal()
    def git(*argv):
        return subprocess.check_output(["git", *argv], cwd=ROOT, timeout=60).decode().strip()
    head, tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
    remote = git("ls-remote", "origin", "refs/heads/develop").split()[0]
    gate = json.loads((args.gate / "receipt.json").read_text(encoding="utf-8"))
    require(gate["status"] == "EXACT_INDEX_NINE_GATES_PASS" and gate["tree"] == tree
            and gate["exit_code"] == 0 and head == remote
            and git("branch", "--show-current") == "develop" and not git("status", "--short"),
            "DELIVERY_NOT_CLEAN_EXACT_GATED_PUSH")
    receipt = dict(status="GATED_DEVELOP_PUSH_VERIFIED", commit=head, tree=tree,
        remote_develop=remote, exit_code=0, t060_complete=False, t061_complete=False,
        M2_notice="待用户转发，尚未送达", gate_tree=gate["tree"],
        scope_package_sha256=manifest["zip_sha256"])
    dump(out / "GIT_DELIVERY.json", receipt)
    paths = [p for p in DOC.iterdir() if p.is_file()]
    paths += [p for p in B2M.iterdir() if p.is_file()]
    paths += SOURCE_PATHS
    paths += [ROOT / "code/software/polyphony_scaling_candidate" / n for n in (
        "b2m_closure.py", "b2m_run.py", "test_b2m_closure.py")]
    paths += [ROOT / "code/docs/hardware/polyphony_scaling_v1" / n for n in (
        "deliver_b2m.py", "B2M_CLOSURE_REPAIR_20261012.md")]
    payload = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in paths}
    for p in args.gate.iterdir():
        if p.is_file():
            payload["release_gate/" + p.name] = p.read_bytes()
    payload["GIT_DELIVERY.json"] = (out / "GIT_DELIVERY.json").read_bytes()
    index = {n: info(d) for n, d in payload.items()}
    target = out / "M3_B2M_CLOSURE_T060_SCOPE_M2_20261012.zip"
    with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(payload.items()):
            archive.writestr(name, raw)
        archive.writestr("FORWARD_MANIFEST.json", json.dumps(index, indent=2) + "\n")
    with zipfile.ZipFile(target) as archive:
        require(archive.testzip() is None, "DELIVERY_FORWARD_CRC")
        for name, item in index.items():
            require(info(archive.read(name)) == item, "DELIVERY_FORWARD_MEMBER")
    result = dict(receipt, file=str(target), **info(target.read_bytes()), members=len(index) + 1)
    dump(out / "forward_receipt.json", result)
    print(json.dumps(result, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "forward"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--b2m-verify", type=Path)
    parser.add_argument("--gate", type=Path)
    args = parser.parse_args()
    prepare(args) if args.mode == "prepare" else forward(args)


if __name__ == "__main__":
    main()
