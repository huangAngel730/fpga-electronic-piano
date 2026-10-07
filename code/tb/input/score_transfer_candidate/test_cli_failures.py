"""Execute the actual PC CLI on malformed inputs and missing physical-port approval."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from vectors import score


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output",type=Path)
    args=parser.parse_args(); args.output.mkdir(exist_ok=False)
    root=Path(__file__).resolve().parents[4]
    cli=root/"code/software/score_transfer_v1/score_transfer.py"
    inputs={"empty_file":"","truncated_json":'{"schema":1,',
            "empty_score":json.dumps(dict(schema=1,sample_hz=48000,score_id=1,events=[])),
            "over_capacity":json.dumps(score(1,513)),
            "unknown_field":json.dumps(dict(score(1,2),unsupported=1)),
            "duplicate_field":'{"schema":1,"schema":1}',
            "missing_port_authority":json.dumps(score(1,2))}
    receipt=[]
    for label,text in inputs.items():
        source=args.output/(label+".json"); source.write_text(text,encoding="utf-8")
        cmd=[sys.executable,"-B","-X","utf8",str(cli),
             "upload" if label=="missing_port_authority" else "encode",
             "--score",str(source),"--output",str(args.output/(label+"_result"))]
        result=subprocess.run(cmd,capture_output=True)
        (args.output/(label+".stdout.bin")).write_bytes(result.stdout)
        (args.output/(label+".stderr.bin")).write_bytes(result.stderr)
        if result.returncode not in (1,2) or (args.output/(label+"_result")).exists():
            raise ValueError(f"{label}: CLI failed to reject before output/serial open")
        receipt.append(dict(label=label,command=cmd,exit_code=result.returncode,
                            input_sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
    (args.output/"receipt.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    print(f"PASS actual PC CLI invalid-input/port-guard rejection {len(receipt)}/{len(receipt)}; no serial opened")


if __name__=="__main__":
    main()
