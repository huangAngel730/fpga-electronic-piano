"""Freeze the actual R02 inputs and path-only schema change, then copy C sources."""
import hashlib
import json
from pathlib import Path


def identity(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def main():
    here = Path(__file__).resolve().parent
    root = here.parents[4]
    docs = root / "code/docs/test/m3_40mhz_pcm_i2s_latency_20261015/night_20261016/RESUME_R02"
    docs.mkdir(exist_ok=False)
    a = root / "code/docs/test/m3_r05_functional_integration_20261015/night_20261016/RESUME_R02"
    expected = {
        "RUN_01/RUN_RECEIPT.json": "1516a35e6a5852164866aa729f8897ca5a668a4308f8e1ce60e91fa994211dbc",
        "CAPTURE_READY.json": "a9f36a26b6fc68d6a84fdda85c1047e79032356f6f78d491527e2d848ef81ab1",
        "RUN_01/stage/inputs/REAL_CAPTURE.jsonl": "a2509a2b5555437ff8ee1da4799e8210ad80e95a058881a5d26111a935e5b5d3",
        "RUN_01/stage/inputs/REAL_INPUTS.jsonl": "d001cac94d1520c42b43bcb33ca079c2f1d815c1205deb4a2d87005fe143038b",
        "STARTUP_BOUNDARY.json": "bbc78215e6c1f839a4d7789af93fc4d994c3ef6bab22c59448e2b9e710a5e8e7",
        "STARTUP_SCHEMA.json": "2e4b9a1d7e19e488f1d06ef1c3a4530900019ab623a7347bad903cc4ef3a0230",
        "STARTUP_SCHEMA.diff": "874418c9a02e016e4c630d607d1d3358cfbd7784ba0837216dfda92f834e0f1a"}
    inputs = {name: identity(a / name) for name in expected}
    for name, digest in expected.items():
        assert inputs[name]["sha256"] == digest, name
    old_schema = json.loads((a.parent / "RESUME_R01/STARTUP_SCHEMA.json").read_text(encoding="utf-8"))
    schema = json.loads((a / "STARTUP_SCHEMA.json").read_text(encoding="utf-8"))
    changed = [k for k in schema if schema[k] != old_schema[k]]
    assert set(changed) == {"producer_observer", "producer_board"}
    assert set(old_schema) == set(schema)
    ready = json.loads((a / "CAPTURE_READY.json").read_text(encoding="utf-8"))
    assert ready["status"] == "REAL_CAPTURE_READY_FOR_C_INDEPENDENT_CONSUMPTION"
    for name, item in ready.items():
        if isinstance(item, dict) and set(item) == {"path", "bytes", "sha256"}:
            assert identity(Path(item["path"])) == item, name
    copies = []
    for name in ("consume_real.py", "consume_capture.py", "run_command.py", "startup_adapter.py", "startup_guards.py"):
        original = here.parent / "RESUME_R01" / name
        target = here / name
        with target.open("xb") as stream:
            stream.write(original.read_bytes())
        copies.append({"original": identity(original), "copy": identity(target)})
    receipt = {"status": "EXACT_R02_INPUTS_FROZEN_PENDING_REAL_CONSUMER", "inputs": inputs,
               "schema_changed_keys": changed, "copies": copies, "old_files_modified": False,
               "capture_aggregate_not_used_as_expectation": True}
    with (docs / "PREFLIGHT_INPUTS.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"input_SHA": "PASS", "ready_identities": "PASS", "schema_changed_keys": changed}))


if __name__ == "__main__":
    main()
