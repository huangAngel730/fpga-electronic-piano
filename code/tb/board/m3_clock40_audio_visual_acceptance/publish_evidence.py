"""Publish exact raw artifacts as Git-safe Base64; never overwrite evidence."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def publish(run):
    run = run.resolve()
    if not run.is_relative_to(HERE/"runtime"):
        raise ValueError("RUN_OUTSIDE_AUTHORIZED_TEST")
    receipt = json.loads((run/"receipt.json").read_text(encoding="utf-8"))
    if not receipt["passed"] or receipt["partial"] or not receipt["repository_gate"]["passed"]:
        raise ValueError("UNPASSED_RECEIPT")
    target = HERE/"evidence"
    target.mkdir(exist_ok=False)
    members = {}

    def encode(source, name, expected):
        data = source.read_bytes()
        if sha(data) != expected:
            raise ValueError("RAW_SHA "+name)
        encoded = base64.b64encode(data).decode("ascii")
        dest = target/(name+".b64")
        dest.write_text("\n".join(encoded[i:i+76] for i in range(0, len(encoded), 76))+"\n", encoding="ascii", newline="\n")
        if base64.b64decode(b"".join(dest.read_bytes().split()), validate=True) != data:
            raise ValueError("BASE64_ROUNDTRIP")
        members[dest.name] = {"raw_sha256": expected, "raw_bytes": len(data)}

    for name in ["receipt.json", "source_manifest.json"]:
        (target/name).write_text((run/name).read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    for case in ["normal", "overflow", "wrong_note", "wrong_audio"]:
        for phase in ["compile", "simulate"]:
            name = case+"_"+phase
            if receipt["runs"][name]["exit_code"]:
                raise ValueError("TOOL_NOT_SUCCESSFUL "+name)
            encode(run/(name+".log"), name, receipt["runs"][name]["log_sha256"])
        encode(run/case/"capture.txt", case+"_capture", receipt["runs"][case+"_simulate"]["capture_sha256"])
    for name in ["check_repo", "version"]:
        encode(run/(name+".log"), name, receipt["runs"][name]["log_sha256"])
    for case, info in receipt["mutations"].items():
        encode(run/case/"tb_joint.sv", case+"_source", info["source_sha256"])
    dump = json.dumps(members, indent=2)+"\n"
    (target/"raw_manifest.json").write_text(dump, encoding="utf-8", newline="\n")
    print(f"PASS {len(members)} original raw SHA and Base64 roundtrips")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--decode", type=Path)
    args = parser.parse_args()
    if args.decode:
        sys.stdout.buffer.write(base64.b64decode(b"".join(args.decode.read_bytes().split()), validate=True))
    elif args.run:
        publish(args.run)
    else:
        parser.error("specify --run or --decode")
