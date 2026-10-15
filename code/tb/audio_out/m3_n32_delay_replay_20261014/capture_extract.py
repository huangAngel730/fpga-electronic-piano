#!/usr/bin/env python3
"""Extract real published PCM records from the frozen C_FULL capsule.

The P record does not carry clipped.  A publication is accepted only when a
same-cycle/same-id/same-PCM K record has publish=1; clipped comes from K.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import BinaryIO, Iterable


EXPECTED_OUTER_SHA256 = (
    "eac6e9371a96e91447a75d869d7e7a6dc76252fd89d6c8b621953a396a42c726"
)
EXPECTED_CAPTURE_SHA256 = (
    "daf92770d8b92ec283d9eae726c5a39a8023a28808b0b262376d44c09654c79d"
)
EXPECTED_CAPTURE_BYTES = 45_522_685
EXPECTED_SNAPSHOT_SHA256 = (
    "15372b95e41463ce6dc459269cf5a60134bda1f7434f41ffc50f9ac2e74d0c9e"
)
SNAPSHOT_MEMBER = "C_FULL/snapshot.zip"
CAPTURE_MEMBER = "reused/capture.log"


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class HashingReader(io.RawIOBase):
    def __init__(self, raw: BinaryIO) -> None:
        self.raw = raw
        self.digest = hashlib.sha256()
        self.count = 0

    def readable(self) -> bool:
        return True

    def readinto(self, target: bytearray) -> int:
        data = self.raw.read(len(target))
        size = len(data)
        if size:
            target[:size] = data
            self.digest.update(data)
            self.count += size
        return size


def parse_capture(stream: BinaryIO) -> tuple[list[dict], dict]:
    reader = HashingReader(stream)
    buffered = io.BufferedReader(reader, buffer_size=1024 * 1024)
    life = -1
    reset_records: list[dict] = []
    published_by_life: dict[int, list[dict]] = defaultdict(list)
    pending_k: dict[tuple[int, str], dict] = {}
    line_count = 0
    end_line = None

    for line_count, raw_line in enumerate(buffered, 1):
        try:
            text = raw_line.decode("ascii").strip()
        except UnicodeDecodeError as exc:
            raise ValueError(f"CAPTURE_NON_ASCII line={line_count}") from exc
        if not text:
            continue
        fields = text.split()
        tag = fields[0]
        if tag == "R":
            if len(fields) != 2:
                raise ValueError(f"RESET_FORMAT line={line_count}")
            life += 1
            reset_records.append(
                {"lifetime": life, "line": line_count, "cycle": int(fields[1])}
            )
            pending_k.clear()
        elif tag == "K":
            if len(fields) != 8 or life < 0:
                raise ValueError(f"K_FORMAT line={line_count}")
            cycle = int(fields[1])
            result_id = fields[2].lower()
            record = {
                "lifetime": life,
                "k_line": line_count,
                "cycle": cycle,
                "id_hex": result_id,
                "left": int(fields[3]),
                "right": int(fields[4]),
                "late": int(fields[5]),
                "clipped": int(fields[6]),
                "publish": int(fields[7]),
            }
            if record["clipped"] not in (0, 1) or record["publish"] not in (0, 1):
                raise ValueError(f"K_FLAG_NOT_BINARY line={line_count}")
            if record["publish"] == 1:
                key = (cycle, result_id)
                if key in pending_k:
                    raise ValueError(f"K_DUPLICATE_PUBLISH line={line_count}")
                pending_k[key] = record
        elif tag == "P":
            if len(fields) != 6 or life < 0:
                raise ValueError(f"P_FORMAT line={line_count}")
            cycle = int(fields[1])
            result_id = fields[2].lower()
            key = (cycle, result_id)
            k_record = pending_k.pop(key, None)
            if k_record is None:
                raise ValueError(
                    f"P_WITHOUT_SAME_CYCLE_PUBLISHED_K line={line_count} key={key}"
                )
            left = int(fields[3])
            right = int(fields[4])
            late = int(fields[5])
            if (left, right, late) != (
                k_record["left"],
                k_record["right"],
                k_record["late"],
            ):
                raise ValueError(f"K_P_PAYLOAD_MISMATCH line={line_count}")
            published_by_life[life].append(
                {
                    **k_record,
                    "p_line": line_count,
                    "id": int(result_id, 16),
                }
            )
        elif tag == "END":
            if end_line is not None:
                raise ValueError("MULTIPLE_END")
            end_line = {"line": line_count, "text": text}

    capture_sha = reader.digest.hexdigest()
    if reader.count != EXPECTED_CAPTURE_BYTES:
        raise ValueError(
            f"CAPTURE_BYTES expected={EXPECTED_CAPTURE_BYTES} actual={reader.count}"
        )
    if capture_sha != EXPECTED_CAPTURE_SHA256:
        raise ValueError(
            f"CAPTURE_SHA expected={EXPECTED_CAPTURE_SHA256} actual={capture_sha}"
        )
    if end_line is None:
        raise ValueError("END_MISSING")
    if pending_k:
        raise ValueError(f"UNPAIRED_PUBLISHED_K count={len(pending_k)}")

    lifetime_counts = {str(key): len(value) for key, value in published_by_life.items()}
    all_records = [record for values in published_by_life.values() for record in values]
    summary = {
        "capture_bytes": reader.count,
        "capture_sha256": capture_sha,
        "line_count": line_count,
        "reset_records": reset_records,
        "lifetime_publication_counts": lifetime_counts,
        "publication_count": len(all_records),
        "unequal_stereo_count": sum(r["left"] != r["right"] for r in all_records),
        "clipped_count": sum(r["clipped"] != 0 for r in all_records),
        "end": end_line,
    }
    longest_life = max(published_by_life, key=lambda key: len(published_by_life[key]))
    summary["selected_lifetime"] = longest_life
    summary["selected_lifetime_publications"] = len(published_by_life[longest_life])
    return published_by_life[longest_life], summary


def pack_record(record: dict) -> str:
    for name in ("left", "right"):
        if not -(1 << 23) <= record[name] < (1 << 23):
            raise ValueError(f"PCM24_RANGE field={name} value={record[name]}")
    value = (
        ((record["lifetime"] & 0xFF) << 184)
        | ((record["k_line"] & 0xFFFFFFFF) << 152)
        | ((record["p_line"] & 0xFFFFFFFF) << 120)
        | ((record["cycle"] & 0xFFFFFFFF) << 88)
        | ((record["id"] & 0xFFFFFFFF) << 56)
        | ((record["left"] & 0xFFFFFF) << 32)
        | ((record["right"] & 0xFFFFFF) << 8)
        | ((record["clipped"] & 1) << 7)
    )
    return f"{value:048x}"


def write_outputs(records: Iterable[dict], output_dir: Path, count: int, summary: dict) -> dict:
    records = list(records)
    if len(records) < count:
        raise ValueError(f"NOT_ENOUGH_ONE_LIFETIME requested={count} actual={len(records)}")
    chosen = records[:count]
    output_dir.mkdir(parents=True, exist_ok=False)
    mem_path = output_dir / "real_publish.mem"
    jsonl_path = output_dir / "real_publish.jsonl"
    mem_path.write_text("\n".join(pack_record(r) for r in chosen) + "\n", encoding="ascii")
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as stream:
        for index, record in enumerate(chosen):
            stream.write(json.dumps({"index": index, **record}, sort_keys=True) + "\n")
    receipt = {
        "status": "PASS",
        "selection": {
            "count": count,
            "lifetime": summary["selected_lifetime"],
            "first": chosen[0],
            "last": chosen[-1],
            "same_lifetime": len({r["lifetime"] for r in chosen}) == 1,
            "source_ids_unique": len({r["id"] for r in chosen}) == count,
            "unequal_stereo_count": sum(r["left"] != r["right"] for r in chosen),
            "clipped_count": sum(r["clipped"] != 0 for r in chosen),
        },
        "capture": summary,
        "outputs": {
            mem_path.name: {"bytes": mem_path.stat().st_size, "sha256": sha256_path(mem_path)},
            jsonl_path.name: {
                "bytes": jsonl_path.stat().st_size,
                "sha256": sha256_path(jsonl_path),
            },
        },
    }
    receipt_path = output_dir / "extraction_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def extract(outer_zip: Path, output_dir: Path, count: int) -> dict:
    outer_sha = sha256_path(outer_zip)
    if outer_sha != EXPECTED_OUTER_SHA256:
        raise ValueError(f"OUTER_SHA expected={EXPECTED_OUTER_SHA256} actual={outer_sha}")
    with zipfile.ZipFile(outer_zip) as outer:
        outer_manifest = json.loads(outer.read("MANIFEST.json"))
        snapshot_bytes = outer.read(SNAPSHOT_MEMBER)
    snapshot_sha = sha256_bytes(snapshot_bytes)
    if snapshot_sha != EXPECTED_SNAPSHOT_SHA256:
        raise ValueError(
            f"SNAPSHOT_SHA expected={EXPECTED_SNAPSHOT_SHA256} actual={snapshot_sha}"
        )
    manifest_entry = outer_manifest["files"][SNAPSHOT_MEMBER]
    if manifest_entry["sha256"] != snapshot_sha or manifest_entry["bytes"] != len(snapshot_bytes):
        raise ValueError("OUTER_MANIFEST_SNAPSHOT_MISMATCH")
    with zipfile.ZipFile(io.BytesIO(snapshot_bytes)) as snapshot:
        nested_manifest = json.loads(snapshot.read("MANIFEST.json"))
        capture_entry = nested_manifest["files"][CAPTURE_MEMBER]
        if capture_entry != {
            "bytes": EXPECTED_CAPTURE_BYTES,
            "sha256": EXPECTED_CAPTURE_SHA256,
        }:
            raise ValueError("NESTED_MANIFEST_CAPTURE_MISMATCH")
        with snapshot.open(CAPTURE_MEMBER) as capture:
            records, summary = parse_capture(capture)
    receipt = write_outputs(records, output_dir, count, summary)
    receipt["outer_zip"] = {
        "path": outer_zip.as_posix(),
        "bytes": outer_zip.stat().st_size,
        "sha256": outer_sha,
    }
    receipt["snapshot"] = {"bytes": len(snapshot_bytes), "sha256": snapshot_sha}
    receipt_path = output_dir / "extraction_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outer-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--count", type=int, default=1300)
    args = parser.parse_args()
    receipt = extract(args.outer_zip.resolve(), args.output_dir.resolve(), args.count)
    print(json.dumps({"status": receipt["status"], "selection": receipt["selection"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
