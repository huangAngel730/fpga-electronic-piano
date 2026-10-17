"""Pure R6-4 consumer reuse; never calls its run/Job/worker/Popen route."""
import ast
import importlib.util
from pathlib import Path
import sys
import types

_path = Path(__file__).with_name("m3r08_common.py")
if "_m3r08_common" not in sys.modules:
    _spec = importlib.util.spec_from_file_location("_m3r08_common", _path)
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = _module
    _spec.loader.exec_module(_module)
c = sys.modules["_m3r08_common"]
LEGACY = c.ROOT / "code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/tool_plan_adapter/r07_fix/consumer.py"
LEGACY_SHA = "56ba0c5615cbe98094e5d37dc72e9e92002ce4976169723b2fd6f5ba8217bb69"
BASE = LEGACY.parent.parent / "plan_adapter.py"
BASE_SHA = "bb29b19984c75a49a102b3481dff6d53403af14bb5671fffb9db587dd6cbbbcc"


def pure_module(path, expected_sha, constants, definitions, name):
    """Select untouched AST nodes from pinned source; no algorithm rewriting."""
    raw = path.read_bytes()
    c.need(c.digest(raw) == expected_sha, "SIGNED_VALIDATOR_CHANGED")
    tree = ast.parse(raw.decode("utf-8"), filename=str(path))
    allowed_imports = {"__future__", "hashlib", "json", "pathlib", "re", "sys"}
    selected, removed, found = [], [], set()
    node_hashes, ranges = {}, {}
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name.split(".")[0] for a in node.names] if isinstance(node, ast.Import) else [node.module]
            if all(x in allowed_imports for x in names):
                selected.append(node)
            else:
                removed.extend(names)
        elif isinstance(node, ast.Assign) and all(isinstance(t, ast.Name) and t.id in constants for t in node.targets):
            selected.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in definitions:
            selected.append(node); found.add(node.name)
            node_hashes[node.name] = c.digest(ast.dump(node, include_attributes=False).encode("utf-8"))
            ranges[node.name] = {"start": node.lineno, "end": node.end_lineno}
    c.need(found == set(definitions), "PURE_AST_DEFINITION_SET")
    derived = ast.Module(body=selected, type_ignores=[])
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(ast.fix_missing_locations(derived), str(path), "exec"), module.__dict__)
    audit = {"original": c.identity(path), "selected_definitions": sorted(found),
             "selected_constants": sorted(constants), "removed_imports": sorted(removed),
             "definition_AST_sha256": node_hashes,
             "definition_source_ranges": ranges,
             "derived_AST_sha256": c.digest(ast.dump(derived, include_attributes=False).encode("utf-8")),
             "derived_source_sha256": c.digest(ast.unparse(derived).encode("utf-8")),
             "module_globals": sorted(k for k in module.__dict__ if not k.startswith("__")),
             "normalization_algorithm_nodes_changed": False}
    return module, audit


def validator(validation_root):
    """Fresh read-only module; only relocate pure validation evidence scope.

    Fixed worker/cwd/runtime/source requirements remain from the signed module.
    The caller cannot select an alternate implementation or execution function.
    """
    c.need(c.identity(LEGACY)["sha256"] == LEGACY_SHA, "SIGNED_VALIDATOR_CHANGED")
    root = Path(validation_root)
    c.no_alias(root)
    root = root.resolve()
    c.need(root.is_relative_to(c.DOC / "plan_consumption_guard") or
           root.is_relative_to(c.DOC / "coordinator"), "VALIDATION_SCOPE")
    base, base_audit = pure_module(BASE, BASE_SHA,
        {"HERE", "ROOT", "DOCS", "TB", "WORKER", "PYTHON", "JOB_HELPER", "JOB_HELPER_SHA", "SPEC_SCHEMA", "PLAN_SCHEMA", "FIXTURE_AUTHORITY", "ROLES"},
        {"Refusal", "sha256_bytes", "identity", "is_within", "repo_path", "declared_file", "output_paths", "normalize_spec"}, "_m3r08_legacy_normalize_only")
    module, consumer_audit = pure_module(LEGACY, LEGACY_SHA,
        {"HERE", "ROOT", "DOC", "TRUST_PATH", "TRUST_SHA", "PLAN_SCHEMA"},
        {"Refusal", "need", "digest", "identity", "pairs", "parse", "canonical", "no_alias", "repo_file", "pinned_runtime", "rebuild", "audit"}, "_m3r08_signed_pure_guard")
    module.DOC = root
    base.DOCS = root
    module.load_legacy = lambda: base
    module.pure_derivation = {"legacy": base_audit, "consumer": consumer_audit,
                              "scope": "PURE_VALIDATION_ONLY_NEW_R08_ROOT; NO_EXECUTION_SPEC_ADMISSION"}
    return module


def evaluate(request):
    c.need(request.get("schema") == "M3_R08_GUARD_REQUEST_V1", "GUARD_SCHEMA")
    c.need(set(request) == {"schema", "validation_root", "spec", "plan", "requested_action"}, "GUARD_REQUEST_FIELDS")
    c.need(request["requested_action"] == "VALIDATE_ONLY", "EXECUTION_ACTION_FORBIDDEN")
    module = validator(request["validation_root"])
    spec_path, spec_id = c.checked_file(request["spec"])
    plan_path, plan_id = c.checked_file(request["plan"])
    try:
        plan, audit = module.audit(plan_path.relative_to(c.ROOT).as_posix(), plan_id["sha256"],
                                   spec_path.relative_to(c.ROOT).as_posix(), spec_id["sha256"])
    except Exception as error:
        raise c.CheckError("SIGNED_GUARD_REJECT:" + str(error)) from error
    return c.result("M3_R08_PURE_PLAN_GUARD_V1", permission="NOT_GRANTED", process_route="ABSENT",
                    reused_validator=c.identity(LEGACY), normalized_plan=plan, audit=audit,
                    pure_derivation=module.pure_derivation,
                    artifacts={"guard_receipt.json": {"spec": spec_id, "plan": plan_id,
                               "compared_fields": audit["compared_fields"], "execution_allowed": False},
                               "pure_import_derivation.json": module.pure_derivation})


if __name__ == "__main__":
    raise SystemExit(c.cli(evaluate))
