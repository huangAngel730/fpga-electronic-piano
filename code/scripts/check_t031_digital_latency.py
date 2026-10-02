"""Strict analysis of T031 RTL timestamps, not instrument CSV/analog proof.
Clocks50MHz; test originR17 status start, endfull received velocity byte pulse.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics

SCENARIOS = ["idle_low_soft", "idle_A4_soft", "idle_high_hard", "idle_A4_phase0",
             "idle_A4_phase15", "idle_A4_phase31", "idle_A4_phase63", "fourth_voice",
             "fifth_voice_steal", "held_retrigger_soft", "release_retrigger"]
FIELDS = ["trial", "note", "raw_velocity", "message_start_slot", "voices_before", "start_cycle",
          "final_byte_rx_cycle", "event_accept_cycle", "note_on_cycle", "first_sample_cycle",
          "first_commit_cycle", "first_buffer_diff_cycle", "first_frame_diff_cycle",
          "right_word_complete_cycle", "left_word_complete_cycle", "dut_right_pcm16",
          "reference_right_pcm16", "dut_left_pcm16", "reference_left_pcm16"]


def summarize(values):
    return {"min_ms": min(values), "mean_ms": statistics.fmean(values), "max_ms": max(values)}


def analyze(path):
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["scenario"] + FIELDS:
            raise ValueError("Unexpected timestamp CSV columns")
        rows = list(reader)
    if [row["scenario"] for row in rows] != SCENARIOS:
        raise ValueError("Missing/repeated/out-of-order target workload")
    output = []
    for index, row in enumerate(rows, 1):
        values = {key: int(row[key]) for key in FIELDS}
        if values["trial"] != index:
            raise ValueError("Bad trial sequence")
        if not (0 <= values["note"] <= 127 and 1 <= values["raw_velocity"] <= 127 and 0 <= values["message_start_slot"] <= 63):
            raise ValueError("Invalid MIDI workload")
        sequence = [values[field] for field in FIELDS[5:13]]
        # status-start, finalUART-byte, FIFOaccept, ADSRNoteOn, laneTick,
        # firstcommit, firstactualbufferdifference, firstadoptedDACframe.
        if min(sequence) <= 0 or sequence[0] >= sequence[1] or sequence != sorted(sequence):
            raise ValueError("Missing or misordered causal stages: " + row["scenario"])
        for field in ["right_word_complete_cycle", "left_word_complete_cycle"]:
            if values[field] < sequence[-1]:
                raise ValueError("Physical word appears before adopted frame")
        if not 47200 <= values["final_byte_rx_cycle"] - values["start_cycle"] <= 47210:
            raise ValueError("Unexpected real31250/three-byte transport duration")
        if values["dut_right_pcm16"] == values["reference_right_pcm16"] or values["dut_left_pcm16"] == values["reference_left_pcm16"]:
            raise ValueError("Response is not caused by the omitted target NoteOn")
        for field in ["dut_right_pcm16", "reference_right_pcm16", "dut_left_pcm16", "reference_left_pcm16"]:
            if not -32768 <= values[field] <= 32767:
                raise ValueError("Bad signed16 decoded word")
        segments = {
            "MIDI_transport_to_final_UART_pulse_ms": (values["final_byte_rx_cycle"] - values["start_cycle"]) / 50000,
            "received_to_event_accept_ms": (values["event_accept_cycle"] - values["final_byte_rx_cycle"]) / 50000,
            "event_to_voice_note_on_ms": (values["note_on_cycle"] - values["event_accept_cycle"]) / 50000,
            "voice_to_first_sample_tick_ms": (values["first_sample_cycle"] - values["note_on_cycle"]) / 50000,
            "sample_tick_to_commit_ms": (values["first_commit_cycle"] - values["first_sample_cycle"]) / 50000,
            "commit_to_quantized_frame_difference_ms": (values["first_frame_diff_cycle"] - values["first_commit_cycle"]) / 50000,
            "frame_to_right_complete_word_ms": (values["right_word_complete_cycle"] - values["first_frame_diff_cycle"]) / 50000,
            "frame_to_left_complete_word_ms": (values["left_word_complete_cycle"] - values["first_frame_diff_cycle"]) / 50000,
        }
        for channel in ["right", "left"]:
            end = values[channel + "_word_complete_cycle"]
            segments["message_start_to_" + channel + "_word_ms"] = (end - values["start_cycle"]) / 50000
            segments["final_receive_to_" + channel + "_word_ms"] = (end - values["final_byte_rx_cycle"]) / 50000
            if segments["message_start_to_" + channel + "_word_ms"] >= 10:
                raise ValueError("Digital sampled scenario exceeds10ms: " + row["scenario"])
        output.append({"scenario": row["scenario"], "timestamps_sysclk50MHz": values, "segments": segments})
    summaries = {field: summarize([row["segments"][field] for row in output])
                 for field in output[0]["segments"]}
    return {"date": "2026-10-02", "scope": "actual unmodified production RTL digital pipeline sampled workloads, not board analog or universal worst-case proof",
            "system_clock_hz": 50000000, "MIDI_baud": 31250, "audio_sample_rate_hz": 48000,
            "input_start": "R17-like testbench RX falling start-bit edge of full90 note velocity message",
            "complete_receive": "uart_rx.rx_valid on finalvelocity byte at stop-bit midpoint; not fullstopbit end",
            "output_end": "last rising BCLK of first complete PT8211 right/left16bit word differing from target-omitted production reference",
            "trial_count": len(output), "rows": output, "sampled_statistics": summaries,
            "CSV_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "physical_analog_latency_proven": False, "T031_closed": False,
            "limitations": ["No DIN optocoupler beforeR17 delay/keyboard sensing delay or USB stack included",
                            "DAC conversion/analog filter/amplifier/speaker and audible amplitude threshold not modeled",
                            "Busy chord firstdifference isolates target message but is not onset of an entire new waveform",
                            "11 sampled trials/frame positions not exhaustive phase/queue/congestion worst-case bound",
                            "Current V1+sustain algorithm not future Pitch/Mod/LFO/effects/video build"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("CSV", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.CSV)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    for row in report["rows"]:
        seg = row["segments"]
        print("PASS", row["scenario"], "message_start_to_R_ms", seg["message_start_to_right_word_ms"],
              "message_start_to_L_ms", seg["message_start_to_left_word_ms"])
    print("Sampled maximum right/left ms:", report["sampled_statistics"]["message_start_to_right_word_ms"]["max_ms"],
          report["sampled_statistics"]["message_start_to_left_word_ms"]["max_ms"])
    print("Digital-only result; T031 real analog requirement still pending")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as exc:
        print("FAIL T031 timestamp analysis:", exc);raise SystemExit(1)
