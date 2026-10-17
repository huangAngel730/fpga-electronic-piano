"""Build and validate read-only reset-edge records on the public time axis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "M3_R08_RESET_EDGES_V1"


class ResetReject(ValueError):
    pass


def record_edges(samples: list[dict[str, Any]]) -> dict[str, Any]:
    prior_time = -1
    prior_reset = None
    epoch = -1
    awaiting_release = False
    edges = []
    for index, sample in enumerate(samples):
        if set(sample) != {"time_ps", "core_posedge", "rst_n", "pll_locked",
                           "source_line"}:
            raise ResetReject(f"SAMPLE_SHAPE_{index}")
        now = sample["time_ps"]
        if type(now) is not int or now < 0 or now <= prior_time:
            raise ResetReject(f"TIME_ORDER_{index}")
        if type(sample["source_line"]) is not int or sample["source_line"] < 1:
            raise ResetReject(f"SOURCE_LINE_{index}")
        if type(sample["core_posedge"]) is not bool:
            raise ResetReject(f"CORE_POSEDGE_VALUE_{index}")
        if type(sample["rst_n"]) is not int or sample["rst_n"] not in {0, 1}:
            raise ResetReject(f"RESET_VALUE_{index}")
        if (sample["pll_locked"] is not None
                and (type(sample["pll_locked"]) is not int
                     or sample["pll_locked"] not in {0, 1})):
            raise ResetReject(f"PLL_LOCKED_VALUE_{index}")
        if prior_reset != 0 and sample["rst_n"] == 0:
            epoch += 1
            awaiting_release = True
            edges.append({"kind": "ASYNC_ASSERT", "epoch": epoch,
                          "time_ps": now, "source_line": sample["source_line"],
                          "clock_aligned": bool(sample["core_posedge"])})
        if awaiting_release and sample["core_posedge"] and sample["rst_n"] == 1:
            lock = sample["pll_locked"]
            if lock == 1:
                edges.append({"kind": "SYNC_RELEASE_PRE_NBA", "epoch": epoch,
                              "time_ps": now,
                              "source_line": sample["source_line"],
                              "pll_locked": lock,
                              "release_source": "PUBLIC_PLL_LOCKED"})
                edges.append({"kind": "FIRST_FUNCTIONAL_PRE_NBA",
                              "epoch": epoch, "time_ps": now,
                              "source_line": sample["source_line"]})
                awaiting_release = False
            else:
                edges.append({"kind": "SYNC_RELEASE_PENDING_AUTHORITY",
                              "epoch": epoch, "time_ps": now,
                              "source_line": sample["source_line"],
                              "pll_locked": lock,
                              "release_source": "UNKNOWN_LOCK_SOURCE"})
        prior_reset = sample["rst_n"]
        prior_time = now
    has_unknown_lock = any(edge["kind"] == "SYNC_RELEASE_PENDING_AUTHORITY"
                           for edge in edges)
    status = ("PENDING_LOCK_AUTHORITY" if awaiting_release and has_unknown_lock
              else "PENDING_RELEASE" if awaiting_release else "COMPLETE")
    if not edges:
        status = "PENDING_NO_ASSERTION"
    return {"schema": SCHEMA, "status": status, "edges": edges,
            "constant_epoch_fabricated": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    samples = json.loads(args.input.read_text(encoding="utf-8"))
    report = record_edges(samples)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
