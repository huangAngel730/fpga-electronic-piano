"""Streaming R01 transaction checker; never invokes HDL or verifies PCM math.

Even successful raw traces remain PROVENANCE_NOT_VERIFIABLE until a separate
approved runner receipt binds this exact input/source/tool/output set.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from plan import COUNT, RESETS, VERSION, Calendar, controls, pack


class Incomplete(ValueError):
    pass


def sha(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def read_json(raw):
    def nonfinite(_):
        raise ValueError("NONFINITE_JSON")
    return json.loads(raw, object_pairs_hook=reject_duplicates,
                      parse_constant=nonfinite)


def equal(actual, expected):
    # JSON true/1 and 3.0/3 must never compare equal.
    return type(actual) is type(expected) and (
        set(actual) == set(expected) and all(equal(actual[k], v)
                                            for k, v in expected.items())
        if isinstance(expected, dict) else
        len(actual) == len(expected) and all(equal(a, b)
                                            for a, b in zip(actual, expected))
        if isinstance(expected, list) else actual == expected)


def check_streams(observation, publications, resets, count=COUNT):
    """count override exists solely for explicit SOFTWARE_FIXTURE tests."""
    expected_reset = [dict(time_ns=t, cycle=c, rst_n=r)
                      for t, c, r in RESETS if c < count]
    try:
        got_reset = [read_json(line) for line in resets]
    except json.JSONDecodeError as exc:
        raise ValueError("RESET_JSON") from exc
    if len(got_reset) < len(expected_reset):
        raise Incomplete("RESET_TRAJECTORY_INCOMPLETE")
    if not equal(got_reset, expected_reset):
        raise ValueError("RESET_TRAJECTORY_MISMATCH")
    calendar = Calendar()
    segment_accept = [0] * 5
    segment_publish = [0] * 5
    for cycle in range(count):
        raw = observation.readline()
        if not raw or not raw.endswith("\n"):
            raise Incomplete(f"MISSING_OR_TRUNCATED_EDGE:{cycle}")
        word = raw[:-2] if raw.endswith("\r\n") else raw[:-1]
        if re.fullmatch("[0-9a-f]{75}", word) is None:
            raise ValueError(f"OBS_FORMAT:{cycle}")
        value = int(word, 16)
        row = controls(cycle)
        ports, events = calendar.step(cycle, row)
        expected = (((cycle << 64 | (10 + 20 * cycle)) << 170 | pack(row)) << 34
                    | ports[0] << 33 | ports[1] << 32 | ports[2])
        if value != expected:
            diagnostic = ("INPUT_CYCLE_OR_TIME_MISMATCH" if value >> 34 != expected >> 34
                          else "READY_VALID_ID_MISMATCH")
            raise ValueError(f"{diagnostic}:{cycle}")
        for event in events:
            actual = publications.readline()
            if not actual:
                raise Incomplete(f"MISSING_EVENT:{cycle}:{event['event']}")
            if not equal(read_json(actual), event):
                raise ValueError(f"TRANSACTION_EVENT_MISMATCH:{cycle}")
            if 256 <= cycle < COUNT - 16:
                frame = (cycle - 256) // 1042
                segment = min(frame // 1024, 4)
                if event["event"] == "ACCEPT":
                    segment_accept[segment] += 1
                elif event["event"] == "PUBLISH":
                    segment_publish[segment] += 1
    if observation.readline() not in (f"END {count}\n", f"END {count}\r\n"):
        raise Incomplete("OBS_END_MISSING_OR_WRONG")
    if observation.read():
        raise ValueError("OBS_AFTER_END")
    tail = publications.readline()
    if not tail:
        raise Incomplete("EVENT_END_MISSING")
    if not equal(read_json(tail), calendar.end(count)):
        raise ValueError("EVENT_END_MISMATCH")
    if publications.read():
        raise ValueError("EVENT_AFTER_END")
    if calendar.pending is not None:
        raise Incomplete("OPEN_TRANSACTION")
    if count == COUNT:
        if calendar.end(count) != dict(type="END", rows=COUNT, accepted=8207,
                                       published=8201, cancelled=6, open=0):
            raise ValueError("M1_R01_TOTALS")
        if segment_accept != [1024] * 4 + [4096] or segment_publish != segment_accept:
            raise ValueError("M1_R01_SEGMENTS")
    return dict(**calendar.end(count), plan=VERSION,
                segment_accept=segment_accept, segment_publish=segment_publish,
                PCM_math_verified=False, provenance_verified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("REPORT_EXISTS")
    paths = [args.capture / name for name in
             ("observations.hex", "publications.jsonl", "resets.jsonl")]
    result = dict(plan=VERSION, software_only=True, RTL_execution_by_this_tool=0)
    try:
        before = {str(p): sha(p) for p in paths}
        with paths[0].open(encoding="ascii", newline="") as obs, \
                paths[1].open(encoding="ascii", newline="") as pubs, \
                paths[2].open(encoding="ascii", newline="") as reset:
            result.update(check_streams(obs, pubs, reset))
        if before != {str(p): sha(p) for p in paths}:
            raise ValueError("CAPTURE_DRIFT")
        result.update(status="NOT_VERIFIABLE", diagnostic="PROVENANCE_NOT_VERIFIED",
                      transaction_comparison="PASS", inputs=before)
        code = 3
    except (FileNotFoundError, Incomplete) as exc:
        result.update(status="INCOMPLETE", diagnostic=str(exc))
        code = 3
    except (ValueError, UnicodeError) as exc:
        result.update(status="FAIL", diagnostic=str(exc))
        code = 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(dict(result, exit_code=code), stream, indent=2)
        stream.write("\n")
    print(json.dumps(dict(result, exit_code=code)))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
