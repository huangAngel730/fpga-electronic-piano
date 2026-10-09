"""Replay M2's software counterexamples against old/current/in-memory mutants.

Historical sources are supplied as raw git-show stdout, never checked out. These
are Python behavior mutants, NOT the compiled RTL mutants still required by B1.
"""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import types


HERE = Path(__file__).resolve().parent


def load_source(name, raw, path):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def expect_error(action, code):
    try:
        action()
    except ValueError as error:
        assert str(error) == code, str(error)
        return
    raise AssertionError("INVALID_INPUT_ACCEPTED")


def check_cases(protocol, inventory):
    def model(rows=None):
        rows = rows or [(1, 1, 1)] * 4
        kwargs = {"drain_limit": 8} if hasattr(protocol.ProtocolOracle, "drain_step") else {}
        return protocol.ProtocolOracle(rows, **kwargs)

    def constructor(field, bad):
        row = [1, 1, 1]
        row[field] = bad
        expect_error(lambda: model([tuple(row)] * 4), "IDENTITY_WIDTH")

    def tags():
        target = model()
        target.begin(1)
        tag = target.issue(1)
        for field in ("slot", "source", "channel", "generation", "request"):
            for value in (True, 1.0):
                assert target.accept(replace(tag, **{field: value}), 99) is False, field
        assert target.scratch == {}

    def replace_boundary():
        target = model()
        expect_error(lambda: target.replace(0, True, 1, 1), "IDENTITY_WIDTH")

    def pedal_boundary():
        target = model()
        expect_error(lambda: target.pedal(True, 1, True), "PEDAL_INPUT")

    def cancel_same_request():
        target = model()
        target.begin(7)
        old = target.issue(0)
        target.cancel()
        expect_error(lambda: target.begin(7), "DRAIN_REQUIRED")
        assert target.accept(old, 99) is False

    cases = (
        ("constructor_source_bool", lambda: constructor(0, True)),
        ("constructor_source_float", lambda: constructor(0, 0.5)),
        ("constructor_generation_bool", lambda: constructor(2, True)),
        ("strict_tag_types", tags),
        ("N_float_controlled_error", lambda: expect_error(lambda: inventory.slot_width(4.0), "N_NOT_SUPPORTED")),
        ("replace_identity_type", replace_boundary),
        ("pedal_identity_type", pedal_boundary),
        ("cancel_same_request", cancel_same_request),
    )
    records = []
    for name, action in cases:
        try:
            action()
            records.append({"case": name, "rule_satisfied": True})
        except Exception as error:
            records.append({"case": name, "rule_satisfied": False,
                            "observed": f"{type(error).__name__}: {error}"})
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("current", "historical", "mutant_type", "mutant_drain"), required=True)
    parser.add_argument("--old-inventory", type=Path)
    parser.add_argument("--old-oracle", type=Path)
    args = parser.parse_args()
    if args.mode == "historical":
        inventory_raw = args.old_inventory.read_bytes()
        protocol_raw = args.old_oracle.read_bytes()
    else:
        inventory_raw = (HERE / "inventory.py").read_bytes()
        protocol_raw = (HERE / "protocol_oracle.py").read_bytes()
    original_sha = hashlib.sha256(protocol_raw).hexdigest()
    if args.mode == "mutant_type":
        old = b"return type(value) is int and 0 <= value < 2**width"
        new = b"return 0 <= value < 2**width"
    elif args.mode == "mutant_drain":
        old = b"self.draining = True"
        new = b"self.draining = False"
    else:
        old = new = None
    if old is not None:
        assert protocol_raw.count(old) == 1, "MUTANT_ANCHOR_NOT_UNIQUE"
        protocol_raw = protocol_raw.replace(old, new)
    inv = load_source("inventory", inventory_raw, HERE / "inventory.py")
    protocol = load_source("review_target", protocol_raw, HERE / "protocol_oracle.py")
    records = check_cases(protocol, inv)
    failed = {row["case"] for row in records if not row["rule_satisfied"]}
    designated = {"mutant_type": "strict_tag_types", "mutant_drain": "cancel_same_request"}.get(args.mode)
    if args.mode == "historical":
        code = 0 if len(failed) == len(records) else 1
        status = "HISTORICAL_DEFECTS_REPRODUCED" if code == 0 else "REPRODUCTION_MISMATCH"
    elif designated:
        code = 2 if designated in failed else 1
        status = "PYTHON_MUTANT_DESIGNATED_REJECT" if code == 2 else "MUTANT_NOT_DETECTED"
    else:
        code = 0 if not failed else 1
        status = "REPAIR_PROBES_PASS" if code == 0 else "FAIL"
    print(json.dumps({"mode": args.mode, "status": status, "exit_code": code,
                      "source_compiled": True, "original_oracle_sha256": original_sha,
                      "executed_oracle_sha256": hashlib.sha256(protocol_raw).hexdigest(),
                      "inventory_sha256": hashlib.sha256(inventory_raw).hexdigest(),
                      "designated_checker": designated, "cases": records,
                      "scope": "Python only; historical exit0 means known defects reproduced, not correctness"}, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
