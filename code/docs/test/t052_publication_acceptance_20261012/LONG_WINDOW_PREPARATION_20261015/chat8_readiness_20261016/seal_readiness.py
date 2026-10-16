"""Seal only this new preflight and immutable R02 reference; no Git/HDL."""
import ast
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
SRC = ROOT / "code/software/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015/chat8_readiness_20261016"


def ident(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return {"bytes": path.stat().st_size, "sha256": h.hexdigest()}


def main():
    output = HERE / "T052_CHAT8_READINESS.zip"
    files = {}
    syntax = []
    for path in [*SRC.glob("*.py"), *HERE.glob("*.py")]:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        syntax.append({"path": str(path.relative_to(ROOT)), **ident(path)})
    syntax_receipt = HERE / "PYTHON_SYNTAX.json"
    with syntax_receipt.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump({"status": "AST_SYNTAX_PASS", "files": syntax,
                   "HDL_compiles": 0, "not_repo_gate": True}, stream, indent=2)
        stream.write("\n")
    for directory in (SRC, HERE):
        for path in directory.rglob("*"):
            if path.is_file() and path != output and path.suffix != ".zip":
                files[path.relative_to(ROOT).as_posix()] = path
            elif path.is_file() and path.name == "source_before.zip":
                files[path.relative_to(ROOT).as_posix()] = path
    readonly = HERE.parent / "T052_LONG_RUNNER_R02.zip"
    if ident(readonly)["sha256"] != "3776ea3d85f09099e7b33f5705d79300c4475697b5a0f1cfaed3dcfd603d54ee":
        raise ValueError("PINNED_R02_CHANGED")
    files["readonly_reference/T052_LONG_RUNNER_R02.zip"] = readonly
    decision = ROOT / "code/docs/M3_T052长窗R02补件_M2限定复核与执行决定_2026-10-16.md"
    files["readonly_reference/M2_T052_R02_DECISION.md"] = decision
    before = {name: ident(path) for name, path in sorted(files.items())}
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(files.items()):
            archive.write(path, name)
        archive.writestr("MANIFEST.json", json.dumps({
            "schema": "T052_CHAT8_READINESS_SOFTWARE_ONLY", "approved": False,
            "validation": "L0", "remaining": "WRITE_PROBE_SCOPE_NOT_GRANTED",
            "real_T052_compile_run_check": 0, "Git_writes": 0,
            "members": before}, indent=2) + "\n")
    if before != {name: ident(path) for name, path in sorted(files.items())}:
        raise ValueError("SEAL_INPUT_DRIFT")
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():
            raise ValueError("ZIP_CRC")
        for name, expected in before.items():
            raw = archive.read(name)
            if {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} != expected:
                raise ValueError("ZIP_MEMBER_SHA:" + name)
    receipt = {"status": "SEAL_PASS_EXECUTION_PARTIAL", "members": len(before)+1,
               "package": ident(output), "execution_authorized": False,
               "remaining": "WRITE_PROBE_SCOPE_NOT_GRANTED"}
    with (HERE / "SEAL_RECEIPT.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    print(json.dumps(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
