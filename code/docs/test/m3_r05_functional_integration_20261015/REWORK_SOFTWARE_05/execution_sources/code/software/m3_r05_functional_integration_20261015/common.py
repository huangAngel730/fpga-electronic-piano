"""Task-local immutable identity and strict JSON helpers."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DOCS = ROOT / "code/docs/test/m3_r05_functional_integration_20261015"
TB_DIR = ROOT / "code/tb/board/m3_r05_functional_integration_20261015"
R05 = ROOT / "code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1TD_R05_XSAFE_ModelSim输入_20261015.zip"
R05_SHA = "dcf15f5d3ded1a0b160f55eab43066c728f80b3c329c44ea9f099c63f178696a"
TB_SHA = "6e677154d0a53ff97e794555ef57695e385a9963de43f1ac9135a54c32fc9777"
PHYSICAL = ROOT / "code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1TD_整机PnR_STA_20261015.zip"
PHYSICAL_SHA = "17e71ebd5b54743fd0214af5fbfdfd1a4cca4eddbcedab56f7b3df7b3ca521ff"
AUTH = ROOT / "code/docs/M3_四项并行主责授权_2026-10-15.md"
PASS_MARKER = "PASS M2_M1TD_REAL_CHAIN_BOARD_FUNCTIONAL_ONLY"


class Refusal(ValueError):
    def __init__(self, code, detail):
        self.code = code
        super().__init__(detail)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(path):
    path = Path(path)
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": sha(data)}


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def write_new(path, value):
    with Path(path).open("xb") as stream:
        stream.write(json_bytes(value))


def json_load(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Refusal("DUPLICATE_KEY", key)
            result[key] = value
        return result
    return json.loads(data.decode("utf-8"), object_pairs_hook=pairs)


def snapshot_sources():
    result = {}
    for base in (HERE, TB_DIR):
        if base.exists():
            for p in base.iterdir():
                if p.is_file() and p.suffix in (".py", ".sv", ".md"):
                    result[p.relative_to(ROOT).as_posix()] = identity(p)
    return result
