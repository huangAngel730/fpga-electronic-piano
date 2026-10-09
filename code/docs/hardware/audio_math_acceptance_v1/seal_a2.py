"""Seal only new A2 evidence; refuse overwrite and changed tested source bytes."""
import base64
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
RUN = ROOT / "code/output/m3_audio_math_received_a2_20261009_01"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    receipt = json.loads((RUN / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "PARTIAL_REAL_A2_AWAITING_BOUNDARY_REVIEW"
    assert receipt["exit_code"] == 3
    assert receipt["component_results"]["successful"]
    assert receipt["repository_gate"] == {"exit_code": 0, "pass_lines": 9, "fail_lines": 0}
    assert receipt["received_bundle_results"]["negative_dispositions"] == {"REJECTED_WITH_SPECIFIED_DIAGNOSTIC": 56}
    entries = {}
    for item in receipt["candidate_sources"] + receipt["frozen_inputs"] + receipt["capture_inputs"]:
        assert sha(Path(item["path"]).read_bytes()) == item["sha256"], item["path"]
    selected = [RUN / "receipt.json"]
    for step in receipt["steps"]:
        if step["label"] in ("component_tests", "repository_gate", "received_bundle_dds"):
            for channel in ("stdout", "stderr"):
                path = Path(step[channel]["path"])
                assert sha(path.read_bytes()) == step[channel]["sha256"]
                selected.append(path)
    probe = ROOT / "code/output/m3_audio_math_a2_probe_20261009_01"
    selected.extend(sorted(probe.glob("*.bin")))
    for path in selected:
        raw = path.read_bytes()
        entries[path.relative_to(ROOT).as_posix()] = {
            "bytes": len(raw), "sha256": sha(raw), "raw_base64": base64.b64encode(raw).decode("ascii")}
    raw = json.dumps(entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    carrier = base64.b64encode(gzip.compress(raw, mtime=0)) + b"\n"
    name = "RECEIVED_A2_EVIDENCE.json.gz.b64"
    manifest = {"schema": 1, "status": receipt["status"], "git_base": receipt["git_head"],
                "committed": False, "pushed": False, "carrier": name,
                "carrier_bytes": len(carrier), "carrier_sha256": sha(carrier),
                "container_raw_bytes": len(raw), "container_raw_sha256": sha(raw),
                "encoding": "base64(gzip(UTF8 JSON path->{bytes,sha256,raw_base64}))",
                "archived_raw_files": {k: {n: v[n] for n in ("bytes", "sha256")} for k, v in entries.items()},
                "candidate_sources": receipt["candidate_sources"],
                "delivery_documents": [{"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size,
                                        "sha256": sha(path.read_bytes())} for path in
                                       (HERE / "RECEIVED_A2_20261009.md", HERE / "M2_HANDOFF_A2_20261009.md",
                                        ROOT / "code/software/audio_math_acceptance_candidate/README.md", Path(__file__))]}
    assert not (HERE / name).exists()
    assert not (HERE / "RECEIVED_A2_EVIDENCE_MANIFEST.json").exists()
    with (HERE / name).open("xb") as out:
        out.write(carrier)
    with (HERE / "RECEIVED_A2_EVIDENCE_MANIFEST.json").open("x", encoding="utf-8", newline="\n") as out:
        json.dump(manifest, out, ensure_ascii=False, indent=2)
        out.write("\n")
    # Verify decoding is byte-identical before presenting the carrier.
    recovered = json.loads(gzip.decompress(base64.b64decode((HERE / name).read_bytes())))
    for key, item in recovered.items():
        data = base64.b64decode(item["raw_base64"], validate=True)
        assert len(data) == item["bytes"] and sha(data) == item["sha256"]
        assert data == (ROOT / key).read_bytes()
    print(json.dumps({"carrier": name, "raw_files": len(entries), "bytes": len(carrier),
                      "sha256": sha(carrier), "verified": True}))


if __name__ == "__main__":
    main()
