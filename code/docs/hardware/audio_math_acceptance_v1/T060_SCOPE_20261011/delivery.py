"""Verify sealed B scope evidence, then forward a separately gated normal push."""

import argparse
import base64
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

DOC = Path(__file__).resolve().parent
ROOT = DOC.parents[4]
SOFTWARE = ROOT / "code/software/audio_math_acceptance_candidate/t060_scope_20261011"
sys.path.insert(0, str(SOFTWARE))
import scope_bundle as scope  # noqa: E402


def verify(sealed, output):
    output = scope.fresh(output)
    manifest = scope.load((sealed / "seal.json").read_bytes())
    raw = base64.b64decode((sealed / "SCOPE_EVIDENCE.zip.b64").read_bytes())
    scope.require(scope.identity(raw) == manifest["zip"], "SCOPE_SEAL_SHA")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        scope.require(len(names) == len(set(names)) and set(names) == set(manifest["members"])
                      and archive.testzip() is None, "SCOPE_SEAL_MEMBERS_OR_CRC")
        for name in names:
            path = output / name
            scope.require(not Path(name).is_absolute() and "\\" not in name
                          and path.resolve().is_relative_to(output), "SCOPE_SEAL_PATH")
            data = archive.read(name)
            scope.require(scope.identity(data) == manifest["members"][name], "SCOPE_MEMBER_SHA:" + name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    bundle = output / "run/bundle"
    scope.require((bundle / "scope_bundle.py").read_bytes() == (SOFTWARE / "scope_bundle.py").read_bytes(),
                  "SCOPE_VERIFIER_SOURCE_IDENTITY")
    receipt = scope.load((output / "run/receipt.json").read_bytes())
    scope.require(receipt["exit_code"] == 0 and receipt["status"] == "NEW_B_SCOPE_QUALIFICATION_PASS"
                  and receipt["sources_before"] == receipt["sources_after"], "SCOPE_SOFTWARE_RECEIPT")
    for source in SOFTWARE.glob("*.py"):
        key = source.relative_to(ROOT).as_posix()
        scope.require(receipt["sources_after"][key] == scope.identity(source.read_bytes())
                      and (output / "run/sources" / source.name).read_bytes() == source.read_bytes(),
                      "SCOPE_EXECUTED_SOURCE_IDENTITY:" + source.name)
    result = subprocess.run([sys.executable, "-I", "-S", "-B", "-X", "utf8",
                             str(bundle / "scope_bundle.py"), "verify", "--bundle", str(bundle)],
                            cwd=output, capture_output=True, timeout=90)
    (output / "verify.stdout.txt").write_bytes(result.stdout)
    (output / "verify.stderr.txt").write_bytes(result.stderr)
    scope.require(result.returncode == 0, "SCOPE_ISOLATED_SEAL_VERIFY")
    result_json = scope.load(result.stdout)
    scope.require(result_json["status"] == "SCOPE_STRUCTURE_AND_IDENTITY_PASS_ONLY"
                  and result_json["t060_complete"] is False, "SCOPE_ISOLATED_VERIFY_RECEIPT")
    result = {"status": "B_SCOPE_SEAL_ISOLATED_VERIFIED", "exit_code": 0,
              "zip": manifest["zip"], "members": len(manifest["members"]),
              "stdout": scope.identity(result.stdout), "stderr": scope.identity(result.stderr),
              "t060_complete": False, "new_math_replays": 0}
    scope.dump(output / "verification.json", result)
    return result


def forward(sealed, gate, output):
    output = scope.fresh(output)
    verified = verify(sealed, output / "seal_verify")
    steps = []

    def git(label, *args):
        result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, timeout=60)
        (output / (label + ".stdout.txt")).write_bytes(result.stdout)
        (output / (label + ".stderr.txt")).write_bytes(result.stderr)
        steps.append({"label": label, "command": ["git", *args], "exit_code": result.returncode,
                      "stdout": scope.identity(result.stdout), "stderr": scope.identity(result.stderr)})
        scope.require(result.returncode == 0, "SCOPE_PUBLICATION_COMMAND:" + label)
        return result.stdout.decode().strip()

    head = git("head", "rev-parse", "HEAD")
    tree = git("tree", "rev-parse", "HEAD^{tree}")
    branch = git("branch", "branch", "--show-current")
    status = git("status", "status", "--short")
    remote = git("remote", "ls-remote", "origin", "refs/heads/develop").split()[0]
    gated = scope.load((gate / "receipt.json").read_bytes())
    scope.require(gated["status"] == "EXACT_INDEX_NINE_GATES_PASS" and gated["exit_code"] == 0
                  and gated["tree"] == tree and branch == "develop" and not status and head == remote,
                  "SCOPE_NOT_EXACT_GATED_CLEAN_REMOTE")
    receipt = {"status": "GATED_DEVELOP_PUSH_VERIFIED", "exit_code": 0, "commit": head,
               "tree": tree, "remote_develop": remote, "clean": True, "gate": str(gate),
               "seal_verification": verified, "steps": steps,
               "M2_notification": "pending_user_forward_not_delivered", "t060_complete": False}
    scope.dump(output / "GIT_DELIVERY.json", receipt)
    members = {p.relative_to(ROOT).as_posix(): p.read_bytes()
               for base in (DOC, SOFTWARE) for p in base.rglob("*") if p.is_file()}
    for p in gate.iterdir():
        if p.is_file():
            members["release_gate/" + p.name] = p.read_bytes()
    for p in output.rglob("*"):
        if p.is_file():
            members["publication/" + p.relative_to(output).as_posix()] = p.read_bytes()
    members["FORWARD_MANIFEST.json"] = json.dumps({n: scope.identity(d) for n, d in sorted(
        members.items())}, indent=2).encode("utf-8") + b"\n"
    target = output / "M3_T060_SCOPE_B_REFUSALS_M2_20261012.zip"
    with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(members.items()):
            archive.writestr(name, raw)
    with zipfile.ZipFile(target) as archive:
        scope.require(archive.testzip() is None, "SCOPE_FORWARD_CRC")
        for name, raw in members.items():
            scope.require(archive.read(name) == raw, "SCOPE_FORWARD_MEMBER:" + name)
    result = {"status": "B_SCOPE_FORWARD_VERIFIED", "exit_code": 0, "commit": head,
              "file": str(target), "members": len(members), **scope.identity(target.read_bytes())}
    scope.dump(output / "forward_receipt.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("verify", "forward"))
    parser.add_argument("--sealed", type=Path, default=DOC / "SEALED_20261012_01")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gate", type=Path)
    args = parser.parse_args()
    result = verify(args.sealed.resolve(), args.output) if args.mode == "verify" else forward(
        args.sealed.resolve(), args.gate.resolve(), args.output)
    print(json.dumps(result))
