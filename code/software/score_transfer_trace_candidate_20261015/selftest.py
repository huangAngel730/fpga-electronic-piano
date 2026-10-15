"""Independent synthetic fixtures and CLI self-test for score_trace_verify.py."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import zipfile


MAGIC = b"\xa5\x5a"
HEADER = struct.Struct("<BBHHHH")
META = struct.Struct("<BBBBHIH")
BEGIN, DATA, COMMIT, ABORT, STATUS, READ = range(1, 7)
ACK, NACK = 0x80, 0x81


def independent_crc(data: bytes) -> int:
    value = 0xFFFF
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            value = ((value << 1) ^ (0x1021 if value & 0x8000 else 0)) & 0xFFFF
    return value


def independent_frame(command: int, session: int, seq: int, offset: int = 0,
                      payload: bytes = b"", version: int = 1) -> bytes:
    body = HEADER.pack(version, command, session, seq, offset, len(payload)) + payload
    return MAGIC + body + independent_crc(body).to_bytes(2, "little")


def score(score_id: int, notes: list[int] | None = None) -> dict:
    notes = notes or [60, 64, 67]
    return {
        "schema": 1,
        "sample_hz": 48000,
        "score_id": score_id,
        "events": [
            {"tick": index * 2400, "type": "note_on" if index < len(notes) - 1 else "note_off",
             "channel": index % 4, "note": note, "velocity": 90 if index < len(notes) - 1 else 0}
            for index, note in enumerate(notes)
        ],
    }


def independent_records(document: dict) -> bytes:
    result = bytearray()
    for event in document["events"]:
        kind = int(event["type"] == "note_off" or event["velocity"] == 0)
        result.extend(struct.pack("<IBBBB", event["tick"], kind, event["channel"],
                                  event["note"], event["velocity"]))
    return bytes(result)


class Trace:
    def __init__(self, start_us: int = 1_000_000):
        self.items: list[dict] = []
        self.now = start_us

    def add(self, direction: str, raw: bytes, *, advance_us: int = 1000,
            label: str | None = None) -> None:
        byte_times = [self.now + 87 * index for index in range(len(raw))]
        item = {"direction": direction, "data": raw,
                "timestamp_us": self.now, "byte_times_us": byte_times,
                "label": label}
        self.items.append(item)
        self.now = byte_times[-1] + advance_us

    def extend(self, other: "Trace") -> None:
        if not other.items:
            return
        shift = self.now - other.items[0]["timestamp_us"]
        for item in other.items:
            copied = dict(item)
            copied["timestamp_us"] += shift
            copied["byte_times_us"] = [value + shift for value in item["byte_times_us"]]
            self.items.append(copied)
        self.now = self.items[-1]["byte_times_us"][-1] + 1000

    def write_jsonl(self, path: Path, mode: str = "normal", prefix_noise: bool = False) -> None:
        lines: list[dict] = []
        if mode == "coalesce":
            grouped: list[dict] = []
            for item in self.items:
                if grouped and grouped[-1]["direction"] == item["direction"]:
                    grouped[-1]["data"] += item["data"]
                    grouped[-1]["byte_times_us"] += item["byte_times_us"]
                    grouped[-1]["label"] = str(grouped[-1]["label"]) + "+" + str(item["label"])
                else:
                    grouped.append(dict(item))
            source_items = grouped
        else:
            source_items = self.items
        for index, item in enumerate(source_items):
            raw = item["data"]
            byte_times = list(item["byte_times_us"])
            if prefix_noise and index == 0:
                noise = b"\x00\xffgarbage"
                first = byte_times[0]
                noise_times = [first - 87 * (len(noise) - offset)
                               for offset in range(len(noise))]
                raw = noise + raw
                byte_times = noise_times + byte_times
            if mode == "fragment":
                positions = [0, 1, 3, 7, 12, len(raw) - 1, len(raw)]
                positions = sorted(set(max(0, min(len(raw), value)) for value in positions))
                for part_index, (start, end) in enumerate(zip(positions, positions[1:])):
                    if start == end:
                        continue
                    lines.append({"direction": item["direction"],
                                  "data_hex": raw[start:end].hex(),
                                  "timestamp_us": byte_times[start],
                                  "byte_times_us": byte_times[start:end],
                                  "label": item["label"] or f"fragment_{index}"})
            else:
                lines.append({"direction": item["direction"], "data_hex": raw.hex(),
                              "timestamp_us": byte_times[0],
                              "byte_times_us": byte_times,
                              "label": item["label"] or f"frame_{index}"})
        path.write_text("".join(json.dumps(line, sort_keys=True) + "\n" for line in lines),
                        encoding="utf-8")

    def streams(self) -> tuple[bytes, bytes]:
        return (b"".join(item["data"] for item in self.items if item["direction"] == "tx"),
                b"".join(item["data"] for item in self.items if item["direction"] == "rx"))

    def retime(self, gap_us: int = 1000) -> None:
        now = 1_000_000
        for item in self.items:
            item["timestamp_us"] = now
            item["byte_times_us"] = [now + 87 * index for index in range(len(item["data"]))]
            now = item["byte_times_us"][-1] + gap_us
        self.now = now


def response(request: bytes, command: int, meta: tuple[int, int, int, int, int, int, int],
             event: bytes = b"") -> bytes:
    _, _, session, seq, offset, _ = HEADER.unpack(request[2:12])
    return independent_frame(command, session, seq, offset, META.pack(*meta) + event)


def successful_upload(document: dict, session: int, *, retransmit: bool = False,
                      duplicate_response: bool = False, replay_commit: bool = False,
                      chunk_sizes: list[int] | None = None,
                      prior_document: dict | None = None) -> Trace:
    records = independent_records(document)
    chunks = chunk_sizes or [5, len(records) - 5]
    trace = Trace()
    begin_payload = struct.pack("<IHHHI", document["score_id"], len(records) // 8,
                                len(records), independent_crc(records), 48000)
    begin = independent_frame(BEGIN, session, 0, payload=begin_payload)
    trace.add("tx", begin, advance_us=500_001 if retransmit else 1000, label="begin")
    if retransmit:
        trace.add("tx", begin, advance_us=1000, label="begin_retry")
    prior_records = independent_records(prior_document) if prior_document is not None else b""
    prior_valid = int(prior_document is not None)
    prior_count = len(prior_records) // 8
    prior_score_id = prior_document["score_id"] if prior_document is not None else 0
    begin_ack = response(begin, ACK, (BEGIN, 0, prior_valid, 1,
                                      prior_count, prior_score_id, 0))
    trace.add("rx", begin_ack, label="begin_ack")
    if duplicate_response:
        trace.add("rx", begin_ack, label="duplicate_begin_ack")
    at = 0
    seq = 1
    for size in chunks:
        if size <= 0:
            continue
        part = records[at:at + size]
        request = independent_frame(DATA, session, seq, at, part)
        trace.add("tx", request, label=f"data_{seq}")
        at += len(part)
        trace.add("rx", response(request, ACK,
                                  (DATA, 0, prior_valid, 1,
                                   prior_count, prior_score_id, at)), label=f"data_{seq}_ack")
        seq += 1
    commit = independent_frame(COMMIT, session, seq)
    commit_ack = response(commit, ACK,
                          (COMMIT, 0, 1, 0, len(records) // 8,
                           document["score_id"], len(records)))
    trace.add("tx", commit, label="commit")
    trace.add("rx", commit_ack, label="commit_ack")
    if replay_commit:
        trace.add("tx", commit, label="commit_retry")
        trace.add("rx", commit_ack, label="commit_ack_replay")
    status = independent_frame(STATUS, session, 0)
    state = (STATUS, 0, 1, 0, len(records) // 8,
             document["score_id"], len(records))
    trace.add("tx", status, label="status")
    trace.add("rx", response(status, ACK, state), label="status_ack")
    for index in range(len(records) // 8):
        read = independent_frame(READ, session, index, index)
        trace.add("tx", read, label=f"read_{index}")
        trace.add("rx", response(read, ACK,
                                  (READ, 0, 1, 0, len(records) // 8,
                                   document["score_id"], len(records)),
                                  records[8 * index:8 * index + 8]),
                  label=f"read_{index}_ack")
    return trace


def abort_then_recover(document: dict, session: int) -> Trace:
    records = independent_records(document)
    trace = Trace()
    begin_payload = struct.pack("<IHHHI", document["score_id"], len(records) // 8,
                                len(records), independent_crc(records), 48000)
    begin = independent_frame(BEGIN, session, 0, payload=begin_payload)
    trace.add("tx", begin, label="aborted_begin")
    trace.add("rx", response(begin, ACK, (BEGIN, 0, 0, 1, 0, 0, 0)), label="aborted_begin_ack")
    data = independent_frame(DATA, session, 1, 0, records[:5])
    trace.add("tx", data, label="aborted_data")
    trace.add("rx", response(data, ACK, (DATA, 0, 0, 1, 0, 0, 5)), label="aborted_data_ack")
    abort = independent_frame(ABORT, 0xBEEF, 0x1234)
    trace.add("tx", abort, label="abort_unrestricted_identity")
    trace.add("rx", response(abort, ACK, (ABORT, 0, 0, 0, 0, 0, 0)), label="abort_ack")
    trace.extend(successful_upload(document, session + 1))
    return trace


def mutate_frame(raw: bytes, *, session: int | None = None, seq: int | None = None,
                 offset: int | None = None, payload: bytes | None = None,
                 version: int | None = None) -> bytes:
    old_version, command, old_session, old_seq, old_offset, _ = HEADER.unpack(raw[2:12])
    return independent_frame(command, old_session if session is None else session,
                             old_seq if seq is None else seq,
                             old_offset if offset is None else offset,
                             raw[12:-2] if payload is None else payload,
                             old_version if version is None else version)


def write_expected(path: Path, documents: list[tuple[int, dict]]) -> None:
    if len(documents) == 1:
        path.write_text(json.dumps(documents[0][1], indent=2) + "\n", encoding="utf-8")
    else:
        bundle = {"schema": 1,
                  "transactions": [{"session": session, "score": document}
                                   for session, document in documents]}
        path.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")


def finding_codes(report: dict) -> set[str]:
    return {item["code"] for item in report["findings"]}


def run_case(root: Path, name: str, arguments: list[str], expected_exit: int,
             expected_status: str, required_codes: set[str] | None = None) -> dict:
    case_dir = root / name
    result_dir = case_dir / "result"
    command = [sys.executable, "-B", "-X", "utf8",
               str(Path(__file__).with_name("score_trace_verify.py")),
               *arguments, "--output", str(result_dir)]
    completed = subprocess.run(command, cwd=Path(__file__).resolve().parents[3],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    (case_dir / "stdout.bin").write_bytes(completed.stdout)
    (case_dir / "stderr.bin").write_bytes(completed.stderr)
    if not (result_dir / "report.json").is_file():
        raise AssertionError(f"{name}: report missing; stderr={completed.stderr!r}")
    report = json.loads((result_dir / "report.json").read_text(encoding="utf-8"))
    codes = finding_codes(report)
    if completed.returncode != expected_exit or report["status"] != expected_status:
        raise AssertionError(
            f"{name}: exit/status {completed.returncode}/{report['status']} != "
            f"{expected_exit}/{expected_status}; codes={sorted(codes)}"
        )
    missing = (required_codes or set()) - codes
    if missing:
        raise AssertionError(f"{name}: missing diagnostics {sorted(missing)}; got {sorted(codes)}")
    return {"name": name, "command": command, "exit_code": completed.returncode,
            "status": report["status"], "finding_codes": sorted(codes),
            "required_codes": sorted(required_codes or set()),
            "input_sha256": {item["role"]: item["sha256"]
                              for item in report["file_identities"]},
            "report_sha256": hashlib.sha256((result_dir / "report.json").read_bytes()).hexdigest()}


def prepare_case(root: Path, name: str, trace: Trace | None,
                 expected: list[tuple[int, dict]] | None, *, mode: str = "normal",
                 prefix_noise: bool = False) -> tuple[Path | None, Path | None]:
    case_dir = root / name
    case_dir.mkdir()
    trace_path = None
    expected_path = None
    if trace is not None:
        trace_path = case_dir / "trace.jsonl"
        trace.write_jsonl(trace_path, mode=mode, prefix_noise=prefix_noise)
    if expected is not None:
        expected_path = case_dir / "expected.json"
        write_expected(expected_path, expected)
    return trace_path, expected_path


def replace_item_frame(trace: Trace, predicate, new_raw) -> None:
    for item in trace.items:
        if predicate(item):
            item["data"] = new_raw(item["data"])
            trace.retime()
            return
    raise AssertionError("fixture frame not found")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output
    if root.exists():
        raise SystemExit("output already exists; refuse overwrite")
    root.mkdir(parents=True)
    results: list[dict] = []
    score_a = score(0x10203040)
    score_b = score(0x55667788, [72, 71, 69, 67])

    def execute(name: str, trace: Trace, expected: list[tuple[int, dict]] | None,
                expected_exit: int, expected_status: str, codes: set[str] | None = None,
                *, parser_mode: str = "strict", write_mode: str = "normal",
                prefix_noise: bool = False) -> None:
        trace_path, expected_path = prepare_case(root, name, trace, expected,
                                                 mode=write_mode, prefix_noise=prefix_noise)
        argv = ["--trace", str(trace_path), "--mode", parser_mode]
        if expected_path:
            argv += ["--expected-json", str(expected_path)]
        results.append(run_case(root, name, argv, expected_exit, expected_status, codes))

    execute("positive_normal", successful_upload(score_a, 7), [(7, score_a)], 0, "PASS")
    execute("positive_fragmented", successful_upload(score_a, 7), [(7, score_a)], 0, "PASS",
            write_mode="fragment")
    execute("positive_coalesced_retry", successful_upload(score_a, 7, retransmit=True),
            [(7, score_a)], 0, "PASS", write_mode="coalesce")
    execute("positive_non_aligned_chunks", successful_upload(score_b, 9, chunk_sizes=[3, 7, 11, 11]),
            [(9, score_b)], 0, "PASS")
    execute("positive_replay_commit", successful_upload(score_a, 7, replay_commit=True),
            [(7, score_a)], 0, "PASS")
    execute("positive_duplicate_response", successful_upload(score_a, 7, duplicate_response=True),
            [(7, score_a)], 0, "RECOVERED", {"DUPLICATE_RESPONSE"})
    execute("positive_noise_recover", successful_upload(score_a, 7), [(7, score_a)],
            0, "RECOVERED", {"RECOVERED_NOISE"}, parser_mode="recover", prefix_noise=True)
    execute("negative_noise_strict", successful_upload(score_a, 7), [(7, score_a)],
            2, "INVALID", {"UNEXPECTED_NOISE"}, prefix_noise=True)
    execute("positive_abort_recovery", abort_then_recover(score_a, 10), [(11, score_a)], 0, "PASS")
    multi = successful_upload(score_a, 12)
    multi.extend(successful_upload(score_b, 13, prior_document=score_a))
    execute("positive_multi_transaction", multi, [(12, score_a), (13, score_b)], 0, "PASS")

    crc_bad = successful_upload(score_a, 7)
    replace_item_frame(crc_bad, lambda item: item["label"] == "data_1",
                       lambda raw: raw[:-1] + bytes([raw[-1] ^ 1]))
    execute("negative_crc", crc_bad, [(7, score_a)], 2, "INVALID", {"FRAME_CRC"},
            parser_mode="recover")

    truncated_dir = root / "negative_truncated"
    truncated_dir.mkdir()
    full_begin = successful_upload(score_a, 7).items[0]["data"]
    truncated_trace = truncated_dir / "trace.jsonl"
    truncated_trace.write_text(json.dumps({"direction": "tx", "data_hex": full_begin[:9].hex(),
                                           "timestamp_us": 0}) + "\n", encoding="utf-8")
    results.append(run_case(root, "negative_truncated",
                            ["--trace", str(truncated_trace)], 3, "INCOMPLETE",
                            {"TRUNCATED_FRAME"}))

    oversize_dir = root / "negative_oversize_length"
    oversize_dir.mkdir()
    oversize = MAGIC + HEADER.pack(1, BEGIN, 7, 0, 0, 129) + b"x"
    oversize_trace = oversize_dir / "trace.jsonl"
    oversize_trace.write_text(json.dumps({"direction": "tx", "data_hex": oversize.hex(),
                                          "timestamp_us": 0}) + "\n", encoding="utf-8")
    results.append(run_case(root, "negative_oversize_length",
                            ["--trace", str(oversize_trace), "--mode", "recover"],
                            2, "INVALID", {"FRAME_LENGTH_OVERSIZE", "OVERSIZE_NO_IDLE"}))

    version_bad = successful_upload(score_a, 7)
    replace_item_frame(version_bad, lambda item: item["label"] == "begin",
                       lambda raw: mutate_frame(raw, version=2))
    execute("negative_version", version_bad, [(7, score_a)], 2, "INVALID", {"FRAME_VERSION"})

    wrong_session = successful_upload(score_a, 7)
    replace_item_frame(wrong_session, lambda item: item["label"] == "data_1",
                       lambda raw: mutate_frame(raw, session=8))
    replace_item_frame(wrong_session, lambda item: item["label"] == "data_1_ack",
                       lambda raw: mutate_frame(raw, session=8))
    execute("negative_wrong_session", wrong_session, [(7, score_a)], 2, "INVALID",
            {"ACKED_INVALID_DATA"})

    wrong_seq = successful_upload(score_a, 7)
    replace_item_frame(wrong_seq, lambda item: item["label"] == "data_1",
                       lambda raw: mutate_frame(raw, seq=3))
    replace_item_frame(wrong_seq, lambda item: item["label"] == "data_1_ack",
                       lambda raw: mutate_frame(raw, seq=3))
    execute("negative_wrong_seq", wrong_seq, [(7, score_a)], 2, "INVALID",
            {"ACKED_INVALID_DATA"})

    wrong_offset = successful_upload(score_a, 7)
    replace_item_frame(wrong_offset, lambda item: item["label"] == "data_1",
                       lambda raw: mutate_frame(raw, offset=1))
    replace_item_frame(wrong_offset, lambda item: item["label"] == "data_1_ack",
                       lambda raw: mutate_frame(raw, offset=1))
    execute("negative_wrong_offset", wrong_offset, [(7, score_a)], 2, "INVALID",
            {"ACKED_INVALID_DATA"})

    ack_mismatch = successful_upload(score_a, 7)
    replace_item_frame(ack_mismatch, lambda item: item["label"] == "data_1_ack",
                       lambda raw: mutate_frame(raw, session=99))
    execute("negative_ack_identity", ack_mismatch, [(7, score_a)], 2, "INVALID",
            {"ACK_IDENTITY_MISMATCH"})

    read_bad = successful_upload(score_a, 7)
    replace_item_frame(read_bad, lambda item: item["label"] == "read_1_ack",
                       lambda raw: mutate_frame(raw, payload=raw[12:24] + b"\xff" * 8))
    execute("negative_readback_mismatch", read_bad, [(7, score_a)], 2, "INVALID",
            {"READBACK_MISMATCH"})

    upload_bad_expected = json.loads(json.dumps(score_a))
    upload_bad_expected["events"][0]["note"] = 61
    execute("negative_upload_expected_mismatch", successful_upload(score_a, 7),
            [(7, upload_bad_expected)], 2, "INVALID", {"UPLOAD_CONTENT_MISMATCH"})

    mid = successful_upload(score_a, 7)
    mid.items = mid.items[:4]
    execute("negative_midstream_end", mid, None, 3, "INCOMPLETE",
            {"ACTIVE_UPLOAD_INCOMPLETE", "EXPECTED_MISSING"})

    nack = Trace()
    bad_read = independent_frame(READ, 7, 0, 0)
    nack.add("tx", bad_read, label="bad_read")
    nack.add("rx", response(bad_read, NACK, (READ, 13, 0, 0, 0, 0, 0)), label="nack13")
    execute("negative_nack_terminal", nack, None, 2, "INVALID",
            {"NACK_RECEIVED", "EXPECTED_MISSING"})

    divergence = Trace()
    divergence_records = independent_records(score_a)
    divergence_begin = independent_frame(
        BEGIN, 21, 0,
        payload=struct.pack("<IHHHI", score_a["score_id"], len(divergence_records) // 8,
                            len(divergence_records), independent_crc(divergence_records), 48000),
    )
    divergence.add("tx", divergence_begin, label="begin")
    divergence.add("rx", response(divergence_begin, ACK, (BEGIN, 0, 0, 1, 0, 0, 0)),
                   label="begin_ack")
    early_commit = independent_frame(COMMIT, 21, 1)
    divergence.add("tx", early_commit, label="incomplete_commit")
    divergence.add("rx", response(early_commit, NACK, (COMMIT, 8, 0, 1, 0, 0, 0)),
                   label="nack8_session_retained")
    execute("negative_commit_nack8_contract_divergence", divergence, None, 2, "INVALID",
            {"CONTRACT_IMPLEMENTATION_DIVERGENCE_COMMIT_NACK8_SESSION"})

    shape_bad = successful_upload(score_a, 7)
    replace_item_frame(shape_bad, lambda item: item["label"] == "status_ack",
                       lambda raw: mutate_frame(raw, payload=raw[12:-2] + b"\x00" * 8))
    execute("negative_non_read_20byte_response", shape_bad, [(7, score_a)], 2, "INVALID",
            {"RESPONSE_SHAPE"})

    missing_expected = successful_upload(score_a, 7)
    execute("not_verifiable_missing_expected", missing_expected, None, 4, "NOT_VERIFIABLE",
            {"EXPECTED_MISSING"})

    separate_dir = root / "not_verifiable_separate_streams"
    separate_dir.mkdir()
    separate = successful_upload(score_a, 7)
    tx, rx = separate.streams()
    tx_path, rx_path = separate_dir / "tx.bin", separate_dir / "rx.bin"
    tx_path.write_bytes(tx)
    rx_path.write_bytes(rx)
    expected_path = separate_dir / "expected.json"
    write_expected(expected_path, [(7, score_a)])
    results.append(run_case(root, "not_verifiable_separate_streams",
                            ["--tx", str(tx_path), "--rx", str(rx_path),
                             "--expected-json", str(expected_path)], 4, "NOT_VERIFIABLE",
                            {"INTERLEAVING_NOT_VERIFIABLE", "TIMING_NOT_VERIFIABLE"}))

    no_time_dir = root / "not_verifiable_no_timestamps"
    no_time_dir.mkdir()
    no_time_trace = no_time_dir / "trace.jsonl"
    no_time_trace.write_text("".join(json.dumps({"direction": item["direction"],
                                                   "data_hex": item["data"].hex()}) + "\n"
                                           for item in successful_upload(score_a, 7).items),
                                  encoding="utf-8")
    no_time_expected = no_time_dir / "expected.json"
    write_expected(no_time_expected, [(7, score_a)])
    results.append(run_case(root, "not_verifiable_no_timestamps",
                            ["--trace", str(no_time_trace), "--expected-json", str(no_time_expected)],
                            4, "NOT_VERIFIABLE", {"TIMING_NOT_VERIFIABLE"}))

    chunk_time_dir = root / "not_verifiable_chunk_timestamps"
    chunk_time_dir.mkdir()
    chunk_time_trace = chunk_time_dir / "trace.jsonl"
    chunk_time_trace.write_text(
        "".join(json.dumps({"direction": item["direction"],
                            "data_hex": item["data"].hex(),
                            "timestamp_us": item["timestamp_us"]}) + "\n"
                for item in successful_upload(score_a, 7).items),
        encoding="utf-8",
    )
    chunk_time_expected = chunk_time_dir / "expected.json"
    write_expected(chunk_time_expected, [(7, score_a)])
    results.append(run_case(
        root, "not_verifiable_chunk_timestamps",
        ["--trace", str(chunk_time_trace), "--expected-json", str(chunk_time_expected)],
        4, "NOT_VERIFIABLE", {"TIMING_NOT_VERIFIABLE"},
    ))

    late = successful_upload(score_a, 7, duplicate_response=True)
    late_duplicate = next(item for item in late.items if item["label"] == "duplicate_begin_ack")
    late.items.remove(late_duplicate)
    data_index = next(index for index, item in enumerate(late.items)
                      if item["label"] == "data_1")
    late.items.insert(data_index + 1, late_duplicate)
    late.retime()
    execute("positive_late_duplicate_response", late, [(7, score_a)], 0, "RECOVERED",
            {"LATE_DUPLICATE_RESPONSE"})

    pending_body = successful_upload(score_a, 7)
    data_index = next(index for index, item in enumerate(pending_body.items)
                      if item["label"] == "data_1")
    original_data = pending_body.items[data_index]
    changed_data = dict(original_data)
    changed_data["data"] = mutate_frame(original_data["data"], payload=b"\xaa")
    changed_data["label"] = "same_identity_changed_body_while_pending"
    changed_data["byte_times_us"] = [changed_data["timestamp_us"] + 87 * index
                                      for index in range(len(changed_data["data"]))]
    pending_body.items.insert(data_index + 1, changed_data)
    pending_body.retime()
    execute("negative_same_identity_changed_body_pending", pending_body, [(7, score_a)],
            2, "INVALID", {"STOP_WAIT_VIOLATION"})

    after_success_body = successful_upload(score_a, 7)
    records_a = independent_records(score_a)
    altered_read = independent_frame(READ, 7, 2, 2, b"\x01")
    after_success_body.add("tx", altered_read, label="same_identity_changed_body_after_success")
    after_success_body.add(
        "rx",
        response(altered_read, ACK,
                 (READ, 0, 1, 0, len(records_a) // 8, score_a["score_id"], 0),
                 records_a[16:24]),
        label="changed_body_ack",
    )
    execute("negative_same_identity_changed_body_after_success", after_success_body,
            [(7, score_a)], 2, "INVALID", {"ACKED_INVALID_READ"})

    read_missing = successful_upload(score_a, 7)
    replace_item_frame(read_missing, lambda item: item["label"] == "read_1_ack",
                       lambda raw: mutate_frame(raw, payload=raw[12:24]))
    execute("negative_read_ack_missing_event", read_missing, [(7, score_a)],
            2, "INVALID", {"RESPONSE_SHAPE"})

    read_nack_extra = successful_upload(score_a, 7)
    replace_item_frame(
        read_nack_extra, lambda item: item["label"] == "read_1_ack",
        lambda raw: response(raw, NACK,
                             (READ, 13, 1, 0, 3, score_a["score_id"], 0), b"\x00" * 8),
    )
    execute("negative_read_nack_extra_event", read_nack_extra, [(7, score_a)],
            2, "INVALID", {"RESPONSE_SHAPE"})

    ack_error = successful_upload(score_a, 7)
    replace_item_frame(
        ack_error, lambda item: item["label"] == "status_ack",
        lambda raw: response(raw, ACK, (STATUS, 1, 1, 0, 3, score_a["score_id"], 0)),
    )
    execute("negative_ack_nonzero_error", ack_error, [(7, score_a)],
            2, "INVALID", {"ACK_NONZERO_ERROR"})

    nack_zero = successful_upload(score_a, 7)
    replace_item_frame(
        nack_zero, lambda item: item["label"] == "status_ack",
        lambda raw: response(raw, NACK, (STATUS, 0, 1, 0, 3, score_a["score_id"], 0)),
    )
    execute("negative_nack_zero_error", nack_zero, [(7, score_a)],
            2, "INVALID", {"NACK_ZERO_ERROR"})

    original_cmd = successful_upload(score_a, 7)
    replace_item_frame(
        original_cmd, lambda item: item["label"] == "status_ack",
        lambda raw: response(raw, ACK, (READ, 0, 1, 0, 3, score_a["score_id"], 0)),
    )
    execute("negative_response_original_command", original_cmd, [(7, score_a)],
            2, "INVALID", {"ACK_COMMAND_MISMATCH"})

    nack_recover = Trace()
    bad_status = independent_frame(STATUS, 30, 0)
    nack_recover.add("tx", bad_status, label="nacked_status")
    nack_recover.add("rx", response(bad_status, NACK, (STATUS, 5, 0, 0, 0, 0, 0)),
                     label="nack5")
    nack_recover.extend(successful_upload(score_a, 31))
    execute("negative_nack_then_successful_recovery", nack_recover, [(31, score_a)],
            2, "INVALID", {"NACK_RECEIVED", "RECOVERY_AFTER_NACK_OBSERVED"})

    early_retry = successful_upload(score_a, 7, retransmit=True)
    first = next(item for item in early_retry.items if item["label"] == "begin")
    retry = next(item for item in early_retry.items if item["label"] == "begin_retry")
    shift = retry["timestamp_us"] - (first["byte_times_us"][-1] + 1000)
    for item in early_retry.items[early_retry.items.index(retry):]:
        item["timestamp_us"] -= shift
        item["byte_times_us"] = [value - shift for value in item["byte_times_us"]]
    execute("negative_retry_too_early", early_retry, [(7, score_a)],
            2, "INVALID", {"RETRY_TOO_EARLY"})

    golden = Trace()
    golden.add("tx", bytes.fromhex("a55a0104efbe3412000000006012"), label="fixed_golden_abort")
    golden.add("rx", bytes.fromhex(
        "a55a0180efbe341200000c000400000000000000000000005895"
    ), label="fixed_golden_abort_ack")
    golden.extend(successful_upload(score_a, 7))
    execute("positive_fixed_hex_golden", golden, [(7, score_a)], 0, "PASS")

    bad_hex_dir = root / "negative_malformed_hex"
    bad_hex_dir.mkdir()
    bad_hex_path = bad_hex_dir / "trace.jsonl"
    bad_hex_path.write_text('{"direction":"tx","data_hex":"xyz"}\n', encoding="utf-8")
    results.append(run_case(root, "negative_malformed_hex",
                            ["--trace", str(bad_hex_path)], 2, "INVALID",
                            {"INPUT_FORMAT_ERROR"}))

    duplicate_json_dir = root / "negative_duplicate_json_field"
    duplicate_json_dir.mkdir()
    duplicate_json_path = duplicate_json_dir / "trace.jsonl"
    duplicate_json_path.write_text(
        '{"direction":"tx","direction":"rx","data_hex":"00"}\n',
        encoding="utf-8",
    )
    results.append(run_case(root, "negative_duplicate_json_field",
                            ["--trace", str(duplicate_json_path)], 2, "INVALID",
                            {"INPUT_FORMAT_ERROR"}))

    session_zero_dir = root / "negative_expected_session_zero"
    session_zero_dir.mkdir()
    session_zero_trace = session_zero_dir / "trace.jsonl"
    successful_upload(score_a, 7).write_jsonl(session_zero_trace)
    session_zero_expected = session_zero_dir / "expected.json"
    write_expected(session_zero_expected, [(0, score_a), (7, score_a)])
    results.append(run_case(root, "negative_expected_session_zero",
                            ["--trace", str(session_zero_trace),
                             "--expected-json", str(session_zero_expected)],
                            2, "INVALID", {"INPUT_FORMAT_ERROR"}))

    capacity_dir = root / "negative_expected_records_capacity"
    capacity_dir.mkdir()
    capacity_trace = capacity_dir / "trace.jsonl"
    successful_upload(score_a, 7).write_jsonl(capacity_trace)
    capacity_records = capacity_dir / "records.bin"
    capacity_records.write_bytes(b"".join(struct.pack("<IBBBB", index, 1, 0, 60, 0)
                                             for index in range(513)))
    results.append(run_case(root, "negative_expected_records_capacity",
                            ["--trace", str(capacity_trace),
                             "--expected-records", str(capacity_records),
                             "--score-id", "1"],
                            2, "INVALID", {"INPUT_FORMAT_ERROR"}))

    source_paths = [Path(__file__), Path(__file__).with_name("score_trace_verify.py")]
    receipt = {
        "schema": 1,
        "status": "PASS",
        "validation_level": "offline_software_synthetic_fixtures",
        "invocation": [sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve()),
                       "--output", str(root)],
        "cwd": str(Path.cwd()),
        "scenario_count": len(results),
        "scenarios": results,
        "source_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in source_paths},
        "crc_golden": independent_crc(b"123456789"),
        "coverage": [
            "complete_upload_status_full_readback", "fragmentation", "coalesced_retry",
            "leading_noise_strict_and_recover", "crc", "truncation", "oversize_length",
            "version", "session", "sequence", "offset", "ack_identity", "retransmission",
            "duplicate_response", "abort_recovery", "nack", "midstream_end",
            "upload_mismatch", "readback_mismatch", "multi_transaction",
            "cross_session", "separate_streams", "missing_timestamps", "missing_expected",
            "commit_nack8_contract_divergence", "response_shape_strictness",
            "exact_per_byte_timing", "late_duplicate_does_not_consume_pending",
            "same_identity_different_body_not_replay", "nack_cannot_be_washed_to_pass",
            "malformed_input_structured_report", "expected_input_bounds",
            "fixed_hex_golden_frame",
        ],
        "hardware_verified": False,
        "rtl_simulation_run": False,
        "serial_opened": False,
    }
    receipt_path = root / "selftest_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name not in ("manifest.json", "evidence.zip"):
            data = path.read_bytes()
            manifest[path.relative_to(root).as_posix()] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with zipfile.ZipFile(root / "evidence.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.name != "evidence.zip":
                archive.write(path, path.relative_to(root).as_posix())
    print(f"PASS offline selftest scenarios={len(results)} output={root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
