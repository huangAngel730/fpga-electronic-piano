"""Shared R08-A file/JSON helpers. Import creates no files or processes."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[5]
SOFT = ROOT / "code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017"
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017"
C6 = ROOT / "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/r06_public_chain_20261017/SOURCE_CLOSURE_R06C6.zip"
C6_SHA = "155177a23ae724a1c8d9a0ca3480781d0b76ae62f5a95f59c65a15a96e0d70e4"


class CheckError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def need(ok, code):
    if not ok:
        raise CheckError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pairs(items):
    out = {}
    for key, value in items:
        need(key not in out, "DUPLICATE_JSON_KEY")
        out[key] = value
    return out


def parse(raw):
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(CheckError("NONFINITE_JSON")))


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def identity(path):
    path = Path(path)
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(raw), "sha256": digest(raw)}


def no_alias(path):
    for part in (Path(path), *Path(path).parents):
        need(not part.is_symlink() and not part.is_junction(), "PATH_ALIAS")


def relative(value):
    need(type(value) is str and value and "\\" not in value and ":" not in value, "PATH_ESCAPE")
    p = PurePosixPath(value)
    need(not p.is_absolute() and ".." not in p.parts and "." != value, "PATH_ESCAPE")
    return p.as_posix()


def checked_file(entry, external=False):
    need(type(entry) is dict and {"path", "sha256"} <= set(entry), "FILE_IDENTITY_REQUIRED")
    path = Path(entry["path"])
    if not path.is_absolute():
        path = ROOT / relative(entry["path"])
    no_alias(path)
    path = path.resolve()
    need(external or path.is_relative_to(ROOT), "PATH_ESCAPE")
    need(path.is_file(), "FILE_MISSING")
    actual = identity(path)
    need(actual["sha256"] == entry["sha256"] and
         ("bytes" not in entry or actual["bytes"] == entry["bytes"]), "FILE_IDENTITY_MISMATCH")
    return path, actual


def archive(entry, prefix="inputs/"):
    path, ident = checked_file(entry)
    payload, folded = {}, set()
    total = 0
    with zipfile.ZipFile(path) as z:
        for item in z.infolist():
            if item.is_dir():
                continue
            name = relative(item.filename)
            need(name.casefold() not in folded and (item.external_attr >> 16) & 0o170000 != 0o120000,
                 "ZIP_DUPLICATE_OR_SYMLINK")
            folded.add(name.casefold())
            total += item.file_size
            need(total <= 64 * 1024 * 1024 and item.file_size <= 16 * 1024 * 1024, "ZIP_SIZE_LIMIT")
            if name.startswith(prefix):
                payload[name[len(prefix):]] = z.read(item)
    return payload, ident


def load_component(directory, name):
    key = "_" + name
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, SOFT / directory / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")


def fixture(out, name, raw):
    path = Path(out) / "inputs" / relative(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as f:
        f.write(raw)
    return identity(path)


def result(schema, status="ACCEPT", **kwargs):
    return {"schema": schema, "status": status, "real_pass": False,
            "board_release_allowed": False, **kwargs}


def run_case_record(case_id, output_dir, expected, request, function, assertion=None):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "INPUT.json", request)
    try:
        actual = function(request)
        outcome = actual["status"]
    except CheckError as error:
        actual = result("M3_R08_REJECTION_V1", "REJECT", reason=error.code)
        outcome = "REJECT:" + error.code
    except Exception as error:
        write_json(out / "ACTUAL.json", result("M3_R08_UNEXPECTED_FAILURE_V1", "UNEXPECTED_ERROR",
                                               error=type(error).__name__ + ":" + str(error)))
        raise
    write_json(out / "ACTUAL.json", actual)
    need(outcome == expected, "CASE_EXPECTATION_MISMATCH:" + outcome + ":" + expected)
    if assertion:
        assertion(actual)
    receipt = {"case_id": case_id, "expected": expected, "actual": outcome, "passed": True,
               "pending_is_real_success": False, "real_pass": False, "board_release_allowed": False}
    write_json(out / "CASE_RECEIPT.json", receipt)
    for name, value in actual.get("artifacts", {}).items():
        write_json(out / relative(name), value)
    return receipt


def cli(function):
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        raw = args.request.read_bytes()
        with (args.output / "INPUT.raw.json").open("xb") as stream:
            stream.write(raw)
        request = parse(raw)
        need(type(request) is dict, "REQUEST_OBJECT_REQUIRED")
        write_json(args.output / "INPUT.json", request)
        actual = function(request)
    except CheckError as error:
        actual = result("M3_R08_REJECTION_V1", "REJECT", reason=error.code)
    except (KeyError, TypeError, OSError, UnicodeError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        actual = result("M3_R08_REJECTION_V1", "REJECT", reason="MALFORMED_REQUEST_OR_FILE",
                        detail=type(error).__name__)
    write_json(args.output / "RESULT.json", actual)
    for name, value in actual.get("artifacts", {}).items():
        write_json(args.output / relative(name), value)
    print(canonical(actual))
    return 2 if actual["status"] == "REJECT" else 3 if actual["status"].startswith("PENDING") else 0
