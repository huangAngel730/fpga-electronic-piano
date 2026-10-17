"""Metadata only: consume finished receipt without executing any candidate."""
import argparse
import hashlib
import json
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[5]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("group", choices=list("RSCTH"))
    parser.add_argument("phase", choices=["initial", "repair"])
    args = parser.parse_args()
    ledger_path = DOC / "CONSUMPTION.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    item = ledger["groups"][args.group]
    assert item[args.phase + "_consumed"] == 1
    receipt_path = ROOT / item[args.phase + "_output"] / "RECEIPT.json"
    raw = receipt_path.read_bytes()
    receipt = json.loads(raw)
    assert receipt["group"] == args.group and receipt["phase"] == args.phase
    assert receipt["elapsed_s"] <= receipt["limit_s"] + 1 or receipt["status"] != "PASS_LIMITED_SOFTWARE"
    item["latest_run_status"] = receipt["status"]
    initial_path = ROOT / item["initial_output"]
    initial_spec = json.loads((initial_path / "SPEC.json").read_text(encoding="utf-8"))
    expected = {(c["component"], c["id"]) for c in initial_spec["cases"]}
    actual = {}
    for folder in ("R01", "R02"):
        candidate = initial_path.parent / folder / "RECEIPT.json"
        if candidate.exists():
            document = json.loads(candidate.read_text(encoding="utf-8"))
            actual.update({(c["component"], c["id"]): c["assertion"] for c in document["results"]})
    missing = expected - actual.keys()
    failed = [key for key, value in actual.items() if value != "MATCHED"]
    item["coverage"] = {"planned": len(expected), "matched_unique": sum(value == "MATCHED" for value in actual.values()), "not_run": len(missing), "unresolved_failed": len(failed)}
    item["not_run_cases"] = [{"component": key[0], "id": key[1]} for key in sorted(missing)]
    item["status"] = ("PASS_LIMITED_SOFTWARE" if not missing and not failed else
                      "PARTIAL_NOT_RUN_REPAIR_PASS" if missing and not failed and args.phase == "repair" else receipt["status"])
    item[args.phase + "_receipt"] = {"path": receipt_path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    item[args.phase + "_elapsed_s"] = receipt["elapsed_s"]
    item[args.phase + "_exit_code"] = receipt["exit_code"]
    temporary = ledger_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, ledger_path)
    print(json.dumps(item))


if __name__ == "__main__":
    main()
