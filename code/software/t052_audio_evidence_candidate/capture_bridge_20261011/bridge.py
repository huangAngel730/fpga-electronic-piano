"""Strict read-only T052 v2 text -> four unmodified mono PCM16 WAV files.

Only Python's standard library is imported. No model, simulator or EDA entry.
An ordinal pairs requests and captures; 8-bit IDs may repeat and wrap.
"""

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import wave


PROFILE = "T052_MODELSIM_REPAIR_V2_4137"
CAP_SHA = "5c67ab75d74537aca9c9c3c69d20eb3be0a0c65d7b940dd027576454cca68fc0"
REQ_SHA = "4e5ceaf804dca473cd81270f3add4ce7dc2808554d676dca314ea2ac27946570"
TB_SHA = "7e1fcd31698cb3778f13b3edc4566504e1ddbe4b175af8193fe9cad258090c4c"
REQ = re.compile(r"REQ\s+([0-9]+)\s+([0-9a-fA-F]{8})\s+"
                 r"([0-9a-fA-F]{8})\s+([0-9a-fA-F]{8})\s+"
                 r"([0-9a-fA-F]{8})\s+([0-9]+)", re.ASCII)
CAP = re.compile(r"ID=\s*([0-9]+)\s+PCM\s+v0=\s*(-?[0-9]+)\s+"
                 r"v1=\s*(-?[0-9]+)\s+v2=\s*(-?[0-9]+)\s+"
                 r"v3=\s*(-?[0-9]+)\s+ACT=([0-9]+)\s+CLIP=([01])",
                 re.ASCII)
KEYS = {"schema", "profile", "expected_rows", "capture_sha256",
        "request_sha256", "wav_rate_hz", "rate_mode", "rate_rationale"}
FALSE_CLAIMS = {"provenance_verified": False,
                "independent_voice_count_proven": False,
                "physical_validation": False, "sample_timing_verified": False,
                "T052_complete": False, "mathematics_newly_verified": False,
                "accepted_handshakes_verified": False,
                "consumer_backpressure_verified": False,
                "PCM24_commit_verified": False, "physical_STA_verified": False}


def require(condition, code):
    if not condition:
        raise ValueError(code)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               ensure_ascii=True, allow_nan=False) + "\n",
                    encoding="utf-8", newline="\n")


def load_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError("NONFINITE_JSON:" + value)

    return json.loads(data, object_pairs_hook=pairs, parse_constant=nonfinite)


def config_for(capture, requests, rows, profile=PROFILE, rate=48000):
    return dict(schema="T052_CAPTURE_BRIDGE_1", profile=profile,
                expected_rows=rows, capture_sha256=sha(capture),
                request_sha256=sha(requests), wav_rate_hz=rate,
                rate_mode="logical_replay_rate",
                rate_rationale="Explicit logical replay, not physical TB timing; "
                               "no resampling or interpolation is performed.")


def validate_config(config):
    require(type(config) is dict and set(config) == KEYS, "CONFIG_SCHEMA")
    require(config["schema"] == "T052_CAPTURE_BRIDGE_1", "CONFIG_VERSION")
    require(config["profile"] in (PROFILE, "SYNTHETIC_SOFTWARE_TEST"), "PROFILE")
    require(type(config["expected_rows"]) is int
            and 1 <= config["expected_rows"] <= 1000000, "EXPECTED_ROWS")
    require(type(config["wav_rate_hz"]) is int
            and 1 <= config["wav_rate_hz"] <= 384000, "WAV_INTEGER_RATE")
    require(config["rate_mode"] == "logical_replay_rate",
            "PHYSICAL_TIME_MAPPING_BLOCKED_NONINTEGER_TB_RATE")
    require(type(config["rate_rationale"]) is str
            and bool(config["rate_rationale"].strip()), "RATE_RATIONALE")
    for key in ("capture_sha256", "request_sha256"):
        require(type(config[key]) is str
                and re.fullmatch(r"[0-9a-f]{64}", config[key]), "INPUT_SHA_SCHEMA")
    if config["profile"] == PROFILE:
        require(config["expected_rows"] == 4137, "FROZEN_ROW_COUNT")
        require(config["capture_sha256"] == CAP_SHA
                and config["request_sha256"] == REQ_SHA, "FROZEN_INPUT_SHA")


def parse_rows(capture, requests, expected_rows):
    # No ignored comments, blank records, unknown tags, trailing records or END.
    try:
        cap_lines = capture.decode("ascii").splitlines()
        req_lines = requests.decode("ascii").splitlines()
    except UnicodeError as error:
        raise ValueError("ASCII_INPUT") from error
    require(len(cap_lines) == len(req_lines) == expected_rows, "ROW_COUNT")
    rows = []
    for ordinal, (cl, rl) in enumerate(zip(cap_lines, req_lines)):
        c, r = CAP.fullmatch(cl), REQ.fullmatch(rl)
        require(c is not None, "CAPTURE_SCHEMA:" + str(ordinal))
        require(r is not None, "REQUEST_SCHEMA:" + str(ordinal))
        cid, *tail = map(int, c.groups())
        values, act, clip = tail[:4], tail[4], tail[5]
        rid, mask = int(r[1]), int(r[6])
        fcws = [int(r[i], 16) for i in range(2, 6)]
        require(0 <= cid <= 255 and 0 <= rid <= 255, "ID_RANGE")
        require(cid == rid, "PAIRED_ID")
        require(0 <= mask <= 15, "MASK_RANGE")
        require(0 <= act <= 4 and act == mask.bit_count(), "ACT_MASK")
        require(all(-32768 <= value <= 32767 for value in values), "PCM16_RANGE")
        rows.append(dict(ordinal=ordinal, capture_line=ordinal + 1,
                         request_line=ordinal + 1, id=cid, mask=mask, act=act,
                         clip_provenance_only=clip, pcm16=values, fcw=fcws))
    return rows


def export(capture_path, request_path, config_path, output):
    require(not output.exists(), "OUTPUT_EXISTS")
    config_raw = config_path.read_bytes()
    config = load_json(config_raw)
    validate_config(config)
    capture, requests = capture_path.read_bytes(), request_path.read_bytes()
    require(sha(capture) == config["capture_sha256"], "CAPTURE_SHA")
    require(sha(requests) == config["request_sha256"], "REQUEST_SHA")
    rows = parse_rows(capture, requests, config["expected_rows"])
    output.mkdir(parents=True, exist_ok=False)
    (output / "original.capture").write_bytes(capture)
    (output / "original.requests").write_bytes(requests)
    (output / "config.json").write_bytes(config_raw)
    rate = config["wav_rate_hz"]
    readback = []
    for lane in range(4):
        path = output / ("lane" + str(lane) + ".wav")
        pcm = [row["pcm16"][lane] for row in rows]
        packed = struct.pack("<" + "h" * len(pcm), *pcm)
        with wave.open(str(path), "wb") as wav:
            wav.setparams((1, 2, rate, len(pcm), "NONE", "not compressed"))
            wav.writeframes(packed)
        with wave.open(str(path), "rb") as wav:
            require((wav.getnchannels(), wav.getsampwidth(), wav.getframerate(),
                     wav.getnframes(), wav.getcomptype())
                    == (1, 2, rate, len(pcm), "NONE"), "WAV_HEADER")
            actual = wav.readframes(len(pcm) + 1)
        require(actual == packed, "WAV_READBACK")
        readback.append(dict(lane=lane, frames=len(pcm), mismatches=0,
                             pcm_bytes_sha256=sha(actual),
                             wav_sha256=sha(path.read_bytes())))
    with (output / "sample_mapping.jsonl").open("w", encoding="utf-8",
                                                newline="\n") as stream:
        for row in rows:
            row["wav_frame"] = row["ordinal"]
            row["wav_pcm_byte_offset"] = 2 * row["ordinal"]
            row["wav_file_byte_offset"] = 44 + 2 * row["ordinal"]
            # Exact FCW frequencies at the EXPLICIT replay rate; not a peak test.
            row["fcw_replay_frequency_hz"] = [
                dict(numerator=fcw * rate, denominator=1 << 32)
                for fcw in row["fcw"]]
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    metadata = dict(status="STRUCTURAL_EXPORT_AND_INTEGER_READBACK_PASS",
                    exit_code=0, profile=config["profile"], rows=len(rows),
                    lane_samples=4 * len(rows), readback=readback,
                    provenance=("RTL_CAPTURE_REPLAY" if config["profile"] == PROFILE
                                else "SYNTHETIC_SOFTWARE_TEST"),
                    capture_sha256=sha(capture), request_sha256=sha(requests),
                    config_sha256=sha(config_raw), exporter_sha256=sha(
                        Path(__file__).read_bytes()),
                    input_has_END=False,
                    completeness="exact original SHA plus explicit expected_rows",
                    rate_mode=config["rate_mode"], wav_rate_hz=rate,
                    rate_rationale=config["rate_rationale"],
                    reference_TB_sha256=(TB_SHA if config["profile"] == PROFILE else None),
                    reference_TB_clock_hz=50000000,
                    reference_TB_sample_interval_cycles=1042,
                    reference_TB_time_rate_hz=dict(numerator=50000000,
                                                   denominator=1042),
                    reference_TB_rate_approx=float(Fraction(50000000, 1042)),
                    physical_time_mapping="BLOCKED: WAV integer rate cannot "
                                          "represent 50000000/1042 exactly",
                    fixed_tone_frequency_PASS=False,
                    reference_04b17e4d_replay_hz=0x04B17E4D * rate / (1 << 32),
                    clip_semantics="raw provenance only, not commit-chain clipping",
                    sample_mapping_sha256=sha((output / "sample_mapping.jsonl").read_bytes()),
                    **FALSE_CLAIMS)
    # Source reads are immutable across this execution as well as before export.
    require(capture_path.read_bytes() == capture
            and request_path.read_bytes() == requests
            and config_path.read_bytes() == config_raw, "INPUT_CHANGED_DURING_RUN")
    dump(output / "receipt.json", metadata)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(export(args.capture, args.requests, args.config, args.output)))
        return 0
    except (ValueError, OSError, wave.Error) as error:
        print("REFUSED:" + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
