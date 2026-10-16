"""Static arithmetic for the exact frozen R05 TB, not simulation evidence."""
import argparse
from pathlib import Path
import re
import zipfile

from common import R05, R05_SHA, TB_SHA, identity, sha, write_new


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if identity(R05)["sha256"] != R05_SHA:
        raise ValueError("R05 archive mismatch")
    with zipfile.ZipFile(R05) as archive:
        raw = archive.read("inputs/tb_m2_m1td_real_chain.sv")
    if sha(raw) != TB_SHA:
        raise ValueError("frozen TB mismatch")
    text = raw.decode("utf-8")
    body = text.split("    initial begin\n", 1)[1].split("    initial begin #", 1)[0]
    calls = re.findall(r"midi_byte\(8'[hd][0-9A-Fa-f]+\)", body)
    if len(calls) != 17 or "for(i=0;i<8;i=i+1)" not in text:
        raise ValueError("audited task structure changed")
    if text.count("#32000") != 3:
        raise ValueError("audited UART task delays changed")
    delays = list(map(int, re.findall(r"#([0-9]+)", body)))
    if delays != [500, 1500, 4000, 220000, 220000, 220000, 220000, 1000]:
        raise ValueError("audited initial schedule changed")
    byte_ns = (1 + 8 + 1) * 32000
    watchdog = int(re.search(r"initial begin #([0-9]+);\$fatal\(1,\"M1TD_REAL_CHAIN_TIMEOUT", text)[1])
    end_ns = len(calls) * byte_ns + sum(delays[:-1])
    pass_ns = end_ns + delays[-1]
    result = {
        "evidence_kind": "EXACT_FROZEN_SOURCE_STATIC_TIME_ARITHMETIC",
        "archive": identity(R05), "TB_sha256": TB_SHA,
        "timescale": "1ns/1ps", "midi_byte_calls": len(calls),
        "bits_per_uart_byte": 10, "bit_ns": 32000, "byte_ns": byte_ns,
        "literal_main_delays_ns": delays,
        "earliest_END_ns_if_all_prior_checks_pass": end_ns,
        "earliest_PASS_ns_if_all_prior_checks_pass": pass_ns,
        "fifth_note_start_ns": 14 * byte_ns + 6000 + 3 * 220000,
        "fifth_note_bytes_complete_ns": 17 * byte_ns + 6000 + 3 * 220000,
        "watchdog_ns": watchdog, "PASS_exceeds_watchdog_ns": pass_ns - watchdog,
        "conclusion": "FROZEN_TB_WATCHDOG_PRECEDES_UNCONDITIONAL_SCHEDULE_END",
        "RTL_executed_by_this_script": False,
        "runtime_claim": "Only original vsim log proves actual fatal at 6 ms",
        "required_decision": "M2 must correct and freeze TB/input identity and decide fresh execution authority",
    }
    if pass_ns <= watchdog:
        raise ValueError("claimed conflict absent")
    write_new(args.output, result)
    print("STATIC_SCHEDULE_CONFLICT_CONFIRMED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
