"""B2 read-only dependencies; no duplicated D3 or pin decoder implementation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TAG = "pro_serial_successor_20261017"
DOCS = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016" / TAG
OLD = ROOT / "code/software/m3_pro_fourvoice_trace_20261016/D"
D3 = OLD / "ingest/ingest.py"
LEGACY = ROOT / "code/software/m3_40mhz_pcm_i2s_latency_20261015/night_20261016/RESUME_R02/consume_capture.py"
LEGACY_SHA = "da91462e8421719e09ffab60d7bbe38d4ee05ac1793ea70e1f09c7a69ccda0cb"
MONITOR = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017"


def identity(path):
    path = Path(path)
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def save(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    item = importlib.util.module_from_spec(spec)
    sys.modules[name] = item
    spec.loader.exec_module(item)
    return item


def decoder():
    # Reuse D3's existing fixed-byte dependency gate, not its incompatible
    # event-calendar intake. No call to legacy.analyze or old self-tests.
    d3 = module("b2_existing_d3_dependency_gate", D3)
    return d3.decoder()


def sources():
    return [*sorted(HERE.glob("*.py")), D3, LEGACY, OLD / "fixture.py",
            ROOT / "code/tb/board/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017/pro_frame_monitor.sv",
            MONITOR / "CONTRACT.md"]
