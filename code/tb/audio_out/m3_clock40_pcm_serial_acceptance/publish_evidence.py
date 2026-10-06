"""Lossless original-log delivery across Git LF normalization (no ZIP)."""
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
    if not run.is_relative_to(HERE / "runtime"):
        raise ValueError("RUN_OUTSIDE_AUTHORIZED_TEST")
    receipt = json.loads((run / "receipt.json").read_text(encoding="utf-8"))
    if not receipt["passed"] or not receipt["repository_gate"]["passed"]:
        raise ValueError("UNPASSED_RECEIPT")
    target = HERE / "evidence"
    target.mkdir(exist_ok=False)
    members = {}

    def encode(source, name, expected):
        data = source.read_bytes()
        if sha(data) != expected:
            raise ValueError("RAW_SHA "+name)
        encoded = base64.b64encode(data).decode("ascii")
        destination = target / (name+".b64")
        destination.write_text("\n".join(encoded[i:i+76] for i in range(0, len(encoded), 76))+"\n",
                               encoding="ascii", newline="\n")
        if base64.b64decode(b"".join(destination.read_bytes().split()), validate=True) != data:
            raise ValueError("BASE64_ROUNDTRIP")
        members[destination.name] = {"raw_sha256": expected, "raw_bytes": len(data)}
    for name in ["receipt.json", "source_manifest.json"]:
        # Metadata is LF text; ORIGINAL artifact SHA values inside stay exact.
        text = (run/name).read_text(encoding="utf-8")
        (target/name).write_text(text, encoding="utf-8", newline="\n")
    for case in ["normal", "diagnostic", "wrong_bit", "wrong_buffer"]:
        for phase in ["compile", "simulate"]:
            name = case+"_"+phase
            if receipt["runs"][name]["exit_code"]:
                raise ValueError("TOOL_NOT_SUCCESSFUL "+name)
            encode(run/(name+".log"), name, receipt["runs"][name]["log_sha256"])
        encode(run/case/"capture.txt", case+"_capture",
               receipt["runs"][case+"_simulate"]["capture_sha256"])
    for name in ["check_repo", "version"]:
        encode(run/(name+".log"), name, receipt["runs"][name]["log_sha256"])
    for case, source in [("wrong_bit", "i2s_tx.sv"), ("wrong_buffer", "pcm_frame_buffer.sv")]:
        encode(run/case/source, case+"_source", receipt["mutations"][case]["mutant_sha256"])
    (target/"raw_manifest.json").write_text(json.dumps(members, indent=2)+"\n", encoding="utf-8", newline="\n")
    print(f"PASS {len(members)} raw artifacts: original SHA + Base64 roundtrip")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--run", type=Path)
    cli.add_argument("--decode", type=Path)
    args = cli.parse_args()
    if args.decode:
        data = base64.b64decode(b"".join(args.decode.read_bytes().split()), validate=True)
        sys.stdout.buffer.write(data)
    elif args.run:
        publish(args.run)
    else:
        cli.error("specify --run or --decode")
