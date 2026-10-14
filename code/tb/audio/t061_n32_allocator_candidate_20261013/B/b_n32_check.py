"""Strict replay checker for the isolated N32/R1 successor combination.

The ordinary B2C rows are replayed by the frozen independent router/DSP
oracle.  ``K`` is an additional public-output observation emitted on every
edge for which result_valid or publish is asserted::

    K cycle valid ready publish id_hex left_dec right_dec late clipped

The output ledger never derives an expected value from a DUT result.  PCM is
the saturated sum of the 32 lane values that the independent B2C oracle checks
against the frozen ROM/integer models in the same run; clipped is derived from
the corresponding unsaturated wide sum.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[5]
REFERENCE = ROOT / "code" / "software" / "polyphony_scaling_candidate"
sys.path.insert(0, str(REFERENCE))

from b2c_check import check as reference_check  # noqa: E402


N = 32
HEADER = re.compile(r"B2C 32 1 ([01])")
FINISH = re.compile(
    r".*[/\\](?:tb_b_n32_r1|tb_b2d_event_audio)\.sv:[0-9]+: "
    r"\$finish called at [0-9]+ \(1ps\)"
)


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def decimal(text: str, low: int, high: int) -> int:
    require(bool(re.fullmatch(r"-?(0|[1-9][0-9]*)", text)), "K_DECIMAL_SCHEMA")
    value = int(text)
    require(low <= value <= high, "K_DECIMAL_RANGE")
    return value


def hexadecimal(text: str, width: int) -> int:
    require(bool(re.fullmatch(r"[0-9a-f]+", text)), "K_HEX_SCHEMA")
    value = int(text, 16)
    require(value < (1 << width), "K_HEX_RANGE")
    return value


def saturated_sum(lanes: dict[int, int]) -> tuple[int, bool]:
    require(set(lanes) == set(range(N)), "RESULT_REQUIRES_ALL_32_LANES")
    total = sum(lanes.values())
    pcm = max(-(1 << 23), min((1 << 23) - 1, total))
    return pcm, pcm != total


class OutputLedger:
    """Independent request/result lifetime and public HOLD ledger."""

    def __init__(self) -> None:
        self.reset_lifetime = -1
        self.accept_serial = 0
        self.active: dict | None = None
        self.hold_payload: tuple[int, int, int, int, int] | None = None
        self.requests = 0
        self.publishes = 0
        self.cancels = 0
        self.hold_edges = 0
        self.clipped_results = 0
        self.unclipped_results = 0
        self.contributing_slots: set[int] = set()

    def reset(self) -> None:
        self.reset_lifetime += 1
        self.active = None
        self.hold_payload = None

    def request(self, result_id: int) -> None:
        require(self.reset_lifetime >= 0, "REQUEST_BEFORE_RESET")
        require(self.active is None, "OVERLAPPING_LEDGER_REQUEST")
        self.active = {
            "id": result_id,
            "serial": self.accept_serial,
            "reset_lifetime": self.reset_lifetime,
            "lanes": {},
            "first_seen": False,
        }
        self.accept_serial += 1
        self.requests += 1

    def lane(self, slot: int, pcm: int) -> None:
        require(self.active is not None, "LANE_WITHOUT_LEDGER_REQUEST")
        require(slot not in self.active["lanes"], "DUPLICATE_LEDGER_LANE")
        self.active["lanes"][slot] = pcm
        if pcm:
            self.contributing_slots.add(slot)

    def cancel(self) -> None:
        if self.active is not None:
            self.cancels += 1
        self.active = None
        self.hold_payload = None

    def result(
        self,
        *,
        valid: int,
        ready: int,
        publish: int,
        result_id: int,
        left: int,
        right: int,
        late: int,
        clipped: int,
        first: bool,
        published_row: bool,
    ) -> None:
        require(valid or publish, "K_WITHOUT_VALID_OR_PUBLISH")
        require(publish == (valid & ready), "K_PUBLISH_HANDSHAKE")
        require(self.active is not None, "RESULT_WITHOUT_LIVE_REQUEST")
        expected_pcm, expected_clipped = saturated_sum(self.active["lanes"])
        require(result_id == self.active["id"], "RESULT_ID_LEDGER")
        require(left == expected_pcm and right == expected_pcm, "RESULT_PCM_LEDGER")
        require(clipped == int(expected_clipped), "RESULT_CLIPPED_LEDGER")
        require(first == (not self.active["first_seen"]), "RESULT_FIRST_ALIGNMENT")
        require(published_row == bool(publish), "RESULT_PUBLISH_ALIGNMENT")
        payload = (result_id, left, right, late, clipped)
        if self.hold_payload is not None:
            require(payload == self.hold_payload, "RESULT_HOLD_STABILITY")
        self.active["first_seen"] = True
        if publish:
            self.publishes += 1
            self.clipped_results += clipped
            self.unclipped_results += not clipped
            self.active = None
            self.hold_payload = None
        else:
            require(not ready, "RESULT_READY_WITHOUT_PUBLISH")
            self.hold_edges += 1
            self.hold_payload = payload


def _capture_lines(raw: bytes) -> tuple[list[str], bool]:
    lines = raw.decode("ascii").splitlines()
    if len(lines) >= 2 and lines[-2].startswith("END ") and FINISH.fullmatch(lines[-1]):
        lines.pop()
    header = HEADER.fullmatch(lines[0]) if lines else None
    require(header is not None, "N32_B_HEADER")
    return lines, bool(int(header.group(1)))


def _group_rows(lines: list[str]) -> dict[int, list[list[str]]]:
    groups: dict[int, list[list[str]]] = {}
    last = -1
    for line in lines[1:]:
        row = line.split()
        require(bool(row), "EMPTY_ROW")
        require(len(row) >= 2, "ROW_SCHEMA")
        cycle = decimal(row[1], 0, 0xFFFFFFFF)
        require(cycle >= last, "CYCLE_ORDER")
        last = cycle
        groups.setdefault(cycle, []).append(row)
    return groups


def check(raw: bytes) -> dict:
    lines, long_case = _capture_lines(raw)
    k_rows = [line for line in lines[1:] if line.startswith("K ")]
    require(bool(k_rows), "MISSING_K_OBSERVATIONS")
    ordinary = [lines[0]] + [line for line in lines[1:] if not line.startswith("K ")]

    ledger = OutputLedger()
    groups = _group_rows(lines)
    ended = False
    for _, rows in groups.items():
        tags = {row[0] for row in rows}
        require(not ended, "TRAILING_AFTER_END")
        if "END" in tags:
            require(len(rows) == 1, "END_ROW_CONFLICT")
            ended = True
            continue
        if "R" in tags:
            require(len(rows) == 1, "RESET_ROW_CONFLICT")
            ledger.reset()
            continue
        for row in rows:
            if row[0] == "J":
                require(len(row) == 3, "J_SCHEMA")
                ledger.request(hexadecimal(row[2], 32))
            elif row[0] == "L":
                require(len(row) == 11, "L_SCHEMA")
                ledger.lane(decimal(row[3], 0, N - 1),
                            decimal(row[9], -(1 << 23), (1 << 23) - 1))

        if "X" in tags or "Z" in tags:
            require(not ({"F", "P", "K"} & tags), "RESULT_ON_CANCEL_EDGE")
            ledger.cancel()
            continue

        first_rows = [row for row in rows if row[0] == "F"]
        publish_rows = [row for row in rows if row[0] == "P"]
        observed = [row for row in rows if row[0] == "K"]
        require(len(first_rows) <= 1 and len(publish_rows) <= 1 and len(observed) <= 1,
                "DUPLICATE_RESULT_ROW_AT_EDGE")
        require(bool(observed) == bool(first_rows or publish_rows or ledger.hold_payload),
                "K_EDGE_COVERAGE")
        if not observed:
            continue
        row = observed[0]
        require(len(row) == 10, "K_SCHEMA")
        values = {
            "valid": decimal(row[2], 0, 1),
            "ready": decimal(row[3], 0, 1),
            "publish": decimal(row[4], 0, 1),
            "result_id": hexadecimal(row[5], 32),
            "left": decimal(row[6], -(1 << 23), (1 << 23) - 1),
            "right": decimal(row[7], -(1 << 23), (1 << 23) - 1),
            "late": decimal(row[8], 0, 1),
            "clipped": decimal(row[9], 0, 1),
        }
        public_row = first_rows[0] if first_rows else publish_rows[0] if publish_rows else None
        if public_row is not None:
            require(len(public_row) == 6, "PUBLIC_RESULT_SCHEMA")
            public_payload = (
                hexadecimal(public_row[2], 32),
                decimal(public_row[3], -(1 << 23), (1 << 23) - 1),
                decimal(public_row[4], -(1 << 23), (1 << 23) - 1),
                decimal(public_row[5], 0, 1),
            )
            require(public_payload == (
                values["result_id"], values["left"], values["right"], values["late"]
            ), "K_PUBLIC_RESULT_ALIGNMENT")
        ledger.result(
            **values,
            first=bool(first_rows),
            published_row=bool(publish_rows),
        )

    require(ended, "MISSING_END")
    require(ledger.active is None and ledger.hold_payload is None,
            "END_LIVE_LEDGER_TRANSACTION")
    require(ledger.contributing_slots == set(range(N)), "ALL_32_CONTRIBUTIONS_REQUIRED")
    require(ledger.hold_edges > 0, "HOLD_COVERAGE_REQUIRED")
    require(ledger.cancels > 0, "CANCEL_COVERAGE_REQUIRED")
    require(ledger.clipped_results > 0 and ledger.unclipped_results > 0,
            "CLIPPED_AND_UNCLIPPED_COVERAGE_REQUIRED")
    # Run the full independent router/control/DSP oracle after the public
    # ledger.  This ordering makes output-only behavior mutants fail with the
    # precise ID/PCM/clipped diagnostic instead of a coarser legacy message.
    reference = reference_check(
        ("\n".join(ordinary) + "\n").encode("ascii"),
        sizes=(N,),
        responses=(1,),
        identity_controls=True,
        extra_long_events=1,
    )
    reference.update(
        status="N32_B_R1_EVENT_AUDIO_PASS_T061_PARTIAL",
        public_output_observations=len(k_rows),
        accepted_requests=ledger.requests,
        published_results=ledger.publishes,
        cancelled_requests=ledger.cancels,
        hold_edges=ledger.hold_edges,
        clipped_results=ledger.clipped_results,
        unclipped_results=ledger.unclipped_results,
        independently_traced_contributing_slots=len(ledger.contributing_slots),
        long_lifecycle_fixture=long_case,
        capture_sha256=hashlib.sha256(raw).hexdigest(),
        exact_allocator_A_identity="BOUND_BY_EXECUTION_PLAN",
        physical_STA="NOT_RUN",
        full_T061_complete=False,
    )
    return reference


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result, code = check(args.input.read_bytes()), 0
    except (ValueError, OSError, UnicodeError) as error:
        result, code = {"status": "REJECT", "reason": str(error)}, 1
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
