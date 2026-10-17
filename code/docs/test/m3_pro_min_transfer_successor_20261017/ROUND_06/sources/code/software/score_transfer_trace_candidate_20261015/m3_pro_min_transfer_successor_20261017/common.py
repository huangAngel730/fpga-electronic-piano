"""E3 isolated paths and exact-byte identity utilities; never serial hardware."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TAG = "m3_pro_min_transfer_successor_20261017"
DOCS = ROOT / "code/docs/test" / TAG
TB = ROOT / "code/tb/input/score_transfer_candidate" / TAG / "tb_e3_file_uart.sv"
TOOL = Path("E:/FPGA/GAOYUNFPGA/138K/tools/icarus_oss_copy")
MIDI_DIR = ROOT / "code/software/score_midi_real_input_acceptance_20261015"
MIDI = MIDI_DIR / "inputs/MIDI_sample_2018-03-21.mid"
MIDI_SHA = "c0a8cb9f1ba3496a00367786a2b4ee5e0580be7b4bfbf0891b75e3b7475f634c"
OLD_PY = [ROOT / "code/software/score_midi_import_candidate_20261014/midi_import.py",
          ROOT / "code/software/score_transfer_v1/score_transfer.py",
          MIDI_DIR / "independent_oracle.py",
          ROOT / "code/software/score_midi_import_candidate_20261014/offline_readback.py",
          ROOT / "code/software/score_transfer_trace_candidate_20261015/score_trace_verify.py"]
ORIGINAL_RECEIVER = ROOT / "code/rtl/input/score_transfer_candidate/score_transfer_candidate.sv"
RTL = [ROOT / "code/rtl/common/uart_rx.sv", ROOT / "code/rtl/common/uart_tx.sv",
       ORIGINAL_RECEIVER.parent / TAG / "score_transfer_e3_successor.sv"]


def identity(path):
    raw = Path(path).read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def save(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sources():
    return [*sorted(HERE.glob("*.py")), TB, *OLD_PY, *RTL, ORIGINAL_RECEIVER, MIDI, MIDI_DIR / "SOURCE_RIGHTS.txt",
            ROOT / "code/docs/hardware/score_transfer_v1/PROTOCOL.md"]
