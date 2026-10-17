"""File-based independent FRAME_PLAN generator candidate.

L0 / NOT_RUN: this file was authored after the R6-5 execution budget was
exhausted.  It must not be imported or executed until M2 grants a new,
explicit incremental admission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


INPUT_SCHEMA = "M3_R06_FRAME_PLAN_GENERATOR_INPUT_V1"
RULES_SCHEMA = "M2_R06_INDEPENDENT_FRAME_RULES_V1"
CANONICAL_SCHEMA = "M3_R06_UNIQUE_FRAME_PLAN_V1"
CALENDAR_SCHEMA = "M3_R06_INDEPENDENT_FRAME_PLAN_V1"
TX_SCHEMA = "M3_R06_TX_FRAME_PLAN_V1"
FROZEN_RULES_SHA256 = (
    "3c968a151b0b5369f9dd95465761b2d87449c29975b1fca914f81fc5cfd01560"
)


class PlanInputError(ValueError):
    """The independent input is absent, malformed, or not frozen."""


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PlanInputError("ROOT_NOT_OBJECT")
    return value


def _require_int(value: Any, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise PlanInputError(f"{name}_INVALID")
    return value


def _validate_rules(rules: dict[str, Any], rules_bytes: bytes) -> None:
    if rules.get("schema") != RULES_SCHEMA:
        raise PlanInputError("RULES_SCHEMA")
    if _sha256_bytes(rules_bytes) != FROZEN_RULES_SHA256:
        raise PlanInputError("RULES_SHA256")
    expected = {
        "acc_bits": 32,
        "phase_step": 659_706_977,
        "core_hz_candidate": 40_000_000,
        "half_bclk_toggles_per_frame": 128,
    }
    for key, value in expected.items():
        if rules.get(key) != value:
            raise PlanInputError(f"RULES_{key.upper()}")
    if rules.get("initial_state") != {
        "accumulator": 0,
        "bclk": 0,
        "slot_count": 0,
    }:
        raise PlanInputError("RULES_INITIAL_STATE")


def _frame_cycles(release_cycle: int, stop_cycle: int,
                  acc_bits: int, phase_step: int,
                  toggles_per_frame: int) -> list[int]:
    """Apply the frozen closed form without consulting a captured trace."""
    modulus = 1 << acc_bits
    cycles: list[int] = []
    frame_index = 1
    while True:
        numerator = toggles_per_frame * frame_index * modulus
        edge_index = (numerator + phase_step - 1) // phase_step
        cycle = release_cycle + edge_index - 1
        if cycle > stop_cycle:
            return cycles
        cycles.append(cycle)
        frame_index += 1


def build_documents(input_doc: dict[str, Any], rules: dict[str, Any],
                    input_sha256: str, rules_sha256: str) -> dict[str, Any]:
    if input_doc.get("schema") != INPUT_SCHEMA:
        raise PlanInputError("INPUT_SCHEMA")
    if input_doc.get("status") != "FROZEN_INDEPENDENT_INPUT":
        raise PlanInputError("INPUT_NOT_FROZEN")
    if input_doc.get("independent_of_observed_trace") is not True:
        raise PlanInputError("TRACE_INDEPENDENCE_NOT_DECLARED")
    if any(key in input_doc for key in (
        "trace", "trace_path", "observed_frames", "observed_frame_rows"
    )):
        raise PlanInputError("FORBIDDEN_OBSERVED_TRACE_INPUT")

    source_identities = input_doc.get("source_identities")
    if not isinstance(source_identities, list) or not source_identities:
        raise PlanInputError("SOURCE_IDENTITIES_MISSING")
    for index, item in enumerate(source_identities):
        if not isinstance(item, dict):
            raise PlanInputError(f"SOURCE_IDENTITY_{index}_NOT_OBJECT")
        if not isinstance(item.get("path"), str) or not item["path"]:
            raise PlanInputError(f"SOURCE_IDENTITY_{index}_PATH")
        digest = item.get("sha256")
        if (not isinstance(digest, str) or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)):
            raise PlanInputError(f"SOURCE_IDENTITY_{index}_SHA256")

    raw_epochs = input_doc.get("epochs")
    if not isinstance(raw_epochs, list) or not raw_epochs:
        raise PlanInputError("EPOCHS_MISSING")

    epochs = []
    previous_epoch = -1
    previous_stop = -1
    for index, raw in enumerate(raw_epochs):
        if not isinstance(raw, dict):
            raise PlanInputError(f"EPOCH_{index}_NOT_OBJECT")
        epoch = _require_int(raw.get("epoch"), f"EPOCH_{index}_ID")
        reset_cycle = _require_int(raw.get("reset_assert_cycle"),
                                   f"EPOCH_{index}_RESET")
        window_kind = raw.get("window_kind")
        if window_kind not in {"ACTIVE", "RESET_ONLY"}:
            raise PlanInputError(f"EPOCH_{index}_WINDOW_KIND")
        raw_release = raw.get("release_cycle")
        stop_cycle = _require_int(raw.get("stop_cycle"),
                                  f"EPOCH_{index}_STOP")
        if epoch != previous_epoch + 1:
            raise PlanInputError(f"EPOCH_{index}_NONCONTIGUOUS")
        if index and reset_cycle != previous_stop + 1:
            raise PlanInputError(f"EPOCH_{index}_UNDECLARED_GAP_OR_OVERLAP")
        if reset_cycle > stop_cycle:
            raise PlanInputError(f"EPOCH_{index}_WINDOW_ORDER")
        if window_kind == "ACTIVE":
            release_cycle = _require_int(raw_release,
                                         f"EPOCH_{index}_RELEASE")
            if not (reset_cycle <= release_cycle <= stop_cycle):
                raise PlanInputError(f"EPOCH_{index}_WINDOW_ORDER")
            cycles = _frame_cycles(
                release_cycle,
                stop_cycle,
                int(rules["acc_bits"]),
                int(rules["phase_step"]),
                int(rules["half_bclk_toggles_per_frame"]),
            )
        else:
            if raw_release is not None:
                raise PlanInputError(f"EPOCH_{index}_RESET_ONLY_RELEASE")
            release_cycle = None
            cycles = []
        epochs.append({
            "epoch": epoch,
            "window_kind": window_kind,
            "reset_assert_cycle": reset_cycle,
            "release_cycle": release_cycle,
            "stop_cycle": stop_cycle,
            "cycles": cycles,
        })
        previous_epoch = epoch
        previous_stop = stop_cycle

    finish = input_doc.get("finish")
    if not isinstance(finish, dict):
        raise PlanInputError("FINISH_MISSING")
    finish_epoch = _require_int(finish.get("epoch"), "FINISH_EPOCH")
    finish_cycle = _require_int(finish.get("cycle"), "FINISH_CYCLE")
    if finish_epoch != epochs[-1]["epoch"] or finish_cycle != epochs[-1]["stop_cycle"]:
        raise PlanInputError("FINISH_NOT_LAST_STOP")

    identity_payload = {
        "schema": CANONICAL_SCHEMA,
        "formula": rules["formula"],
        "rules_sha256": rules_sha256,
        "input_sha256": input_sha256,
        "source_identities": source_identities,
        "parameters": {
            "acc_bits": rules["acc_bits"],
            "phase_step": rules["phase_step"],
            "core_hz_candidate": rules["core_hz_candidate"],
            "half_bclk_toggles_per_frame": rules[
                "half_bclk_toggles_per_frame"
            ],
            "initial_state": rules["initial_state"],
        },
        "epochs": epochs,
        "finish": {"epoch": finish_epoch, "cycle": finish_cycle},
    }
    identity_sha256 = _sha256_bytes(_canonical_bytes(identity_payload))
    plan_id = f"sha256:{identity_sha256}"
    common = {
        "authority": "CANDIDATE_INDEPENDENT_PLAN_NOT_M2_ADMITTED",
        "independent_of_trace": True,
        "canonical_plan_id": plan_id,
        "canonical_identity_sha256": identity_sha256,
        "generator_input_sha256": input_sha256,
        "frame_rules_sha256": rules_sha256,
        "finish": identity_payload["finish"],
        "real_authority_claimed": False,
    }
    canonical = dict(identity_payload)
    canonical.update({
        "canonical_plan_id": plan_id,
        "canonical_identity_sha256": identity_sha256,
        "authority": common["authority"],
        "independent_of_trace": True,
        "real_authority_claimed": False,
    })
    calendar_projection = {
        "schema": CALENDAR_SCHEMA,
        **common,
        "epochs": [
            {"epoch": item["epoch"], "frame_cycles": item["cycles"]}
            for item in epochs
        ],
        "projection_of": plan_id,
    }
    tx_projection = {
        "schema": TX_SCHEMA,
        **common,
        "epochs": [
            {"epoch": item["epoch"], "cycles": item["cycles"]}
            for item in epochs
        ],
        "projection_of": plan_id,
    }
    return {
        "canonical": canonical,
        "event_calendar_projection": calendar_projection,
        "tx_checker_projection": tx_projection,
    }


def generate(input_path: Path, rules_path: Path, output_dir: Path) -> None:
    input_bytes = input_path.read_bytes()
    rules_bytes = rules_path.read_bytes()
    input_doc = json.loads(input_bytes.decode("utf-8"))
    rules = json.loads(rules_bytes.decode("utf-8"))
    if not isinstance(input_doc, dict) or not isinstance(rules, dict):
        raise PlanInputError("ROOT_NOT_OBJECT")
    _validate_rules(rules, rules_bytes)
    documents = build_documents(
        input_doc,
        rules,
        _sha256_bytes(input_bytes),
        _sha256_bytes(rules_bytes),
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    filenames = {
        "canonical": "UNIQUE_FRAME_PLAN.json",
        "event_calendar_projection": "FRAME_PLAN.json",
        "tx_checker_projection": "TX_FRAME_PLAN.json",
    }
    for key, filename in filenames.items():
        (output_dir / filename).write_bytes(_canonical_bytes(documents[key]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--rules", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    generate(args.input, args.rules, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
