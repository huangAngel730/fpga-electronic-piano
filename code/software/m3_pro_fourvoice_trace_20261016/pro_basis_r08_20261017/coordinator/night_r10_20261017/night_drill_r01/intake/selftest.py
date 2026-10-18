"""Ten LOCAL_SYNTHETIC cases. No candidate load or write at import time."""
import copy
import hashlib
import json
from pathlib import Path
import types

ROOT = Path(__file__).resolve().parents[8]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017/night_drill_r01/intake"


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def check(ok, reason):
    if not ok:
        raise ValueError(reason)


def source():
    binding = json.loads((DOC / "BINDING.json").read_text(encoding="utf-8"))
    path = ROOT / binding["engine"]["path"]
    raw = path.read_bytes()
    check(len(raw) == binding["engine"]["bytes"] and hashlib.sha256(raw).hexdigest() == binding["engine"]["sha256"], "ENGINE_BINDING")
    module = types.ModuleType("_night_drill_intake_" + binding["engine"]["sha256"][:20])
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec", dont_inherit=True), module.__dict__)
    return module


def rejected(engine, function, expected):
    try:
        function()
    except engine.Reject as error:
        check(str(error) == expected, "REJECTION_MISMATCH:" + str(error))
        return str(error)
    raise ValueError("EXPECTED_REJECTION:" + expected)


def run_case(case_id, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    content = out / "input"
    content.mkdir()
    body = b"LOCAL_SYNTHETIC exact manifest payload\n"
    (content / "payload.txt").write_bytes(body)
    handoff = {"schema": "NIGHT_HANDOFF_V1", "handoff_id": "DRILL-SYNTHETIC-01",
               "task_id": "M3-NIGHT-DRILL-R01-20261017", "plan_version": "R01",
               "producer": "M2", "consumer": "M3", "base_commit": "a" * 40,
               "result_commit": "b" * 40,
               "manifest": [{"path": "payload.txt", "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}],
               "validation": {"level": "LOCAL_SYNTHETIC_ONLY"}}
    definitions = json.loads((DOC / "CASES.json").read_text(encoding="utf-8"))["cases"]
    selected = next((case for case in definitions if case["id"] == case_id), None)
    check(selected is not None, "UNKNOWN_CASE")
    write_json(out / "INPUT.json", {"case": selected, "handoff": handoff,
                                    "content_root": str(content), "store_root": str(out / "store"),
                                    "origin": "LOCAL_SYNTHETIC", "processes_or_network": False})
    # Only the coordinator invokes run_case; all fixture identities exist first.
    engine = source()
    store = engine.Store(out / "store")
    options = {"task_id": handoff["task_id"], "plan_version": "R01", "origin": "LOCAL_SYNTHETIC"}
    actual = {"case_id": case_id, "origin": "LOCAL_SYNTHETIC", "remote_verified": False}
    try:
        if case_id == "INTAKE_NORMAL":
            received = store.receive(handoff, content, **options)
            snapshot = store.snapshot()
            check(received["status"] == "RECEIVED" and snapshot["advance_count"] == 0, "PERSIST_BEFORE_ADVANCE")
            advanced = store.advance(received["key"])
            check(advanced["status"] == "ADVANCED" and engine.Store(out / "store").snapshot()["advance_count"] == 1, "ADVANCE_PERSISTED")
            actual.update(status="RECEIVED_THEN_ADVANCED", received=received, advanced=advanced)
        elif case_id == "INTAKE_DUPLICATE_RELOAD":
            first = store.receive(handoff, content, **options)
            store.advance(first["key"])
            reloaded = engine.Store(out / "store")
            second = reloaded.receive(handoff, content, **options)
            advanced = reloaded.advance(second["key"])
            snap = reloaded.snapshot()
            check(second["status"] == "DUPLICATE" and advanced["status"] == "ALREADY_ADVANCED" and
                  len(snap["receipts"]) == snap["advance_count"] == 1, "DUPLICATE_ONCE")
            actual.update(status="DUPLICATE_EXACTLY_ONCE", snapshot=snap)
        elif case_id == "INTAKE_MANIFEST_BOUNDARIES":
            variants = []
            for name, changes, reason in (
                    ("bytes", {"bytes": len(body) + 1}, "MANIFEST_BYTES_MISMATCH:payload.txt"),
                    ("sha", {"sha256": "0" * 64}, "MANIFEST_SHA_MISMATCH:payload.txt"),
                    ("escape", {"path": "../payload.txt"}, "MANIFEST_PATH"),
                    ("device", {"path": "NUL"}, "DEVICE_NAME")):
                candidate = copy.deepcopy(handoff)
                candidate["manifest"][0].update(changes)
                variants.append({"name": name, "handoff": candidate, "expected": reason})
            write_json(out / "VARIANTS.json", variants)
            reasons = []
            for variant in variants:
                target = engine.Store(out / ("s_" + variant["name"]))
                reasons.append(rejected(engine, lambda: target.receive(variant["handoff"], content, **options), variant["expected"]))
                check(not target.snapshot()["receipts"], "BAD_MANIFEST_RECEIPT")
            actual.update(status="MANIFEST_4_REJECTIONS", reasons=reasons)
        elif case_id == "INTAKE_SCHEMA_VERSION_CONSUMER":
            variants = []
            for name, changes, reason in (
                    ("schema", {"schema": "OTHER"}, "HANDOFF_SCHEMA"),
                    ("version", {"plan_version": "R00"}, "HANDOFF_VERSION"),
                    ("consumer", {"consumer": "M2"}, "HANDOFF_CONSUMER"),
                    ("short", {"result_commit": "bbbbbbb"}, "FULL_COMMIT_REQUIRED")):
                candidate = copy.deepcopy(handoff)
                candidate.update(changes)
                variants.append({"name": name, "handoff": candidate, "expected": reason})
            write_json(out / "VARIANTS.json", variants)
            reasons = [rejected(engine, lambda candidate=variant["handoff"]: store.receive(candidate, content, **options), variant["expected"])
                       for variant in variants]
            actual.update(status="CONTRACT_4_REJECTIONS", reasons=reasons)
        elif case_id in ("OUTBOX_RETRY_RELOAD", "OUTBOX_UNKNOWN", "OUTBOX_DENIED", "OUTBOX_INTERRUPTED"):
            handoff = copy.deepcopy(handoff)
            handoff["producer"] = "M3"
            handoff["consumer"] = "M2"
            write_json(out / "OUTGOING_INPUT.json", handoff)
            queued = store.enqueue(handoff, task_id=handoff["task_id"], plan_version="R01")
            key = queued["key"]
            write_json(out / "SEND_INPUT.json", {"key": key, "remote": "origin", "branch": "develop",
                                                "result_commit": handoff["result_commit"], "origin": "LOCAL_SYNTHETIC",
                                                "argv": ["LOCAL_SYNTHETIC_ADAPTER", "origin", "develop", handoff["result_commit"]]})
            store.begin_attempt(key)
            if case_id == "OUTBOX_INTERRUPTED":
                recovery = engine.Store(out / "store").recover_in_flight()
                check(recovery["unknown_keys"] == [key], "INTERRUPTED_UNKNOWN")
                rejected(engine, lambda: store.begin_attempt(key), "UNKNOWN_REQUIRES_REMOTE_CHECK")
                actual["status"] = "INTERRUPTED_SEND_UNKNOWN"
            else:
                outcome = {"OUTBOX_RETRY_RELOAD": "FAILED_TEMPORARY", "OUTBOX_UNKNOWN": "UNKNOWN", "OUTBOX_DENIED": "DENIED"}[case_id]
                evidence = {"outcome": outcome, "error": "LOCAL_SYNTHETIC:" + outcome,
                            "argv": ["LOCAL_SYNTHETIC_ADAPTER", "origin", "develop", handoff["result_commit"]],
                            "exit_code": None if outcome == "UNKNOWN" else 1, "elapsed_seconds": 0.01,
                            "origin": "LOCAL_SYNTHETIC"}
                store.finish_attempt(key, **evidence)
                store = engine.Store(out / "store")
                if case_id == "OUTBOX_RETRY_RELOAD":
                    second = store.begin_attempt(key)
                    check(second["attempts"] == 2, "PERSISTENT_ATTEMPTS")
                    store.finish_attempt(key, **evidence)
                    rejected(engine, lambda: store.begin_attempt(key), "SEND_NOT_READY")
                    actual["status"] = "ONE_RETRY_MAXIMUM"
                elif case_id == "OUTBOX_UNKNOWN":
                    rejected(engine, lambda: store.begin_attempt(key), "UNKNOWN_REQUIRES_REMOTE_CHECK")
                    actual["status"] = "UNKNOWN_NO_RESEND_OR_REMOTE_PASS"
                else:
                    rejected(engine, lambda: store.begin_attempt(key), "SEND_NOT_READY")
                    actual["status"] = "DENIED_NO_RETRY"
            item = store.snapshot()["outbox"][key]
            check(item["remote"] == "origin" and item["branch"] == "develop" and
                  item["handoff"] == handoff and item["remote_verified"] is False, "EXACT_OUTBOX")
            check(item["attempts"] == (2 if case_id == "OUTBOX_RETRY_RELOAD" else 1), "ATTEMPT_TOTAL")
            actual["outbox"] = item
        elif case_id == "INTAKE_SINGLE_WRITER":
            with store.lock():
                reason = rejected(engine, lambda: engine.Store(out / "store", owner="SECOND").receive(handoff, content, **options), "SINGLE_WRITER_LOCK_HELD")
            check(store.receive(handoff, content, **options)["status"] == "RECEIVED", "LOCK_RELEASE")
            actual.update(status="EXCLUSIVE_WRITER", rejection=reason)
        elif case_id == "INTAKE_CHECKPOINT_GAP":
            rejected(engine, lambda: store.advance("0" * 64), "RECEIVED_REQUIRED")
            received = store.receive(handoff, content, **options)
            check(store.snapshot()["advance_count"] == 0, "GAP_NO_ADVANCE")
            reloaded = engine.Store(out / "store")
            check(reloaded.receive(handoff, content, **options)["status"] == "DUPLICATE", "GAP_RECEIPT_PERSISTED")
            reloaded.advance(received["key"])
            check(reloaded.snapshot()["advance_count"] == 1, "GAP_ADVANCE_ONCE")
            actual["status"] = "RELOAD_CONTINUES_AFTER_RECEIVED"
        else:
            raise ValueError("CASE_NOT_IMPLEMENTED")
        write_json(out / "ACTUAL.json", actual)
        check(actual["status"] == selected["expected"], "CASE_STATUS")
        result = {"case_id": case_id, "assertion": "MATCHED", "expected": selected["expected"],
                  "actual": actual, "origin": "LOCAL_SYNTHETIC", "remote_verified": False,
                  "network_calls": 0, "business_tools_started": 0}
        write_json(out / "RESULT.json", result)
        return result
    except Exception as error:
        write_json(out / "FAILURE.json", {"error": type(error).__name__, "reason": str(error),
                                          "origin": "LOCAL_SYNTHETIC", "partial_actual": actual})
        raise
