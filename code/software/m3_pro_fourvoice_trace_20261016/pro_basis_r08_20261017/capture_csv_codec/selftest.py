"""NOT_RUN case adapter for capture_csv_codec."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from capture_csv_codec import (EXTENSIONS, FIELDS, SOURCE, CodecReject,
                               decode_rows, encode_rows, iter_decode)


def _row() -> dict:
    fields = dict.fromkeys(FIELDS)
    fields.update(cycle=0, epoch=0, rst_n=1, tx_sample_valid=1,
                  tx_req_id=0, tx_clip=1, finish=1)
    ext = dict.fromkeys(EXTENSIONS)
    ext.update(schema="M3_R7A_TX_EXTENSION_V1", obs_core_clk=1,
               obs_polyphonic_valid=1, obs_tx_metadata_valid=1,
               obs_tx_req_id_valid=1, obs_tx_clip_mask=2,
               obs_metadata_error=0, obs_frame_id_overflow=0,
               uart_tx=1, raw_tx_req_id_bits="0" * 32)
    source = dict.fromkeys(SOURCE)
    source.update(raw_sha256="1" * 64, reset_edges_sha256="2" * 64,
                  line=1, cycle=0, epoch=0, time_ps=0,
                  sampling_phase="POSEDGE_PRE_NBA")
    return {"schema": "M3_R7A_PUBLIC_ROW_V1", "capture_id": "fixture",
            "origin": "SYNTHETIC_SCHEMA_FIXTURE", "source": source,
            "fields": fields, "extensions": ext, "missing_reasons": {},
            "events": ["TX_ADOPT", "FINISH"]}


def run_case(case_id: str, output_dir: Path) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    row = _row()
    expected = "PASS"
    actual_input = None
    component_output = None
    if case_id == "ROUNDTRIP_61_TX":
        actual_input = {"rows": [row]}
        encoded = encode_rows([row])
        decoded = decode_rows(encoded)
        component_output = {"encoded_csv": encoded, "decoded_rows": decoded}
        if decoded != [row]:
            raise AssertionError("ROUNDTRIP_CHANGED")
    elif case_id == "STARTUP_NULL_VS_ID0":
        startup = copy.deepcopy(row)
        startup["fields"]["tx_req_id"] = None
        startup["extensions"]["obs_tx_req_id_valid"] = 0
        actual_input = {"rows": [startup, row]}
        encoded = encode_rows([startup, row])
        decoded = decode_rows(encoded)
        component_output = {"encoded_csv": encoded, "decoded_rows": decoded}
        if decoded != [startup, row]:
            raise AssertionError("NULL_OR_ZERO_CHANGED")
    elif case_id == "UNKNOWN_EXTENSION_REJECT":
        row["extensions"]["schema"] = "UNKNOWN"
        expected = "TX_EXTENSION_PROFILE"
        actual_input = {"rows": [row]}
        try:
            encode_rows([row])
        except CodecReject as exc:
            if expected not in str(exc):
                raise
            component_output = {"exception": str(exc)}
        else:
            raise AssertionError("UNKNOWN_EXTENSION_ACCEPTED")
    elif case_id == "LEGACY_29_COLUMN_REJECT":
        expected = "CSV_HEADER_PROFILE"
        legacy_csv = ",".join(f"c{x}" for x in range(29)) + "\n"
        actual_input = {"csv": legacy_csv}
        try:
            decode_rows(legacy_csv)
        except CodecReject as exc:
            if expected not in str(exc):
                raise
            component_output = {"exception": str(exc)}
        else:
            raise AssertionError("LEGACY_PROFILE_ACCEPTED")
    elif case_id == "STREAMING_NO_READ_AHEAD":
        second = copy.deepcopy(row)
        second["source"]["line"] = 2
        second["source"]["cycle"] = 1
        second["fields"]["cycle"] = 1
        encoded = encode_rows([row, second])
        physical_lines = encoded.splitlines(keepends=True)

        class GuardedLines:
            def __init__(self, lines: list[str]) -> None:
                self.lines = iter(lines)
                self.consumed = 0

            def __iter__(self):
                return self

            def __next__(self) -> str:
                if self.consumed >= 2:
                    raise AssertionError("DECODER_READ_AHEAD")
                self.consumed += 1
                return next(self.lines)

        guarded = GuardedLines(physical_lines)
        decoded = iter_decode(guarded)
        first = next(decoded)
        actual_input = {"csv_physical_lines": physical_lines,
                        "guard_after_lines": 2}
        component_output = {"first_decoded_row": first,
                            "physical_lines_consumed": guarded.consumed}
        if first != row or guarded.consumed != 2:
            raise AssertionError("STREAMING_BOUNDARY")
    else:
        raise KeyError(case_id)
    result = {"case_id": case_id, "status": "PASS", "expected": expected}
    (output_dir / "input.json").write_text(json.dumps(actual_input, indent=2) + "\n",
                                             encoding="utf-8")
    (output_dir / "component_output.json").write_text(
        json.dumps(component_output, indent=2) + "\n", encoding="utf-8")
    (output_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n",
                                              encoding="utf-8")
    return result
