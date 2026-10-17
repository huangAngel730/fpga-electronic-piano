"""New R6-1 software cases only. No HDL compiler, old checker or DUT execution."""
import copy
import json
import sys
import zipfile
from pathlib import Path

import audit


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fixture(root):
    files = {
        "source_closure/inputs/compile.f": b"leaf.sv\n",
        "source_closure/inputs/leaf.sv": b"module leaf(input wire a, output wire b); assign b=a; endmodule\n",
        "source_closure/candidate/wrapper.sv": b"module wrapper(input wire a, output wire b); leaf u(.a(a), .b(b)); endmodule\n",
        "source_closure/candidate/test.cst": b"// SYNTHETIC not board pins\n",
        "source_closure/candidate/test.sdc": b"# SYNTHETIC not timing approval\n",
        "source_closure/inputs/pll.v": b"// SYNTHETIC PG484 old header\nmodule pll; endmodule\n"
    }
    roms = []
    for index in range(9):
        name = f"source_closure/inputs/rom/{index}.mem"
        files[name] = b"0000\n"
        roms.append({"path": name, "bytes": 5, "sha256": audit.sha(files[name])})
    binding = {"simulation_source_list": {"path": "source_closure/inputs/compile.f",
               "sha256": audit.sha(files["source_closure/inputs/compile.f"])},
               "candidate_top": {"path": "source_closure/candidate/wrapper.sv", "module": "wrapper"},
               "roms": roms, "constraints": [{"path": n, "sha256": audit.sha(v)}
               for n, v in files.items() if n.endswith((".cst", ".sdc"))],
               "pll_ip": {"physical_candidate_path": "source_closure/inputs/pll.v",
               "physical_candidate_sha256": audit.sha(files["source_closure/inputs/pll.v"]),
               "new_pro_ip_generated": False}, "target": {}}
    files["SOURCE_BINDING.json"] = json.dumps(binding).encode()
    manifest = [{"path": n, "bytes": len(v), "sha256": audit.sha(v)} for n, v in files.items()]
    files["MANIFEST.json"] = json.dumps({"files": manifest}).encode()
    archive = root / "SYNTHETIC.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 17, 0, 0, 0))
            z.writestr(info, data)
    return {"mode": "simulation", "assembly": "bound_list_plus_wrapper", "archive": {
            "path": archive.name, "sha256": audit.sha(archive.read_bytes()),
            "manifest_sha256": audit.sha(files["MANIFEST.json"])}}, files


def run(repo, output, real_config):
    output.mkdir(exist_ok=False)
    root = output / "fixtures"
    root.mkdir()
    config, _ = fixture(root)
    cases = []

    def add(label, changes, expected):
        c = copy.deepcopy(config)
        c.update(changes)
        cases.append((label, c, expected))

    def overlay(name, content, **extra):
        p = root / name
        p.write_text(content, encoding="utf-8")
        return {"path": name, "stage_as": "new/" + name,
                "sha256": audit.sha(p.read_bytes()), **extra}

    add("synthetic_static_positive", {}, "STATIC_CLOSURE_READY")
    add("physical_identity_missing", {"mode": "physical"}, "PENDING_PHYSICAL_ID")
    add("wrapper_omitted", {"assembly": "bound_list_only"}, "WRAPPER_NOT_IN_SOURCE_LIST")
    add("missing_leaf", {"remove_sources": ["source_closure/inputs/leaf.sv"]}, "MISSING_MODULE:leaf")
    duplicate = overlay("duplicate.sv", "module leaf; endmodule\n")
    add("duplicate_module", {"candidates": [duplicate]}, "DUPLICATE_MODULE:leaf")
    escaped = dict(duplicate, stage_as="../escape.sv")
    add("stage_path_escape", {"candidates": [escaped]}, "PATH_ESCAPE:")
    add("input_path_escape", {"candidates": [dict(duplicate, path="../escape.sv")]}, "PATH_ESCAPE:")
    add("candidate_sha_drift", {"candidates": [dict(duplicate, sha256="0" * 64)]}, "SHA_MISMATCH:")
    add("candidate_overwrite", {"candidates": [dict(duplicate, stage_as="source_closure/inputs/leaf.sv")]}, "CANDIDATE_OVERWRITE:")
    newleaf = overlay("newleaf.sv", "module leaf(input a, output b); assign b=a; endmodule\n",
                      replaces="source_closure/inputs/leaf.sv")
    add("explicit_new_candidate", {"candidates": [newleaf]}, "STATIC_CLOSURE_READY")
    wrong = overlay("wrong.sv", "module wrapper(input a,output b); leaf x(.NO_PORT(a),.b(b)); endmodule\n",
                    replaces="source_closure/candidate/wrapper.sv")
    add("wrong_named_port", {"candidates": [wrong]}, "UNKNOWN_NAMED_PORT:leaf.NO_PORT")
    include = overlay("include.sv", '`include "absent.svh"\nmodule extra; endmodule\n')
    add("missing_include", {"candidates": [include]}, "MISSING_INCLUDE:")
    rom = overlay("rom.sv", 'module extra; initial $readmemh("rom/missing.mem", x); endmodule\n')
    add("missing_rom_literal", {"candidates": [rom]}, "MISSING_ROM_REFERENCE:")
    macro = overlay("macro.sv", '`ifdef TEST\nmodule extra; endmodule\n`endif\n')
    add("unelaborated_macro_pending", {"candidates": [macro]}, "PENDING_STATIC_ELABORATION")
    comment = overlay("comment.sv", '// module leaf; endmodule\nmodule comment_only; endmodule\n')
    add("comment_not_duplicate", {"candidates": [comment]}, "STATIC_CLOSURE_READY")
    # Freeze generated input files/configs before invoking the implementation.
    for label, c, expected in cases:
        dump(root / (label + ".json"), {"config": c, "expected": expected})
    dump(output / "CASE_PLAN.json", {"synthetic": True, "cases": cases,
         "fixtures": [{"path": p.name, "sha256": audit.sha(p.read_bytes())}
                      for p in sorted(root.iterdir())]})
    results = []
    for label, c, expected in cases:
        try:
            result, payload = audit.audit(c, root)
            found = [result["status"]] + result["errors"]
            if result["board_release_allowed"] or result["pro_dut_pass"]:
                raise AssertionError("false release")
        except audit.Rejected as error:
            result, found = {"status": "REJECTED", "diagnostic": str(error)}, [str(error)]
        passed = any(s.startswith(expected) for s in found)
        dump(output / (label + ".json"), result)
        results.append({"case": label, "expected": expected, "actual": found, "passed": passed})
        print(json.dumps(results[-1]), flush=True)
    # Real original archive is inspected only, not executed. No success requirement
    # hides genuine dependencies/parse limits discovered in the old list.
    real = audit.load(real_config.read_bytes())
    real_results = []
    for assembly, mode in [("bound_list_only", "simulation"),
                           ("bound_list_plus_wrapper", "simulation"),
                           ("bound_list_plus_wrapper", "physical")]:
        c = dict(real, assembly=assembly, mode=mode)
        result, payload = audit.audit(c, repo)
        audit.write_result(result, payload, output / (assembly + "_" + mode))
        real_results.append({"assembly": assembly, "mode": mode, "status": result["status"],
                             "errors": result["errors"], "physical_status": result["physical_status"]})
    ok = all(r["passed"] for r in results)
    ok &= "WRAPPER_NOT_IN_SOURCE_LIST" in real_results[0]["errors"]
    ok &= "WRAPPER_NOT_IN_SOURCE_LIST" not in real_results[1]["errors"]
    ok &= real_results[2]["physical_status"] == "PENDING_PHYSICAL_ID"
    dump(output / "SUMMARY.json", {"software_cases_passed": ok, "cases": results,
         "real_static_intake": real_results, "hdl_calls": 0, "board_release_allowed": False})
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(run(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])))
