"""Create R7-A versioned schema and pin existing contracts; no old tests run."""
import hashlib
import json
from pathlib import Path
import shutil

SOFT = Path(__file__).resolve().parent
ROOT = SOFT.parents[4]
REL = "m3_pro_fourvoice_trace_20261016/pro_basis_r07_20261017/public_capture_tb"
DOC = ROOT / "code/docs/test" / REL
TB = ROOT / "code/tb/board" / REL
M2 = ROOT / "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/r06_observer_20261017"


def identity(path):
    p = Path(path).resolve()
    data = p.read_bytes()
    return {"path": str(p), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    ports = json.loads((M2 / "OBSERVER_EXPORTS_R06C3.json").read_text(encoding="utf-8"))["expected_observation_ports"]
    normalized = json.loads((M2 / "NORMALIZED_ROW_SCHEMA.json").read_text(encoding="utf-8"))
    assert len(ports) == 38 and len(normalized["required"]) == 61
    mapping = {}
    for name, info in ports.items():
        target = name.removeprefix("obs_")
        if name == "obs_tx_clip_any":
            target = "tx_clip"
        if target in normalized["required"]:
            mapping[target] = {"port": name, **info}
    physical = {"bclk": "i2s_bclk", "ws": "i2s_lrck", "din": "i2s_din", "pa_en": "pa_en"}
    mapping.update({field: {"port": port, "width": 1, "signed": False} for field, port in physical.items()})
    raw_ports = {**ports, **{p: {"width": 1, "signed": False} for p in (*physical.values(), "uart_tx")}}
    missing = {name: normalized["properties"][name]["description"].split(";")[0]
               for name in normalized["required"] if name not in mapping and name not in ("cycle", "epoch", "finish")}
    save(DOC / "PORT_MAP.json", {"schema": "M3_R7A_PUBLIC_PORT_MAP_V1", "exports": identity(M2 / "OBSERVER_EXPORTS_R06C3.json"),
        "normalized_schema": identity(M2 / "NORMALIZED_ROW_SCHEMA.json"), "raw_ports": raw_ports,
        "normalized_mapping": mapping, "unimplemented": missing,
        "epoch": "Bound after capture from independent asynchronous RESET_EDGES; ambiguous same-time transitions remain null",
        "tx_req_id": "null unless obs_tx_req_id_valid known1; original bits remain in raw file and extensions",
        "pro_dut_pass": False, "board_release_allowed": False})
    extension_names = ("obs_core_clk", "obs_polyphonic_valid", "obs_tx_metadata_valid", "obs_tx_req_id_valid",
                       "obs_tx_clip_mask", "obs_metadata_error", "obs_frame_id_overflow", "uart_tx")
    source = {"type": "object", "additionalProperties": False,
              "required": ["raw_sha256", "reset_edges_sha256", "line", "cycle", "epoch", "time_ps", "sampling_phase"],
              "properties": {"raw_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                  "reset_edges_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                  "line": {"type": "integer", "minimum": 1}, "cycle": {"type": "integer", "minimum": 0},
                  "epoch": {"type": ["integer", "null"], "minimum": 0}, "time_ps": {"type": "integer", "minimum": 0},
                  "sampling_phase": {"const": "POSEDGE_PRE_NBA"}}}
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "M3 R7-A canonical public row V1",
        "type": "object", "additionalProperties": False,
        "required": ["schema", "capture_id", "origin", "source", "fields", "extensions", "missing_reasons", "events"],
        "properties": {"schema": {"const": "M3_R7A_PUBLIC_ROW_V1"}, "capture_id": {"type": "string", "minLength": 1},
            "origin": {"enum": ["SYNTHETIC_SCHEMA_FIXTURE", "HDL_PUBLIC_CAPTURE_UNVERIFIED"]},
            "source": source, "fields": normalized,
            "extensions": {"type": "object", "additionalProperties": False,
                "required": ["schema", *extension_names, "raw_tx_req_id_bits"],
                "properties": {"schema": {"const": "M3_R7A_TX_EXTENSION_V1"},
                    **{name: {"type": ["integer", "string", "null"]} for name in extension_names},
                    "raw_tx_req_id_bits": {"type": "string", "pattern": "^[01xXzZ]{32}$"}}},
            "missing_reasons": {"type": "object", "additionalProperties": {"type": "string", "minLength": 1}},
            "events": {"type": "array", "uniqueItems": True, "items": {"enum": ["FRAME_F", "ACCEPT_A", "RESULT_TRANSFER", "COMMIT", "TX_ADOPT", "FINISH"]}}},
        "x-contract": {"fields": "Exactly unmodified M2 61 keys; source/metadata/extensions never inserted into fields",
            "missing": missing, "FRAME_PLAN_generated": False, "HDL_status": "NOT_RUN",
            "pro_dut_pass": False, "board_release_allowed": False}}
    save(DOC / "CAPTURE_SCHEMA.json", schema)
    references = [M2 / name for name in ("CAPTURE_CONTRACT.json", "NORMALIZED_ROW_SCHEMA.json", "OBSERVER_EXPORTS_R06C3.json", "SOURCE_REPLACEMENTS_R06C3.json")]
    old = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/midi_stimulus"
    references += [old / "RESULT.md", old / "RUN_02/receipt.json"]
    references += [old / "RUN_02/products" / n for n in ("plan.json", "bytes.drv", "reset.drv", "ready.drv")]
    references += [ROOT / "code/tb/board/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/midi_stimulus/midi_public_port_driver.sv"]
    r = ROOT / "code/rtl/board/m2_138k_pro_fourvoice_candidate_20261016/r06_observer_20261017"
    references += [r / n for n in ("m2_138k_pro_fourvoice_observer_top_r06.sv", "m2_fourvoice_timbre_delay_board_top_r06.sv", "m2_fourvoice_timbre_delay_frame_core_r06.sv", "m2_r06_tx_identity_sidecar.sv")]
    references += [ROOT / "code/docs/Pro基础持续推进与M3扩充分工任务单_R07_2026-10-17.md"]
    target = DOC / "INPUT_ORIGINALS"
    target.mkdir(exist_ok=False)
    items = []
    for p in references:
        entry = identity(p)
        dst = target / (entry["sha256"][:16] + "_" + p.name)
        shutil.copyfile(p, dst)
        assert identity(dst)["sha256"] == entry["sha256"]
        items.append({"original": entry, "snapshot": identity(dst)})
    save(DOC / "INPUT_IDENTITIES.json", {"baseline": "4fd3366e42fd2356e56eb96eee70b6771afd4bb1", "files": items,
        "old_R06_tests_reexecuted": 0, "HDL": "NOT_RUN", "board_release_allowed": False})
    print(json.dumps({"schema": identity(DOC / "CAPTURE_SCHEMA.json"), "missing_fields": len(missing)}))


if __name__ == "__main__":
    main()
