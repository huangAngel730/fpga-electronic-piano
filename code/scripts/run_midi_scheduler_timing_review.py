"""Reuse the existing parser miter for the E contract's frozen base and burst16.

No RTL change, new latency, synthesis, or timing-closure claim. The existing
selector oracle and behavioral mutants are reused rather than duplicated.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    specification = importlib.util.spec_from_file_location(
        "m3_existing_equivalence", ROOT / "code/scripts/run_midi_scheduler_equivalence.py")
    existing = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(existing)
    original = ROOT / existing.TB
    bench = original.read_text(encoding="utf-8")
    anchor = "localparam integer BURST = (lane == 0) ? 1 : ((lane == 3) ? 3 : 8);"
    if bench.count(anchor) != 1:
        raise ValueError("existing miter configuration changed; review before reuse")
    output_root = ROOT / "code/output"
    output_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="m3_timing_tb_", dir=output_root) as temporary:
        generated = Path(temporary) / "tb_midi_scheduler_equivalence.sv"
        generated.write_text(bench.replace(anchor, anchor.replace("? 3 : 8", "? 16 : 8"), 1),
                             encoding="utf-8", newline="\n")
        existing.BASELINE = "3ad0650"
        existing.TB = generated.relative_to(ROOT).as_posix()
        return existing.main()


if __name__ == "__main__":
    raise SystemExit(main())
