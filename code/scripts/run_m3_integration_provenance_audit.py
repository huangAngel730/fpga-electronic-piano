"""Read-only GPRJ/independently approved manifest audit; no build/STA claims."""
from __future__ import annotations

import argparse
import hashlib
import json
import ntpath
from pathlib import Path, PureWindowsPath
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
KINDS = {"source", "include", "rom", "cst", "sdc"}
ORIGINS = {"repository", "isolated_candidate", "approved_external", "approved_production_stage"}
SHA = re.compile(r"[0-9a-fA-F]{64}\Z")


class AuditError(ValueError):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.details = {"code": code, "message": message, **details}


def require(condition, code, message, **details):
    if not condition:
        raise AuditError(code, message, **details)


def digest(path):
    require(path.is_file(), "missing_file", "required file does not exist", actual_path=str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    # Duplicate JSON keys must not silently replace an approved digest or policy.
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate_json_key", "duplicate JSON key", key=key)
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique)


def within(path, root):
    return path == root or root in path.parents


class Resolver:
    """Relocate ONLY an explicitly recorded repository root; never basename-map."""
    def __init__(self, root, manifest):
        self.root = root.resolve(strict=True)
        require(self.root.is_dir(), "bad_root", "repo root must be a directory")
        self.recorded = manifest.get("recorded_repo_root")
        if self.recorded:
            require(PureWindowsPath(self.recorded).is_absolute(), "bad_recorded_root", "recorded repo root must be an absolute Windows path")
            self.recorded = PureWindowsPath(ntpath.normpath(self.recorded))
        self.external = []
        for item in manifest.get("approved_external_roots", []):
            require(isinstance(item, str) and Path(item).is_absolute(),
                    "bad_external_root", "external root must be an absolute string path")
            path = Path(item).resolve(strict=True)
            require(path.is_dir() and not within(path, self.root), "bad_external_root", "external root must be an explicit existing directory outside repo", path=str(path))
            self.external.append(path)

    def resolve(self, raw, base=None):
        require(isinstance(raw, str) and bool(raw.strip()) and "\x00" not in raw,
                "bad_path", "path must be a nonempty string", path=raw)
        windows = PureWindowsPath(raw)
        relocated = False
        if windows.drive and not windows.is_absolute():
            raise AuditError("ambiguous_path", "drive-relative paths are forbidden", path=raw)
        if windows.is_absolute():
            normal = PureWindowsPath(ntpath.normpath(raw))
            if self.recorded:
                try:
                    relative = normal.relative_to(self.recorded)
                except ValueError:
                    pass
                else:
                    path = self.root.joinpath(*relative.parts).resolve()
                    relocated = True
            if not relocated:
                path = Path(str(normal)).resolve()
        elif Path(raw).is_absolute():
            path = Path(raw).resolve()
        else:
            require(not windows.root, "ambiguous_path", "root-relative path without drive is forbidden", path=raw)
            path = ((base or self.root) / raw.replace("\\", "/")).resolve()
        require(within(path, self.root) or any(within(path, p) for p in self.external),
                "outside_approved_roots", "resolved path escapes independently approved roots", requested_path=raw, actual_path=str(path))
        return path


def synthesis_text(text):
    """Remove declared simulation-only sections, then comments (preserve strings)."""
    active, lines = True, []
    for line in text.splitlines():
        off = re.search(r"(?:synthesis|synopsys)\s+translate_off\b", line)
        on = re.search(r"(?:synthesis|synopsys)\s+translate_on\b", line)
        if off:
            require(active, "bad_translate_region", "nested translate_off unsupported")
            active = False
            continue
        if on:
            require(not active, "bad_translate_region", "unmatched translate_on")
            active = True
            continue
        if active:
            lines.append(line)
    require(active, "bad_translate_region", "unterminated translate_off")
    joined = "\n".join(lines)
    token = re.compile(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*', re.S)
    return token.sub(lambda m: m.group(0) if m.group(0).startswith('"') else " ", joined)


def audit(project_path, manifest_path, root):
    manifest = read_json(manifest_path)
    require(isinstance(manifest, dict), "bad_manifest", "manifest must be an object")
    require(manifest.get("version") == 1, "bad_manifest", "manifest version must be1")
    scope = manifest.get("scope")
    require(scope in ("production", "isolated"), "bad_scope", "scope must explicitly be production or isolated")
    fixture = manifest.get("test_fixture", False)
    require(isinstance(fixture, bool), "bad_fixture_label", "test_fixture must be boolean")
    approval = manifest.get("approval", {})
    require(isinstance(approval, dict) and approval.get("by") == ("TEST_FIXTURE" if fixture else "M2")
            and isinstance(approval.get("reference"), str) and bool(approval["reference"].strip()),
            "missing_approval", "require independently supplied M2 approval reference (or explicitly labeled TEST_FIXTURE)")
    baseline = manifest.get("baseline_commit")
    require(isinstance(baseline, str) and re.fullmatch(r"[0-9a-fA-F]{7,40}", baseline),
            "missing_baseline", "explicit baseline commit required")
    require(isinstance(manifest.get("features"), dict) and manifest["features"],
            "missing_features", "M2 must declare enabled audio/visual feature selection")
    resolver = Resolver(root, manifest)
    hash_maps = {}
    imported = []
    for spec in manifest.get("hash_manifests", []):
        require(isinstance(spec, dict), "bad_hash_manifest", "hash manifest entry must be an object")
        path = resolver.resolve(spec.get("path"))
        expected = spec.get("sha256", "")
        require(isinstance(expected, str) and SHA.fullmatch(expected), "bad_sha", "hash manifest SHA must be independently pinned", path=str(path))
        actual = digest(path)
        require(actual == expected.lower(), "sha_mismatch", "approved hash manifest SHA mismatch", actual_path=str(path), expected_sha256=expected, actual_sha256=actual)
        require(path not in hash_maps, "duplicate_hash_manifest", "duplicate imported hash manifest")
        hash_maps[path] = read_json(path)
        imported.append({"path": str(path), "sha256": actual})

    def expected_hash(spec):
        value = spec.get("sha256")
        ref = spec.get("hash_ref")
        if ref is not None:
            require(isinstance(ref, dict), "bad_hash_ref", "hash_ref must be an object")
            path = resolver.resolve(ref.get("manifest"))
            require(path in hash_maps, "unapproved_hash_manifest", "hash_ref must use an independently pinned hash_manifests entry", actual_path=str(path))
            table = hash_maps[path]
            field = ref.get("field")
            require(isinstance(field, str) and bool(field), "bad_hash_ref", "hash_ref needs an explicit field")
            for key in field.split("."):
                require(isinstance(table, dict) and key in table, "missing_hash_field", "missing field in approved existing manifest", field=ref.get("field"), actual_path=str(path))
                table = table[key]
            require(isinstance(table, dict) and ref.get("key") in table, "missing_hash_key", "exact recorded hash key missing (no basename fallback)", key=ref.get("key"), actual_path=str(path))
            selected = table[ref["key"]]
            if isinstance(selected, dict):
                selected = selected.get("sha256")
            require(value is None or value == selected, "conflicting_hash", "direct SHA conflicts with imported approved SHA")
            value = selected
        require(isinstance(value, str) and SHA.fullmatch(value), "bad_sha", "independently approved raw-byte SHA required", entry=spec.get("path"))
        return value.lower()

    project_spec = manifest.get("project")
    require(isinstance(project_spec, dict), "missing_project", "approved project path and SHA required")
    approved_project = resolver.resolve(project_spec.get("path"))
    require(project_path.resolve(strict=True) == approved_project, "project_path_mismatch", "provided GPRJ does not have the independently approved path", actual_path=str(project_path), expected_path=str(approved_project))
    project_hash = digest(approved_project)
    expected_project_hash = expected_hash(project_spec)
    require(project_hash == expected_project_hash, "sha_mismatch", "GPRJ SHA mismatch", actual_path=str(approved_project), expected_sha256=expected_project_hash, actual_sha256=project_hash)
    synth_cwd = resolver.resolve(manifest.get("synthesis_cwd"))
    require(synth_cwd.is_dir(), "missing_synthesis_cwd", "approved synthesis working directory missing", actual_path=str(synth_cwd))
    specs = manifest.get("files")
    require(isinstance(specs, list) and bool(specs), "empty_file_list", "nonempty independently approved files list required")
    files, records = {}, []
    for spec in specs:
        require(isinstance(spec, dict), "bad_file", "file entry must be an object")
        kind, origin = spec.get("kind"), spec.get("origin")
        require(kind in KINDS and origin in ORIGINS, "bad_file_policy", "explicit supported kind and origin required", entry=spec)
        path = resolver.resolve(spec.get("path"))
        require(path not in files, "duplicate_approved_path", "every approved path must be listed exactly once", actual_path=str(path))
        output_source = within(path, resolver.root / "code/output")
        if origin == "isolated_candidate":
            require(scope == "isolated", "candidate_in_production", "isolated candidate cannot be labeled production", actual_path=str(path))
        if output_source:
            allowed = (scope == "isolated" and origin == "isolated_candidate") or (
                origin == "approved_production_stage" and bool(spec.get("approval_reference")))
            require(allowed, "unapproved_output", "output copy requires explicit isolated or production-stage approval, never basename substitution", actual_path=str(path))
        if origin == "repository":
            require(within(path, resolver.root) and not output_source, "bad_repository_origin", "repository origin must resolve inside non-output repo", actual_path=str(path))
        if origin == "approved_external":
            require(not within(path, resolver.root) and bool(spec.get("approval_reference")), "bad_external_origin", "external source requires explicit approved root and reference", actual_path=str(path))
        if origin == "approved_production_stage":
            require(scope == "production" and output_source and bool(spec.get("approval_reference")),
                    "bad_stage_origin", "production-stage origin requires an output path and explicit production approval", actual_path=str(path))
        expected = expected_hash(spec)
        actual = digest(path)
        require(actual == expected, "sha_mismatch", "raw-byte SHA mismatch (line endings not normalized)", actual_path=str(path), expected_sha256=expected, actual_sha256=actual)
        files[path] = spec
        records.append({"path": str(path), "recorded_path": spec["path"], "kind": kind, "origin": origin, "sha256": actual})
    project_text = approved_project.read_text(encoding="utf-8-sig")
    require(not re.search(r"<!\s*(?:ENTITY|DOCTYPE)\b", project_text, re.I),
            "unsafe_xml", "external/entity XML input unsupported")
    # Existing prepare scripts already accommodate historical Gowin XML version1.
    project_text = project_text.replace('<?xml version="1"', '<?xml version="1.0"')
    tree = ET.fromstring(project_text)
    require(tree.tag == "Project" and len(tree.findall("FileList")) == 1, "bad_gprj", "expected one Gowin Project/FileList")
    enabled, disabled = {}, []
    type_kinds = {"file.verilog": "source", "file.systemverilog": "source", "file.vhdl": "source",
                  "file.cst": "cst", "file.sdc": "sdc", "file.mem": "rom", "file.hex": "rom"}
    for node in tree.findall("FileList/File"):
        require(node.get("enable") in ("0", "1"), "bad_enable", "GPRJ must explicitly mark each File enable0/1", entry=node.attrib)
        if node.get("enable") == "0":
            disabled.append(node.attrib)
            continue
        path = resolver.resolve(node.get("path"), approved_project.parent)
        require(path not in enabled, "duplicate_enabled_source", "GPRJ enables the same resolved file twice", actual_path=str(path))
        require(path in files, "unlisted_enabled_source", "GPRJ enables a path not approved by manifest", actual_path=str(path), recorded_path=node.get("path"))
        kind = type_kinds.get(node.get("type"))
        require(kind is not None and kind == files[path]["kind"], "file_type_mismatch", "GPRJ type disagrees with approved file kind", actual_path=str(path), gprj_type=node.get("type"), manifest_kind=files[path]["kind"])
        enabled[path] = node.get("type")
    require(enabled, "empty_project", "no enabled GPRJ files")
    for path, spec in files.items():
        if spec["kind"] in ("source", "cst", "sdc"):
            require(path in enabled, "missing_enabled_source", "manifest expected an enabled source/constraint absent from GPRJ", actual_path=str(path))
    require(any(files[p]["kind"] == "cst" for p in enabled) and any(files[p]["kind"] == "sdc" for p in enabled),
            "missing_constraints", "both approved CST and SDC must be enabled")
    by_name = {}
    for path in enabled:
        by_name.setdefault(path.name.casefold(), []).append(path)
    allowances = manifest.get("allowed_duplicate_basenames", [])
    require(isinstance(allowances, list), "bad_duplicate_policy", "duplicate basename exceptions must be exact path lists")
    for name, paths in by_name.items():
        if len(paths) > 1:
            matching = [item for item in allowances if isinstance(item, dict) and item.get("name", "").casefold() == name]
            require(len(matching) == 1 and set(resolver.resolve(p) for p in matching[0].get("paths", [])) == set(paths),
                    "duplicate_basename", "duplicate enabled basename not explicitly approved for these exact paths", basename=name, actual_paths=list(map(str, paths)))
    roles = manifest.get("roles")
    required_roles = manifest.get("required_roles")
    require(isinstance(roles, dict) and bool(roles) and isinstance(required_roles, list) and bool(required_roles),
            "bad_roles", "M2 must specify nonempty roles and required_roles explicitly")
    role_report = {}
    for role, raw in roles.items():
        path = resolver.resolve(raw)
        require(path in enabled and files[path]["kind"] == "source", "role_not_enabled", "feature role must bind an exact enabled source", role=role, actual_path=str(path))
        role_report[role] = next(record for record in records if record["path"] == str(path))
    require(all(isinstance(role, str) and role in role_report for role in required_roles),
            "missing_required_role", "M2-required role missing", expected_roles=required_roles, actual_roles=list(role_report))
    for role in ("parser", "button_counter", "public_fifo", "control_snapshot", "adsr", "strict_flash"):
        role_report.setdefault(role, {"status": "not_declared_by_M2_manifest"})
    include_dirs = [resolver.resolve(p) for p in manifest.get("include_dirs", [])]
    require(all(p.is_dir() for p in include_dirs), "missing_include_dir", "approved include directory missing")
    scanned, modules, dependencies = set(), {}, []

    def dependency(path, reference, kind, from_path):
        require(path in files and files[path]["kind"] == kind, "unapproved_dependency", "synthesis dependency missing from independent manifest", source=str(from_path), reference=reference, actual_path=str(path), expected_kind=kind)
        dependencies.append({"source": str(from_path), "reference": reference, "path": str(path), "kind": kind})

    def scan(path):
        if path in scanned:
            return
        scanned.add(path)
        if path.suffix.lower() not in (".v", ".sv", ".vh", ".svh"):
            raise AuditError("unsupported_source_language", "cannot inspect synthesis dependencies in this source language", actual_path=str(path))
        text = synthesis_text(path.read_text(encoding="utf-8-sig"))
        require(not re.search(r"`(?:pragma\s+)?protect\b", text),
                "encrypted_source", "encrypted HDL needs a separate approved dependency inspection; unsupported here", actual_path=str(path))
        for name in re.findall(r"\bmodule\s+(?:(?:automatic|static)\s+)?([a-zA-Z_]\w*)", text):
            require(name not in modules, "duplicate_module", "duplicate enabled module definition (parser aliases cannot bypass provenance)", module=name, actual_path=str(path), first_path=str(modules.get(name)))
            modules[name] = path
        includes = re.findall(r'`include\s+"([^"\n]+)"', text)
        require(len(includes) == len(re.findall(r"`include\b", text)),
                "unresolved_include", "nonliteral include path cannot be statically audited", actual_path=str(path))
        for reference in includes:
            candidates = []
            for base in [path.parent, *include_dirs]:
                candidate = resolver.resolve(reference, base)
                if candidate.is_file() and candidate not in candidates:
                    candidates.append(candidate)
            require(len(candidates) == 1, "missing_or_ambiguous_include", "synthesis include must resolve uniquely", source=str(path), reference=reference, candidates=list(map(str, candidates)))
            dependency(candidates[0], reference, "include", path)
            scan(candidates[0])
        constants = {}
        for name, literal in re.findall(r'\b(?:parameter|localparam)\s+(?:string\s+)?([A-Za-z_]\w*)\s*=\s*"([^"\n]+)"', text):
            constants.setdefault(name, set()).add(literal)
        for argument in re.findall(r"\$readmem[hb]\s*\(\s*([^,]+),", text):
            expression = argument.strip()
            if re.fullmatch(r'"[^"\n]+"', expression):
                references = [expression[1:-1]]
            else:
                require(re.fullmatch(r"[A-Za-z_]\w*", expression) and expression in constants,
                        "unresolved_synthesis_rom", "ROM expression cannot be statically resolved; M2 must provide auditable constant synthesis path", source=str(path), expression=expression)
                references = sorted(constants[expression])
            for reference in references:
                rom = resolver.resolve(reference, synth_cwd)
                dependency(rom, reference, "rom", path)
                require(rom.is_file(), "missing_rom", "synthesis ROM missing (simulation override is not evidence)", source=str(path), actual_path=str(rom))
        # Named constant ROM overrides in enabled HDL are dependencies too;
        # conservative: defaults and override literals must both be approved.
        for name, reference in re.findall(r'\.([A-Za-z_]\w*)\s*\(\s*"([^"\n]+\.(?:mem|hex))"\s*\)', text):
            rom = resolver.resolve(reference, synth_cwd)
            dependency(rom, f"{name}={reference}", "rom", path)
    for path in enabled:
        if files[path]["kind"] == "source":
            scan(path)
    for path, spec in files.items():
        if spec["kind"] == "include":
            require(path in scanned, "unused_include", "approved include has no enabled synthesis consumer", actual_path=str(path))
    return {"result": "PASS", "label": "TEST_FIXTURE_ONLY" if fixture else ("ISOLATED_CANDIDATE_ONLY" if scope == "isolated" else "PRODUCTION_PROVENANCE_ONLY"),
            "scope": scope, "scope_label": "ISOLATED_CANDIDATE_ONLY" if scope == "isolated" else "PRODUCTION_PROVENANCE_ONLY",
            "validation_level": "L0 source audit / L1 verifier checks, not RTL simulation or STA",
            "baseline_commit": baseline, "approval": approval, "features": manifest["features"],
            "project": {"path": str(approved_project), "sha256": project_hash},
            "manifest": {"path": str(manifest_path.resolve()), "sha256": digest(manifest_path)},
            "repo_root": str(resolver.root), "recorded_repo_root": str(resolver.recorded) if resolver.recorded else None,
            "synthesis_cwd": str(synth_cwd), "imported_hash_manifests": imported,
            "approved_files": records, "enabled_project_file_count": len(enabled),
            "enabled_project_paths": list(map(str, enabled)),
            "disabled_project_entries": disabled, "roles": role_report,
            "synthesis_dependencies": dependencies,
            "claims_excluded": ["algorithm correctness", "synthesis", "PnR", "STA", "board/audio acceptance"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path, help="new JSON output, must not overwrite any existing file")
    args = parser.parse_args()
    try:
        report = audit(args.project, args.manifest, args.repo_root)
        code = 0
    except AuditError as error:
        report, code = {"result": "FAIL", "error": error.details}, 1
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError) as error:
        report, code = {"result": "FAIL", "error": {"code": "invalid_input", "message": str(error)}}, 1
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        try:
            # Exclusive-create protects GPRJ/source/manifest and prior evidence.
            with args.report.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
        except OSError as error:
            print(json.dumps({"result": "FAIL", "error": {"code": "report_write", "message": str(error)}}))
            return 1
    print(text, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
