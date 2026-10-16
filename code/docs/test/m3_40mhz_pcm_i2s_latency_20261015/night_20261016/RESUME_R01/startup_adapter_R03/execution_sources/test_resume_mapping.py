"""New flat-source-layout guards only. No old suite or simulator execution."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from consume_capture import sha256
from consume_real import verify_source_snapshots


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    run = args.output / "SYNTHETIC_RUN"
    (run / "source").mkdir(parents=True)
    receipt_path = run / "SYNTHETIC_RECEIPT.json"
    before, mapping = {}, {}
    for relative, data in (("code/software/a/shared.py", b"SOURCE_A\n"),
                           ("code/software/b/shared.py", b"SOURCE_B\n")):
        tag = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:12]
        path = run / "source" / (tag + "_" + Path(relative).name)
        path.write_bytes(data)
        item = {"path": str(path.resolve()), "bytes": len(data), "sha256": sha256(path)}
        mapping[relative] = item
        before[relative] = dict(item, path="SYNTHETIC_ORIGINAL_NOT_USED")
    receipt = {"source_before": before, "source_snapshot_layout": "FLAT_RELATIVE_SHA_MAP_V1",
               "source_snapshot_files": mapping}
    keys = list(before)
    cases = []
    def check(name, candidate, expected):
        try:
            verify_source_snapshots(receipt_path, candidate)
            actual = None
        except (ValueError, OSError, KeyError, TypeError) as exc:
            actual = str(exc)
        cases.append({"name": name, "expected": expected, "actual": actual,
                      "passed": expected == actual, "evidence_kind": "SYNTHETIC_SOFTWARE_ONLY"})
    check("flat_mapping_positive_same_basename_two_paths", receipt, None)
    altered = copy.deepcopy(receipt)
    altered["source_snapshot_files"].pop(keys[0])
    check("missing_mapping_key", altered, "SOURCE_SNAPSHOT_KEYS")
    altered = copy.deepcopy(receipt)
    altered["source_snapshot_files"]["EXTRA"] = mapping[keys[0]]
    check("extra_mapping_key", altered, "SOURCE_SNAPSHOT_KEYS")
    altered = copy.deepcopy(receipt)
    altered["source_snapshot_files"][keys[0]] = mapping[keys[1]]
    check("mapped_to_other_source", altered, "SOURCE_SNAPSHOT_PATH_MAPPING")
    altered = copy.deepcopy(receipt)
    altered["source_before"][keys[0]]["sha256"] = "0" * 64
    check("original_sha_mismatch", altered, "SOURCE_SNAPSHOT_ORIGINAL_IDENTITY")
    altered = copy.deepcopy(receipt)
    altered["source_snapshot_files"][keys[0]]["sha256"] = "0" * 64
    check("snapshot_sha_mismatch", altered, "IDENTITY_BYTES_OR_SHA")
    altered = copy.deepcopy(receipt)
    altered["source_snapshot_layout"] = "UNKNOWN_LAYOUT"
    check("unsupported_layout", altered, "SOURCE_SNAPSHOT_LAYOUT_UNSUPPORTED")
    altered = copy.deepcopy(receipt)
    altered.pop("source_snapshot_files")
    check("flat_without_map_no_legacy_fallback", altered, "SOURCE_SNAPSHOT_KEYS")
    with (args.output / "RESULTS.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(cases, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"tests": len(cases), "passed": sum(c["passed"] for c in cases),
                      "failed": [c for c in cases if not c["passed"]]}))
    return int(not all(c["passed"] for c in cases))


if __name__ == "__main__":
    raise SystemExit(main())
