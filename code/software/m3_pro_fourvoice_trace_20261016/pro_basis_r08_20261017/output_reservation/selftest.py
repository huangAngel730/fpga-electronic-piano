"""Coordinator-only S atomic file/thread cases; no subprocesses."""
import copy
import importlib.util
from pathlib import Path
import sys
import threading

_p = Path(__file__).resolve().parents[1] / "plan_consumption_guard/m3r08_common.py"
if "_m3r08_common" not in sys.modules:
    _s = importlib.util.spec_from_file_location("_m3r08_common", _p)
    _m = importlib.util.module_from_spec(_s); sys.modules[_s.name] = _m; _s.loader.exec_module(_m)
c = sys.modules["_m3r08_common"]
m = c.load_component("output_reservation", "m3r08_04")
f = c.load_component("plan_consumption_guard", "m3r08_fixture_builders")


def run_case(case_id, output_dir):
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=False)
    base = f.reservation_request(out)
    success, failure = copy.deepcopy(base), copy.deepcopy(base)
    success.update(action="FINALIZE", outcome="SUCCESS")
    failure.update(action="FINALIZE", outcome="FAILURE")
    expected, initial = "ACCEPT", []
    if case_id == "04_reserve_finalize": operations = [base, success]
    elif case_id == "04_replay_claim": operations, expected = [base, copy.deepcopy(base)], "REJECT:ALREADY_CLAIMED_OR_CONSUMED"
    elif case_id == "04_failed_cannot_reset": operations, expected = [base, failure, copy.deepcopy(base)], "REJECT:ALREADY_CLAIMED_OR_CONSUMED"
    elif case_id == "04_nonce_mismatch":
        success["nonce"] = "b" * 32
        operations, expected = [base, success], "REJECT:CLAIM_IDENTITY_MISMATCH"
    elif case_id == "04_escape":
        base["root"] = str(c.ROOT)
        operations, expected = [base], "REJECT:RESERVATION_SCOPE"
    elif case_id == "04_existing_output":
        path = Path(base["root"]) / "outputs" / base["capture_id"] / "original.txt"
        path.parent.mkdir(parents=True, exist_ok=False); path.write_bytes(b"KEEP ORIGINAL\n")
        initial.append(c.identity(path))
        operations, expected = [base], "REJECT:OUTPUT_EXISTS_OR_ALIAS"
    else:
        c.need(case_id == "04_thread_race", "UNKNOWN_CASE")
        operations = [copy.deepcopy(base) for _ in range(4)]
    request = {"schema": "M3_R08_RESERVATION_CASE_INPUT_V1", "operations": operations, "initial_files": initial}
    def scenario(data):
        results = []
        if case_id == "04_thread_race":
            barrier, lock = threading.Barrier(4), threading.Lock()
            def contender(operation):
                try:
                    barrier.wait(timeout=2)
                    item = m.evaluate(operation)
                except c.CheckError as error:
                    item = c.result("RACE_REJECT", "REJECT", reason=error.code)
                except Exception as error:
                    item = c.result("RACE_UNEXPECTED", "UNEXPECTED", error=repr(error))
                with lock: results.append(item)
            threads = [threading.Thread(target=contender, args=(operation,)) for operation in data["operations"]]
            for thread in threads: thread.start()
            for thread in threads: thread.join(timeout=3)
            c.write_json(out / "RACE_ACTUAL.json", results)
            c.need(not any(t.is_alive() for t in threads) and len(results) == 4 and
                   sum(r["status"] == "ACCEPT" for r in results) == 1 and
                   sum(r.get("reason") == "ALREADY_CLAIMED_OR_CONSUMED" for r in results) == 3, "ATOMIC_RACE")
        else:
            for i, operation in enumerate(data["operations"], 1):
                try:
                    item = m.evaluate(operation)
                except c.CheckError as error:
                    c.write_json(out / (f"STEP_{i:02d}_ACTUAL.json"), c.result("STEP_REJECT", "REJECT", reason=error.code))
                    raise
                c.write_json(out / (f"STEP_{i:02d}_ACTUAL.json"), item)
                results.append(item)
        return c.result("M3_R08_RESERVATION_SEQUENCE_V1", steps=results)
    return c.run_case_record(case_id, out, expected, request, scenario)
