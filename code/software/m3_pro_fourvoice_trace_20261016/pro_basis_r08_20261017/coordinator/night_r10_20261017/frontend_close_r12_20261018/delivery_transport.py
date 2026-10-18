"""R12 Git-evidence successor; production transport NOT_RUN."""
"""Future-admission delivery bridge to the unchanged bounded Git transport.

NOT an active publisher. No import-time candidate load, writes or network.
The current R11 static task must never call send_once or migrate publication.
"""
from datetime import datetime, timezone
import builtins
import hashlib
import json
import os
from pathlib import Path
import threading
import time
import types

ROOT = Path(__file__).resolve().parents[7]
HERE = Path(__file__).resolve().parent
LEGACY = HERE.parent / "night_drill_r01"
OUTPUT = ROOT / "code/output/m3_m2_night_drill_20261017"
STORE_ROOT = OUTPUT / "state/morning_r11_20261018/delivery"
BINDING_SHA = "bd8bc9a6f3b40dc793db8a32a91b5d4eb464d783f5166f2976e6a73d0a83844d"
JSON_IDENTITY_SHA = "d601d68bb2ee5d4ba4c4a435bdf3709dc943f05bb4858d516b854c507c9e6ae4"
ENGINE_SHA = "f463927e4c719e2b40645896b644647bed93f70a7640dca342ce2dc3cba6233b"
NETWORK_SHA = "add7a4195f70e8ad7dd23fb50b46892cda1d5d3a09edefd70794a145579016c5"
LEGACY_BASELINE_SHA = "ca723ff05905b81dce4d2a80bf226369cc9f03def4e444245bbddb662350e6ce"
GIT_PREFIX = ["C:/Program Files/Git/cmd/git.exe", "-c", "http.proxy=http://127.0.0.1:7892",
              "-c", "http.version=HTTP/1.1", "-c", "credential.interactive=false"]


def load(path, sha, name, imports=None):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError("PINNED_SOURCE_CHANGED:" + str(path))
    module = types.ModuleType(name)
    module.__file__, module.__package__ = str(path), ""
    if imports:
        def local_import(name, globals=None, locals=None, fromlist=(), level=0):
            if level == 0 and name in imports:
                return imports[name]
            return builtins.__import__(name, globals, locals, fromlist, level)
        module.__dict__["__builtins__"] = {**vars(builtins), "__import__": local_import}
    exec(compile(raw, str(path), "exec", dont_inherit=True), module.__dict__)
    return module


def support():
    identity_module = load(HERE / "json_identity.py", JSON_IDENTITY_SHA,
                           "_r12_delivery_identity")
    return load(HERE / "delivery_binding.py", BINDING_SHA,
                "_r12_delivery_binding", {"json_identity": identity_module})


def engine():
    return load(LEGACY / "intake/engine.py", ENGINE_SHA, "_r11_original_durable_store")


def operation_id(key):
    return "r11_delivery_" + key  # Full stable key; caller cannot reset retries by renaming it.


def target_argv(commit):
    return GIT_PREFIX + ["push", "--porcelain", "--quiet", "origin", commit + ":refs/heads/develop"]


def preserve_history(c, spec, current_operation):
    c.need(spec["legacy_network_snapshot"]["sha256"] == LEGACY_BASELINE_SHA,
           "ORIGINAL_LEGACY_BASELINE_REQUIRED")
    baseline = c.read_ref(spec["legacy_network_snapshot"])
    c.need(all(type(rows) is list and rows and rows[-1]["status"] == "OK"
               for rows in baseline.values()), "QUIESCENT_LEGACY_BASELINE_REQUIRED")
    path = OUTPUT / "state/network.json"
    c.need(path.is_file(), "LEGACY_NETWORK_HISTORY_MISSING")
    observation = c.read_record(path)
    current = observation.value
    for key, original in baseline.items():
        c.need(key in current and len(current[key]) >= len(original) and
               current[key][:len(original)] == original, "LEGACY_NETWORK_HISTORY_REWRITTEN")
    unresolved = [key for key, rows in current.items()
                  if rows and rows[-1]["status"] != "OK" and key != current_operation]
    c.need(not unresolved, "LEGACY_FAILURE_REVIEW_REQUIRED:" + ",".join(unresolved))
    return {"path": path, "body": current, "observation": observation.stamp}


def prepare_send(spec_ref):
    c = support()
    bound = c.verify(spec_ref)
    c.need(bound["direction"] == "SEND", "SEND_SPEC_REQUIRED")
    # The supplied historical example is useful for binding review, never a send request.
    c.need(bound["queue_allowed"] and bound["spec_body"]["purpose"] == "NEW_UNPUBLISHED_DELIVERY", "HISTORICAL_EXAMPLE_NOT_SENDABLE")
    preserve_history(c, bound["spec_body"], operation_id(bound["key"]))
    original = engine()
    handoff = bound["handoff"]
    store = original.Store(STORE_ROOT, owner="night_task_1")
    item = store.enqueue(handoff, task_id=handoff["task_id"], plan_version=handoff["plan_version"])
    return {"binding": bound, "outbox": item, "remote_verified": False, "execution_allowed": False}


def receive_frozen(spec_ref, snapshot_root=ROOT):
    c = support()
    bound = c.verify(spec_ref, snapshot_root)
    c.need(bound["direction"] == "RECEIVE", "RECEIVE_SPEC_REQUIRED")
    c.need(bound["queue_allowed"] and bound["spec_body"]["purpose"] == "NEW_RECEIVED_DELIVERY",
           "HISTORICAL_EXAMPLE_NOT_RECEIVABLE")
    original = engine()
    handoff = bound["handoff"]
    store = original.Store(STORE_ROOT, owner="night_task_1")
    receipt = store.receive(handoff, snapshot_root, task_id=bound["spec_body"]["expected_identity"]["task_id"],
                            plan_version=bound["spec_body"]["expected_identity"]["plan_version"],
                            origin="LOCAL_REPOSITORY_SNAPSHOT")
    # No implicit advance: verified RECEIVED must be durably observable first.
    return {"binding": bound, "receipt": receipt, "advance_performed": False, "remote_verified": False}


def same_root_cwd(c, record, reason):
    cwd = record.get("cwd")
    c.need(type(cwd) is str and Path(cwd).is_absolute()
           and c.safe_path(cwd) == c.safe_path(ROOT), reason)


def check_admission(c, admission_ref, spec_ref, bound):
    admission = c.read_ref(admission_ref)
    c.need(admission["schema"] == "M3_R11_EXACT_TRANSPORT_RUN_CONTRACT_V1", "RUN_CONTRACT_SCHEMA")
    c.need(admission["delivery_spec"] == spec_ref and admission["executor_thread"] == "01a14050-cd98-7c41-8004-5d3e25765167",
           "RUN_DELIVERY_EXECUTOR_BINDING")
    c.need(admission["network_source"]["sha256"] == NETWORK_SHA and
           admission["engine_source"]["sha256"] == ENGINE_SHA, "RUN_SOURCE_BINDING")
    c.checked(admission["network_source"])
    c.checked(admission["engine_source"])
    git = admission["git_executable"]
    c.need(c.safe_path(git["path"]) == c.safe_path(GIT_PREFIX[0]) and
           c.identity(git["path"]) == {key: git[key] for key in ("bytes", "sha256")}, "GIT_TOOL_IDENTITY")
    c.need(admission["argv"] == target_argv(bound["handoff"]["result_commit"]) and
           admission["cwd"] == str(ROOT) and admission["network_seconds"] == 30 and
           admission["max_attempts"] == 2, "RUN_EXACT_OPERATION_BINDING")
    instant = datetime.now(timezone.utc)
    start, stop = (datetime.fromisoformat(admission[key]) for key in ("valid_from", "deadline"))
    c.need(start.tzinfo is not None and stop.tzinfo is not None and start <= instant < stop, "RUN_WINDOW_INVALID")
    # Previously executed independent fetch+ancestry originals, not an approval string.
    fetch = c.read_ref(admission["fresh_fetch_result"])
    ancestry = c.read_ref(admission["fresh_ancestry_result"])
    same_root_cwd(c, fetch, "FETCH_CWD_IDENTITY")
    same_root_cwd(c, ancestry, "ANCESTRY_CWD_IDENTITY")
    for descriptor in (fetch["stdout"], fetch["stderr"]):
        c.checked(descriptor)
    c.need(fetch["kind"] == "fetch" and fetch["exit_code"] == 0 and fetch["within_30_seconds"] is True,
           "FRESH_FETCH_REQUIRED")
    c.need(fetch["argv"] == GIT_PREFIX + ["fetch", "origin"], "FETCH_ARGV_IDENTITY")
    c.need(ancestry["argv"] == [GIT_PREFIX[0], "merge-base", "--is-ancestor",
                                bound["handoff"]["result_commit"], "origin/develop"] and
           ancestry["exit_code"] == 1 and ancestry["fetch_result"] == admission["fresh_fetch_result"],
           "EXACT_NOT_CONTAINED_PROOF_REQUIRED")
    for ref in (ancestry["stdout"], ancestry["stderr"]):
        c.checked(ref)
    tree = c.read_ref(admission["commit_tree_verification"])
    c.need(tree["commit"] == bound["handoff"]["result_commit"] and
           tree["manifest"] == bound["handoff"]["manifest"] and
           [row["payload"] for row in tree["entries"]] == tree["manifest"], "COMMIT_MANIFEST_BINDING")
    for row in tree["entries"]:
        same_root_cwd(c, row, "SHOW_CWD_IDENTITY")
        payload = row["payload"]
        c.need(row["exit_code"] == 0 and row["argv"] ==
               [GIT_PREFIX[0], "show", tree["commit"] + ":" + payload["path"]], "COMMIT_BLOB_READ_BINDING")
        c.checked(row["stdout"])
        c.checked(row["stderr"])
        c.need({key: row["stdout"][key] for key in ("bytes", "sha256")} ==
               {key: payload[key] for key in ("bytes", "sha256")}, "COMMIT_BLOB_IDENTITY_MISMATCH")
    for item in (fetch, ancestry):
        observed = datetime.fromisoformat(item["utc"])
        c.need(observed.tzinfo is not None and start <= observed <= instant and
               (instant - observed).total_seconds() <= 300, "REMOTE_CHECK_NOT_FRESH")
    return admission


def classify(code, record, stderr):
    text = stderr.casefold()
    if code == 0:
        return "SUCCESS_REPORTED"
    if any(token in text for token in ("permission denied", "authentication failed", "access denied", "unacceptable risk")):
        return "DENIED"
    if "non-fast-forward" in text or "fetch first" in text:
        return "NON_FAST_FORWARD"
    if "pre-receive hook declined" in text or "remote rejected" in text:
        return "REJECTED"
    if record.get("status") == "FAILED" and any(token in text for token in ("could not resolve host", "failed to connect")):
        return "FAILED_TEMPORARY"  # Only failures before a connection can be established.
    return "UNKNOWN"  # Reset/timeout/exception may follow a successful remote write.


def require_launch_window(c, admission):
    instant = datetime.now(timezone.utc)
    start, stop = (datetime.fromisoformat(admission[key]) for key in ("valid_from", "deadline"))
    c.need(start.tzinfo is not None and stop.tzinfo is not None and start <= instant and
           (stop - instant).total_seconds() >= 31, "INSUFFICIENT_FULL_TRANSPORT_WINDOW")


def send_once(spec_ref, admission_ref, retry_basis=None):
    """Future bound runner only. Current static preparation grants ZERO runs."""
    prepared = prepare_send(spec_ref)
    c, bound = support(), prepared["binding"]
    admission = check_admission(c, admission_ref, spec_ref, bound)
    original = engine()
    store = original.Store(STORE_ROOT, owner="night_task_1")
    key, op = bound["key"], operation_id(bound["key"])
    history_snapshot = preserve_history(c, bound["spec_body"], op)
    history = history_snapshot["body"]
    prior = history.get(op, [])
    item = prepared["outbox"]
    c.need(item["attempts"] == len(prior), "NETWORK_OUTBOX_ATTEMPT_MISMATCH")
    if item["attempts"]:
        c.need(retry_basis is not None, "RETRY_BASIS_REQUIRED")
        basis = c.read_ref(retry_basis)
        c.need(basis["outbox_key"] == key and basis["prior_attempt"] == item["attempts"] and
               basis["run_contract"] == admission_ref, "RETRY_IDENTITY_BINDING")
    # Loading/identity checks happen before consumption; they do not start Git.
    network = load(LEGACY / "network.py", NETWORK_SHA, "_r11_original_bounded_network")
    network.COMMANDS = {**network.COMMANDS, "push": target_argv(bound["handoff"]["result_commit"])[len(GIT_PREFIX):]}
    require_launch_window(c, admission)
    # Enqueue and exact pending identity already persisted. Consume before actual transport.
    watchdog = threading.Timer(29.5, lambda: os._exit(124))
    watchdog.daemon = True
    watchdog.start()
    started = time.monotonic()
    try:
        attempt = store.begin_attempt(key)
        # A slow disk/lock may have consumed the margin: reject without resetting
        # IN_FLIGHT. An expiry after consumption is UNKNOWN-on-recovery.
        require_launch_window(c, admission)
        # Same Git/tool/proxy/Job/deadline mechanism; exact target refspec only.
        code = network.run("push", op, retry_basis=None if not prior else "FROZEN_BASIS:" + retry_basis["sha256"])
        run = OUTPUT / "runs" / (op + "_" + str(attempt["attempts"]).zfill(2))
        record_observation = c.read_record(run / "RESULT.json")
        record = record_observation.value
        stdout, stderr = run / "stdout.bin", run / "stderr.bin"
        c.need(record["argv"] == admission["argv"] and record["cwd"] == admission["cwd"], "ACTUAL_TRANSPORT_IDENTITY_MISMATCH")
        with stderr.open("rb") as stream:
            error_text = stream.read(64 * 1024).decode("utf-8", errors="backslashreplace")
        raw_refs = {"stdout": c.identity(stdout), "stderr": c.identity(stderr)}
        finished = store.finish_attempt(key, outcome=classify(code, record, error_text),
            error=json.dumps({"message": error_text, "raw_files": {"stdout": str(stdout), "stderr": str(stderr)},
                              "raw_identities": raw_refs, "transport_status": record["status"]}, ensure_ascii=False),
            argv=record["argv"], exit_code=record["exit_code"],
            elapsed_seconds=time.monotonic() - started, origin="ACTUAL_ADAPTER_REPORTED")
        # The legacy complete network ledger must still contain its immutable old prefix.
        preserve_history(c, bound["spec_body"], op)
        return {"outbox": finished, "network_record": record, "network_record_identity": record_observation.stamp, "raw_identities": raw_refs,
                "remote_verified": False, "receiver_accepted": False}
    except Exception as error:
        # Keep the slot consumed; persist wrapper failures as well as native raw streams.
        failure_root = c.safe_path(STORE_ROOT / "failures")
        failure_root.mkdir(parents=True, exist_ok=True)
        filename = failure_root / (key + "_" + str(item["attempts"] + 1) + ".json")
        payload = {"schema": "M3_R11_SEND_WRAPPER_FAILURE_V1", "key": key,
                   "delivery_spec": spec_ref, "run_contract": admission_ref,
                   "error": type(error).__name__, "reason": str(error),
                   "outbox": "CONSUMED; IN_FLIGHT must recover to UNKNOWN, not reset",
                   "remote_verified": False}
        with filename.open("xb") as stream:
            stream.write(c.canonical(payload) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        raise
    finally:
        # On exception or watchdog termination IN_FLIGHT remains consumed/UNKNOWN-on-recovery.
        # Do not return a pending slot to READY or erase original errors.
        watchdog.cancel()
