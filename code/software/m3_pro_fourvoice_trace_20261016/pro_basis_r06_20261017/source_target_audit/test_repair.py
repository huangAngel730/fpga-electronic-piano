"""One targeted software repair group, not the original fifteen-case suite."""
import json
import sys
from pathlib import Path

import audit
from test_audit import dump, fixture


def run(repo, out, config_path):
    out.mkdir(exist_ok=False)
    root = out / "fixtures"
    root.mkdir()
    config, _ = fixture(root)
    specifications = [
        ("tight_width_ports", "module probe(input logic signed[11:0]bend, output logic[31:0]fcw); endmodule", "ports"),
        ("macro_header_pending", "`define PORTS input a, output b\nmodule probe (`PORTS); endmodule", "macro"),
        ("function_not_instance", "module probe; function automatic performance_event_t encode(input int x); encode=x; endfunction endmodule", "function"),
        ("parameter_rom_pending", 'module probe #(parameter FILE="rom/not_here.mem"); initial $readmemh(FILE, mem); endmodule', "parameter"),
        ("literal_rom_rejected", 'module probe; initial $readmemh("rom/not_here.mem", mem); endmodule', "literal"),
        ("missing_module_rejected", "module probe; missing_leaf u(.a()); endmodule", "missing"),
        ("wrong_port_rejected", "module probe; leaf u(.BAD()); endmodule", "port_error")
    ]
    cases = []
    for label, source, expected in specifications:
        p = root / (label + ".sv")
        p.write_text(source, encoding="utf-8")
        c = dict(config, candidates=[{"path": p.name, "stage_as": "new/" + p.name,
                                      "sha256": audit.sha(p.read_bytes())}])
        cases.append((label, c, expected))
    dump(out / "CASE_PLAN.json", {"cases": cases, "synthetic": True,
         "fixtures": [{"path": p.name, "sha256": audit.sha(p.read_bytes())} for p in sorted(root.iterdir())]})
    results = []
    for label, c, expected in cases:
        result, _ = audit.audit(c, root)
        probe = next(m for m in result["modules"] if m["name"] == "probe")
        if expected == "ports":
            ok = {p["name"] for p in probe["ports"]} == {"bend", "fcw"} and not result["errors"]
        elif expected == "macro":
            ok = not probe["port_inventory_complete"] and result["status"] == "PENDING_STATIC_ELABORATION"
        elif expected == "function":
            ok = not result["errors"] and not any(i["type"] == "performance_event_t" for i in result["instances"])
        elif expected == "parameter":
            ok = not result["errors"] and any(p.startswith("ROM_PARAMETER_DEFAULT_NEEDS_BINDING") for p in result["pending"])
        else:
            prefix = {"literal": "MISSING_ROM_REFERENCE", "missing": "MISSING_MODULE:missing_leaf",
                      "port_error": "UNKNOWN_NAMED_PORT:leaf.BAD"}[expected]
            ok = any(e.startswith(prefix) for e in result["errors"])
        dump(out / (label + ".json"), result)
        results.append({"case": label, "passed": ok, "status": result["status"]})
        print(json.dumps(results[-1]), flush=True)
    real = audit.load(config_path.read_bytes())
    result, payload = audit.audit(real, repo)
    audit.write_result(result, payload, out / "real_incremental")
    ok = all(r["passed"] for r in results)
    # Only affected parser diagnostics; unresolved legacy dds stays unaltered.
    ok &= not any(e.startswith("UNKNOWN_NAMED_PORT") or e == "MISSING_MODULE:performance_event_t"
                  or e.startswith("MISSING_ROM_REFERENCE") for e in result["errors"])
    dump(out / "SUMMARY.json", {"targeted_repair_passed": ok, "cases": results,
         "real_status": result["status"], "real_errors": result["errors"],
         "original_fifteen_not_rerun": True, "board_release_allowed": False})
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(run(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])))
