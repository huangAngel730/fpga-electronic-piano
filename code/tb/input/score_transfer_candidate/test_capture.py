"""Reject actual damaged RTL captures; never count simulation timeout as success."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from check_capture import crc


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture",type=Path); parser.add_argument("expected",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args(); args.output.mkdir(exist_ok=False)
    lines=args.capture.read_text(encoding="ascii").splitlines()
    tx_index=next(i for i,line in enumerate(lines) if line.startswith("TX "))
    rx_index=next(i for i,line in enumerate(lines) if line.startswith("RX "))
    meta_index=next(i for i,line in enumerate(lines) if line.startswith("META "))
    event_index=next(i for i,line in enumerate(lines) if line.startswith("EVENT "))
    idle_id=next(case["id"] for case in json.loads(args.expected.read_text())["cases"] if case["op"]=="I")
    timeout_index=next(i for i,line in enumerate(lines) if line.startswith(f"TX {idle_id} "))
    variants={"empty":[],"missing_start":lines[1:],"missing_end":lines[:-1],
              "truncated_end":lines[:-1]+["END"],"unknown_record":lines[:-1]+["UNKNOWN 1 0",lines[-1]],
              "missing_event":lines[:event_index]+lines[event_index+1:],
              "duplicate_event":lines[:event_index]+[lines[event_index]]+lines[event_index:],
              "missing_input":lines[:rx_index]+lines[rx_index+1:],
              "duplicate_reply":lines[:tx_index]+[lines[tx_index]]+lines[tx_index:],
              "missing_reply":lines[:tx_index]+lines[tx_index+1:],
              "missing_metadata":lines[:meta_index]+lines[meta_index+1:]}
    for label,idx,value in (("wrong_start_clock",0,"START 50000000 115200"),
                            ("wrong_end_count",len(lines)-1,"END 0 0"),
                            ("wrong_input",rx_index,lines[rx_index][:-2]+"ff"),
                            ("wrong_public_event",event_index,lines[event_index][:-1]+"f"),
                            ("zero_meta",meta_index,"META 1 1 0 0 0 0")):
        changed=lines.copy(); changed[idx]=value; variants[label]=changed
    changed=lines.copy(); parts=changed[timeout_index].split(); parts[-1]=str(int(parts[-1])-1000000)
    changed[timeout_index]=" ".join(parts); variants["shortened_timeout_timestamp"]=changed
    for label,offset,value in (("wrong_reply_crc",-1,1),("wrong_ack_command",3,0x81),
                               ("wrong_session",4,0xff),("wrong_sequence",6,0xff),
                               ("wrong_error",13,0xff),("wrong_score_id",18,0xff)):
        changed=lines.copy(); parts=changed[tx_index].split(); raw=bytearray.fromhex(parts[2])
        raw[offset]^=1  # always a real change, including an originally NACK first reply
        if label!="wrong_reply_crc": raw[-2:]=crc(raw[2:-2]).to_bytes(2,"little")
        parts[2]=raw.hex(); changed[tx_index]=" ".join(parts); variants[label]=changed
    results=[]
    for label,changed in variants.items():
        capture=args.output/(label+".txt"); capture.write_text("\n".join(changed)+"\n",encoding="ascii")
        result=subprocess.run([sys.executable,"-B","-X","utf8",Path(__file__).with_name("check_capture.py"),
                               capture,args.expected],capture_output=True)
        (args.output/(label+".stdout.bin")).write_bytes(result.stdout)
        (args.output/(label+".stderr.bin")).write_bytes(result.stderr)
        if result.returncode!=1 or b"FAIL " not in result.stdout:
            raise ValueError(f"{label}: damaged capture not rejected, exit={result.returncode}")
        results.append(dict(label=label,exit_code=result.returncode,reason=result.stdout.decode().strip()))
    (args.output/"receipt.json").write_text(json.dumps(results,indent=2)+"\n",encoding="utf-8")
    print(f"PASS damaged real-capture rejection {len(results)}/{len(results)}")


if __name__=="__main__":
    main()
