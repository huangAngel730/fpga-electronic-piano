"""Gate the exact staged tree, then export a verified ordinary develop push.

Does not stage, commit, fetch, push, change RTL, or run EDA. Existing repository
checks include the mandatory short T007/T019 simulations.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

import evidence as tool
import qualify


ROOT = tool.ROOT
DOC = qualify.DOC


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("gate", "finalize"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gate", type=Path)
    args = parser.parse_args()
    out = qualify.fresh_output(args.output)
    steps = []

    def command(label, argv, cwd=ROOT, env=None, timeout=600):
        begin = time.monotonic()
        try:
            result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=timeout)
            stdout, stderr, code, timed_out = result.stdout, result.stderr, result.returncode, False
        except subprocess.TimeoutExpired as error:
            stdout, stderr, code, timed_out = error.stdout or b"", error.stderr or b"", -1, True
        (out / (label + ".stdout.txt")).write_bytes(stdout)
        (out / (label + ".stderr.txt")).write_bytes(stderr)
        steps.append(dict(label=label, command=argv, cwd=str(cwd), exit_code=code,
                          timed_out=timed_out, elapsed_seconds=time.monotonic() - begin,
                          stdout_sha256=tool.sha(stdout), stderr_sha256=tool.sha(stderr)))
        tool.dump(out / "progress.json", steps)
        print(label + ": exit " + str(code), flush=True)
        if code or timed_out:
            raise ValueError("COMMAND_FAILED:" + label)
        return stdout

    try:
        if args.mode == "gate":
            tree = command("index_tree", ["git", "write-tree"]).decode().strip()
            snapshot = out / "snapshot"
            snapshot.mkdir()
            command("index_export", ["git", "-c", "core.longpaths=true", "checkout-index",
                                      "--all", "--prefix", str(snapshot) + "/"])
            index = command("index_path", ["git", "rev-parse", "--git-path", "index"]).decode().strip()
            env = os.environ.copy()
            env.update(GIT_DIR=str(ROOT / ".git"), GIT_WORK_TREE=str(snapshot),
                       GIT_INDEX_FILE=str((ROOT / index).resolve()), PYTHONUTF8="1",
                       PYTHONDONTWRITEBYTECODE="1", GIT_CONFIG_COUNT="1",
                       GIT_CONFIG_KEY_0="core.longpaths", GIT_CONFIG_VALUE_0="true")
            env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env["PATH"]
            raw = command("repo_gates", [shutil.which("pwsh") or shutil.which("powershell"),
                "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(snapshot / "code/scripts/check_repo.ps1")], cwd=snapshot, env=env)
            if raw.count(b"[PASS]") != 9 or b"All repository checks passed." not in raw:
                raise ValueError("NOT_NINE_REAL_GATES")
            after = command("index_after", ["git", "write-tree"]).decode().strip()
            if tree != after:
                raise ValueError("INDEX_CHANGED_DURING_GATE")
            tool.dump(out / "receipt.json", dict(status="EXACT_INDEX_NINE_GATES_PASS",
                      exit_code=0, tree=tree, steps=steps, EDA_run=False,
                      new_audio_RTL_run=False, mandatory_repo_RTL_gates=True))
            print("EXACT_INDEX_NINE_GATES_PASS:" + tree)
            return
        gate = args.gate.resolve()
        gate.relative_to(ROOT / "code/output")
        gated = tool.load_json((gate / "receipt.json").read_bytes())
        head = command("head", ["git", "rev-parse", "HEAD"]).decode().strip()
        tree = command("tree", ["git", "rev-parse", "HEAD^{tree}"]).decode().strip()
        branch = command("branch", ["git", "branch", "--show-current"]).decode().strip()
        remote = command("remote", ["git", "ls-remote", "origin", "refs/heads/develop"],
                         timeout=60).decode().split()[0]
        status = command("status", ["git", "status", "--short"]).decode().strip()
        if (gated["status"] != "EXACT_INDEX_NINE_GATES_PASS" or gated["tree"] != tree
                or head != remote or branch != "develop" or status):
            raise ValueError("NOT_EXACT_CLEAN_GATED_REMOTE")
        verified = qualify.verify(DOC / "EVIDENCE_20261011")
        receipt = dict(status="GATED_DEVELOP_PUSH_VERIFIED", exit_code=0, commit=head,
                       remote_develop=remote, tree=tree, branch=branch, clean=True,
                       gate=str(gate), package=verified, steps=steps,
                       M1_private_notice="awaiting_user_forward_not_delivered",
                       M2_private_notice="awaiting_user_forward_not_delivered")
        tool.dump(out / "git_delivery.json", receipt)
        paths = list(DOC.rglob("*")) + qualify.sources()
        paths += [p for p in gate.glob("*") if p.is_file()]
        paths += [p for p in out.glob("*") if p.is_file()]
        payload = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in paths if p.is_file()}
        manifest = {name: dict(bytes=len(data), sha256=tool.sha(data))
                    for name, data in payload.items()}
        archive_path = out / "M3_T052_WAV_M2_HANDOFF_20261011.zip"
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(payload.items()):
                archive.writestr(name, data)
            archive.writestr("FORWARD_MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
        with zipfile.ZipFile(archive_path) as archive:
            if archive.testzip():
                raise ValueError("FORWARD_CRC")
            for name, item in manifest.items():
                if tool.sha(archive.read(name)) != item["sha256"]:
                    raise ValueError("FORWARD_MEMBER_SHA")
        tool.dump(out / "forward_receipt.json", dict(status="FORWARD_ZIP_VERIFIED", exit_code=0,
                  file=str(archive_path), sha256=tool.sha(archive_path.read_bytes()),
                  bytes=archive_path.stat().st_size, commit=head, members=len(payload) + 1))
        print(json.dumps(receipt))
    except Exception as error:
        tool.dump(out / "failure.json", dict(status="FAIL", exit_code=1,
                                             error=str(error), steps=steps))
        raise


if __name__ == "__main__":
    main()
