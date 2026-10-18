"""Durable local intake/outbox only. Import performs no file or network action."""
import argparse
from contextlib import contextmanager
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import uuid

MAX_JSON = 4 * 1024 * 1024
MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024
STORE_SCHEMA = "M3_DRILL_INTAKE_STATE_V1"
OUTPUT = Path(__file__).resolve().parents[8] / "code/output/m3_m2_night_drill_20261017"


class Reject(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise Reject(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(",", ":")).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def no_alias(path):
    path = Path(path)
    require(not str(path).startswith("\\\\"), "NETWORK_OR_DEVICE_PATH")
    require(not str(path).startswith(("\\\\.\\", "\\\\?\\", "\\??\\")), "DEVICE_PATH")
    for part in path.parts:
        require(not re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part), "DEVICE_NAME")
        require(part.rstrip(" .") == part, "NONCANONICAL_PATH")
    for ancestor in (path, *path.parents):
        require(not ancestor.is_symlink() and not ancestor.is_junction(), "PATH_ALIAS")
    return path.resolve()


def relative(value):
    require(type(value) is str and 0 < len(value) <= 512, "MANIFEST_PATH")
    item = PurePosixPath(value)
    require(value != "." and not item.is_absolute() and item.as_posix() == value and
            not any(part in (".", "..", ".git", ".codex", ".aws") for part in item.parts) and
            "\\" not in value and ":" not in value, "MANIFEST_PATH")
    return value


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def read_json(path):
    with no_alias(path).open("rb") as stream:
        raw = stream.read(MAX_JSON + 1)
    require(len(raw) <= MAX_JSON, "JSON_BOUND")
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(Reject("NONFINITE_JSON")))


def identity(path):
    path = no_alias(path)
    require(path.is_file(), "MANIFEST_FILE_MISSING")
    sha, count = hashlib.sha256(), 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            count += len(block)
            require(count <= MAX_FILE, "MANIFEST_FILE_BOUND")
            sha.update(block)
    return {"bytes": count, "sha256": sha.hexdigest()}


def validate_handoff(handoff, consumer, task_id, plan_version):
    require(type(handoff) is dict and handoff.get("schema") == "NIGHT_HANDOFF_V1", "HANDOFF_SCHEMA")
    for key in ("handoff_id", "task_id", "plan_version", "producer", "consumer", "result_commit", "base_commit", "manifest"):
        require(key in handoff, "HANDOFF_FIELD:" + key)
    require(handoff["consumer"] == consumer and consumer in ("M1", "M2", "M3"), "HANDOFF_CONSUMER")
    require(handoff["task_id"] == task_id and handoff["plan_version"] == plan_version, "HANDOFF_VERSION")
    require(type(handoff["handoff_id"]) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,120}", handoff["handoff_id"]), "HANDOFF_ID")
    require(handoff["producer"] in ("M1", "M2", "M3"), "HANDOFF_PRODUCER")
    for key in ("base_commit", "result_commit"):
        require(type(handoff[key]) is str and re.fullmatch("[0-9a-f]{40}", handoff[key]), "FULL_COMMIT_REQUIRED")
    require(type(handoff["manifest"]) is list and 0 < len(handoff["manifest"]) <= 4096, "MANIFEST_FIELDS")
    names, total = set(), 0
    for entry in handoff["manifest"]:
        require(type(entry) is dict and set(entry) == {"path", "bytes", "sha256"}, "MANIFEST_DESCRIPTOR")
        name = relative(entry["path"])
        require(name.casefold() not in names, "MANIFEST_DUPLICATE")
        names.add(name.casefold())
        require(type(entry["bytes"]) is int and 0 <= entry["bytes"] <= MAX_FILE, "MANIFEST_SIZE")
        require(type(entry["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", entry["sha256"]), "MANIFEST_SHA")
        total += entry["bytes"]
    require(total <= MAX_TOTAL, "MANIFEST_TOTAL_BOUND")
    # The complete commit participates; no abbreviated-prefix deduplication.
    return digest([handoff["handoff_id"], handoff["result_commit"], consumer])


class Store:
    """One local writer, atomic state containing receipt/checkpoint/outbox.

    Caller owns the directory and records original START/Goal separately.
    No external work is executed by advance or any outbox method.
    """

    def __init__(self, root, *, consumer="M3", owner="night_task_1"):
        self.root = Path(root)
        self.consumer, self.owner = consumer, owner

    @contextmanager
    def lock(self):
        root = no_alias(self.root)
        require(root.is_relative_to(OUTPUT), "STORE_OUTPUT_SCOPE")
        root.mkdir(parents=True, exist_ok=True)
        lock = no_alias(root / "writer.lock")
        token = uuid.uuid4().hex
        raw = canonical({"token": token, "pid": os.getpid(), "owner": self.owner}) + b"\n"
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise Reject("SINGLE_WRITER_LOCK_HELD") from error
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            yield
        finally:
            # A crashed writer leaves its lock for identity-checked coordinator recovery.
            require(no_alias(lock).read_bytes() == raw, "LOCK_OWNER_CHANGED")
            lock.unlink()

    def _read(self):
        path = no_alias(self.root / "STATE.json")
        if not path.exists():
            return {"schema": STORE_SCHEMA, "consumer": self.consumer, "revision": 0,
                    "receipts": {}, "outbox": {}, "advance_count": 0}
        state = read_json(path)
        require(type(state) is dict and set(state) == {"schema", "consumer", "revision", "receipts", "outbox", "advance_count"}, "STATE_FIELDS")
        require(state["schema"] == STORE_SCHEMA and state["consumer"] == self.consumer, "STATE_IDENTITY")
        require(type(state["revision"]) is int and state["revision"] >= 0 and
                type(state["receipts"]) is dict and type(state["outbox"]) is dict, "STATE_SHAPE")
        require(state["advance_count"] == sum(item["advance_count"] for item in state["receipts"].values()) and
                all(item["status"] == "RECEIVED" and type(item["advance_count"]) is int and
                    item["advance_count"] in (0, 1) for item in state["receipts"].values()), "STATE_RECEIPTS")
        for key, item in state["receipts"].items():
            require(key == digest([item["handoff_id"], item["result_commit"], self.consumer]) and
                    item["consumer"] == self.consumer and item["remote_verified"] is False, "STATE_RECEIPT_IDENTITY")
        for key, item in state["outbox"].items():
            require(type(item["attempts"]) is int and 0 <= item["attempts"] <= 2 and
                    len(item["history"]) <= item["attempts"] and item["remote_verified"] is False, "STATE_OUTBOX")
            require(key == digest([item["handoff"]["handoff_id"], item["handoff"]["result_commit"], item["handoff"]["consumer"]]) and
                    item["remote"] == "origin" and item["branch"] == "develop" and item["max_retries"] == 1 and
                    item["binding_sha256"] == digest({"handoff": item["handoff"], "remote": item["remote"], "branch": item["branch"]}),
                    "STATE_OUTBOX_IDENTITY")
        return state

    def _write(self, state):
        state["revision"] += 1
        raw = canonical(state) + b"\n"
        require(len(raw) <= MAX_JSON, "STATE_SIZE_BOUND")
        target = no_alias(self.root / "STATE.json")
        staging = no_alias(self.root / ("state-" + uuid.uuid4().hex + ".tmp"))
        with staging.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        # Readers see either the complete old snapshot or the complete new snapshot.
        # Failed/incomplete staging files are retained; never replay them implicitly.
        os.replace(staging, target)

    def snapshot(self):
        with self.lock():
            return copy.deepcopy(self._read())

    def receive(self, handoff, content_root, *, task_id, plan_version, origin):
        require(self.consumer == "M3", "INTAKE_ROLE")
        require(origin in ("LOCAL_SYNTHETIC", "LOCAL_REPOSITORY_SNAPSHOT"), "INTAKE_ORIGIN")
        key = validate_handoff(handoff, self.consumer, task_id, plan_version)
        handoff_sha = digest(handoff)
        root = no_alias(content_root)
        with self.lock():
            state = self._read()
            if key in state["receipts"]:
                receipt = state["receipts"][key]
                require(receipt["handoff_sha256"] == handoff_sha, "HANDOFF_KEY_COLLISION")
                return {"status": "DUPLICATE", "key": key, "receipt": copy.deepcopy(receipt), "remote_verified": False}
            checked = []
            for entry in handoff["manifest"]:
                path = no_alias(root / entry["path"])
                require(path.is_relative_to(root) and not path.is_relative_to(no_alias(self.root)), "MANIFEST_PATH_SCOPE")
                actual = identity(path)
                require(actual["bytes"] == entry["bytes"], "MANIFEST_BYTES_MISMATCH:" + entry["path"])
                require(actual["sha256"] == entry["sha256"], "MANIFEST_SHA_MISMATCH:" + entry["path"])
                checked.append(copy.deepcopy(entry))
            receipt = {"schema": "NIGHT_HANDOFF_RECEIPT_V1", "status": "RECEIVED", "key": key, "handoff_id": handoff["handoff_id"],
                       "task_id": handoff["task_id"], "plan_version": handoff["plan_version"],
                       "producer": handoff["producer"], "base_commit": handoff["base_commit"],
                       "result_commit": handoff["result_commit"], "consumer": self.consumer,
                       "handoff_sha256": handoff_sha, "manifest": checked, "origin": origin,
                       "received_utc": now(), "advance_count": 0, "remote_verified": False,
                       "accepted": False, "integrated": False}
            state["receipts"][key] = receipt
            self._write(state)
            return {"status": "RECEIVED", "key": key, "receipt": copy.deepcopy(receipt), "remote_verified": False}

    def advance(self, key):
        with self.lock():
            state = self._read()
            require(key in state["receipts"] and state["receipts"][key]["status"] == "RECEIVED", "RECEIVED_REQUIRED")
            receipt = state["receipts"][key]
            if receipt["advance_count"] == 1:
                return {"status": "ALREADY_ADVANCED", "key": key, "advance_count": 1}
            receipt["advance_count"] = 1
            receipt["advanced_utc"] = now()
            state["advance_count"] += 1
            self._write(state)
            return {"status": "ADVANCED", "key": key, "advance_count": 1}

    def enqueue(self, handoff, *, task_id, plan_version, remote="origin", branch="develop"):
        require(type(handoff) is dict, "HANDOFF_SCHEMA")
        key = validate_handoff(handoff, handoff.get("consumer"), task_id, plan_version)
        require(remote == "origin" and branch == "develop", "OUTBOX_TARGET")
        with self.lock():
            state = self._read()
            binding = {"handoff": copy.deepcopy(handoff), "remote": remote, "branch": branch}
            if key in state["outbox"]:
                require(state["outbox"][key]["binding_sha256"] == digest(binding), "OUTBOX_KEY_COLLISION")
                return copy.deepcopy(state["outbox"][key])
            item = {"key": key, **binding, "binding_sha256": digest(binding), "status": "PUSH_PENDING",
                    "attempts": 0, "max_retries": 1, "history": [], "remote_verified": False,
                    "next_action": "Coordinator may start bounded first send; engine sends nothing"}
            state["outbox"][key] = item
            self._write(state)
            return copy.deepcopy(item)

    def begin_attempt(self, key):
        with self.lock():
            state = self._read()
            require(key in state["outbox"], "OUTBOX_MISSING")
            item = state["outbox"][key]
            require(item["status"] != "UNKNOWN", "UNKNOWN_REQUIRES_REMOTE_CHECK")
            require(item["status"] == "PUSH_PENDING", "SEND_NOT_READY")
            require(item["attempts"] < 2, "RETRY_LIMIT")
            item["attempts"] += 1
            item["status"] = "IN_FLIGHT"
            item["next_action"] = "Persist actual adapter response; interrupted in-flight remains UNKNOWN on recovery"
            self._write(state)
            return copy.deepcopy(item)

    def finish_attempt(self, key, *, outcome, error, argv, exit_code, elapsed_seconds, origin):
        require(outcome in ("FAILED_TEMPORARY", "UNKNOWN", "DENIED", "NON_FAST_FORWARD", "REJECTED", "SUCCESS_REPORTED"), "SEND_OUTCOME")
        require(origin in ("LOCAL_SYNTHETIC", "ACTUAL_ADAPTER_REPORTED"), "SEND_ORIGIN")
        require(type(error) is str and type(argv) is list and bool(argv) and
                all(type(arg) is str for arg in argv), "SEND_EVIDENCE")
        require(exit_code is None or type(exit_code) is int, "SEND_EXIT")
        require(type(elapsed_seconds) in (int, float) and math.isfinite(elapsed_seconds) and elapsed_seconds >= 0, "NETWORK_ELAPSED")
        with self.lock():
            state = self._read()
            require(key in state["outbox"], "OUTBOX_MISSING")
            item = state["outbox"][key]
            require(item["status"] == "IN_FLIGHT", "SEND_NOT_IN_FLIGHT")
            item["history"].append({"attempt": item["attempts"], "outcome": outcome, "error": error,
                                    "argv": copy.deepcopy(argv), "exit_code": exit_code,
                                    "elapsed_seconds": elapsed_seconds, "network_limit_seconds": 30,
                                    "network_budget_exceeded": elapsed_seconds > 30,
                                    "origin": origin, "recorded_utc": now()})
            if outcome == "FAILED_TEMPORARY":
                item["status"] = "PUSH_PENDING" if item["attempts"] < 2 else "RETRY_EXHAUSTED"
                item["next_action"] = "At most one bounded retry" if item["attempts"] < 2 else "Stop sends; preserve outbox"
            elif outcome == "UNKNOWN":
                item["status"], item["next_action"] = "UNKNOWN", "Coordinator must fetch/query exact commit containment before any resend"
            else:
                item["status"] = "AWAITING_REMOTE_VERIFICATION" if outcome == "SUCCESS_REPORTED" else "STOPPED_" + outcome
                item["next_action"] = "Coordinator verifies actual remote containment; no automatic resend"
            self._write(state)
            return copy.deepcopy(item)

    def recover_in_flight(self):
        """After separately verified removal of owned stale lock, never resend blindly."""
        with self.lock():
            state = self._read()
            changed = []
            for key, item in state["outbox"].items():
                if item["status"] == "IN_FLIGHT":
                    item["status"] = "UNKNOWN"
                    item["next_action"] = "Interrupted send: query exact remote containment; do not resend"
                    changed.append(key)
            if changed:
                self._write(state)
            return {"status": "RECOVERED_LOCAL_STATE", "unknown_keys": changed, "remote_verified": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--handoff", required=True, type=Path)
    parser.add_argument("--content-root", required=True, type=Path)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--plan-version", required=True)
    parser.add_argument("--origin", required=True, choices=("LOCAL_SYNTHETIC", "LOCAL_REPOSITORY_SNAPSHOT"))
    args = parser.parse_args()
    result = Store(args.store).receive(read_json(args.handoff), args.content_root,
                                      task_id=args.task_id, plan_version=args.plan_version, origin=args.origin)
    print(canonical(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
