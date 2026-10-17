"""Local identity and immutable JSON utilities for E4 only."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOC = ROOT / "code/docs/test/m3_n32_pro_candidate_20261017"
SOFT = Path(__file__).resolve().parent


def identity(path):
    p = Path(path).resolve()
    raw = p.read_bytes()
    return {"path":str(p),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}


def write_new(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("x",encoding="utf-8",newline="\n") as f:
        json.dump(value,f,ensure_ascii=False,indent=2)
        f.write("\n")
