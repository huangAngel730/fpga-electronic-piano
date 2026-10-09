"""Seal immutable new router evidence and a forwardable ZIP, never old evidence."""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--delivery", type=Path, required=True)
    args = parser.parse_args()
    run, delivery = args.run.resolve(), args.delivery.resolve()
    assert run.is_relative_to(ROOT / "code/output")
    assert delivery.is_relative_to(ROOT / "code/output") and delivery != ROOT / "code/output"
    receipt = json.loads((run / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "ROUTER_AUDIO_MATCH_AWAITING_M2_CLOSURE" and receipt["exit_code"] == 3
    assert receipt["component_results"]["successful"] and receipt["component_results"]["tests_run"] == 60
    assert receipt["repository_gate"] == dict(exit_code=0, pass_lines=9, fail_lines=0)
    assert receipt["received_bundle_results"]["negative_dispositions"] == {"REJECTED_WITH_SPECIFIED_DIAGNOSTIC": 56}
    assert receipt["router_results"]["negative_cases"] == 6 and receipt["router_results"]["executable_mutants"] == 2
    assert receipt["elapsed_seconds"] <= receipt["limits"]["total_seconds"]
    for step in receipt["steps"]:
        assert not step["timed_out"] and not step["elapsed_limit_exceeded"]
        assert step["elapsed_seconds"] <= step["timeout_seconds"]
    for item in receipt["candidate_sources"] + receipt["frozen_inputs"] + receipt["capture_inputs"] + receipt["artifacts"]:
        assert sha(Path(item["path"]).read_bytes()) == item["sha256"], item["path"]
    # Only raw receipt and logs enter the small Git evidence carrier. Full new
    # mutated inputs and executed source copies are kept in the forwardable ZIP.
    evidence = [run / "receipt.json", run / "router/receipt.json"]
    evidence += sorted(run.glob("*.bin")) + sorted((run / "router").glob("*.bin"))
    entries = {}
    for path in evidence:
        raw = path.read_bytes()
        entries[path.relative_to(ROOT).as_posix()] = dict(bytes=len(raw), sha256=sha(raw), raw_base64=base64.b64encode(raw).decode("ascii"))
    container = json.dumps(entries, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    carrier = base64.b64encode(gzip.compress(container, mtime=0)) + b"\n"
    carrier_path = HERE / "ROUTER_EVIDENCE_20261010.json.gz.b64"
    manifest_path = HERE / "ROUTER_EVIDENCE_MANIFEST_20261010.json"
    assert not carrier_path.exists() and not manifest_path.exists() and not delivery.exists()
    delivery.mkdir(parents=True)
    with carrier_path.open("xb") as out:
        out.write(carrier)
    decoded = json.loads(gzip.decompress(base64.b64decode(carrier_path.read_bytes())))
    for name, item in decoded.items():
        raw = base64.b64decode(item["raw_base64"], validate=True)
        assert len(raw) == item["bytes"] and sha(raw) == item["sha256"] and raw == (ROOT / name).read_bytes()

    payload = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in run.rglob("*") if p.is_file()}
    docs = [HERE / "ROUTER_CLOSURE_20261010.md", HERE / "M2_HANDOFF_ROUTER_20261010.md", Path(__file__), carrier_path,
            ROOT / "code/software/audio_math_acceptance_candidate/README.md"]
    for path in docs + [Path(item["path"]) for item in receipt["candidate_sources"] + receipt["frozen_inputs"]]:
        payload[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    # Original capture bytes, not a reserialized JSONL; old56 remain in the
    # already-shared bundle and are explicitly identified by the raw receipts.
    for item in receipt["capture_inputs"]:
        path = Path(item["path"])
        payload["original_Golden/" + path.name] = path.read_bytes()
    index = {name: dict(bytes=len(raw), sha256=sha(raw)) for name, raw in sorted(payload.items())}
    payload["PAYLOAD_INDEX.json"] = (json.dumps(index, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    zip_path = delivery / "M3_T060_ROUTER_20261010.zip"
    with zip_path.open("xb") as out, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(payload.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 10, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    with zipfile.ZipFile(zip_path) as archive:
        assert archive.testzip() is None
        for name, raw in payload.items():
            assert archive.read(name) == raw
    manifest = dict(schema=1, status=receipt["status"], git_base=receipt["git_head"], committed_at_seal=False,
                    pushed_at_seal=False, carrier=carrier_path.name, carrier_bytes=len(carrier), carrier_sha256=sha(carrier),
                    container_bytes=len(container), container_sha256=sha(container),
                    archived_raw_files={k: {n: v[n] for n in ("bytes", "sha256")} for k, v in entries.items()},
                    tested_sources=receipt["candidate_sources"], frozen_inputs=receipt["frozen_inputs"],
                    forward_zip=dict(path=str(zip_path), bytes=zip_path.stat().st_size, sha256=sha(zip_path.read_bytes()),
                                     members=len(payload), verified=True),
                    delivery_docs=[dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size, sha256=sha(p.read_bytes())) for p in docs])
    with manifest_path.open("x", encoding="utf-8", newline="\n") as out:
        json.dump(manifest, out, ensure_ascii=False, indent=2)
        out.write("\n")
    print(json.dumps(dict(carrier_bytes=len(carrier), carrier_sha256=sha(carrier), manifest=str(manifest_path),
                          forward_zip=manifest["forward_zip"], verified=True), ensure_ascii=False))


if __name__ == "__main__":
    main()
