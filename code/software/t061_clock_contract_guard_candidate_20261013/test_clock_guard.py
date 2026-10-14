"""Pure-software contract mutations; no synthetic fixture is RTL evidence."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import clock_guard as guard


class ContractTests(unittest.TestCase):
    """Fake project/tool bytes exercise semantics, never EDA execution."""

    def setUp(self):
        output_root = Path(__file__).resolve().parents[2] / "output"
        output_root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="n32d_software_only_",
                                               dir=output_root)
        self.base = Path(self.temp.name)
        self.root = self.base / "project"
        self.root.mkdir()
        self.files = []

        def put(name, data, role, origin=None):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data, encoding="utf-8", newline="\n")
            row = {"path": name, "bytes": path.stat().st_size,
                   "sha256": guard.sha256(path), "role": role}
            if origin:
                row["origin_snapshot"] = origin
            self.files.append(row)
            return row

        inputs = []
        sources = []
        for i in range(18):
            source = put(f"sources/s{i}.sv", f"module s{i}; endmodule\n",
                         "source", f"fixture/s{i}.sv")
            inputs.append({"role": "HDL", "snapshot": source["origin_snapshot"],
                           "sha256": source["sha256"], "bytes": source["bytes"]})
            sources.append(source["path"])
        for i, suffix in enumerate([".svh", ".svh"] + [".mem"] * 5):
            role = "include" if suffix == ".svh" else "rom"
            folder = "include" if role == "include" else "rom"
            row = put(f"{folder}/p{i}{suffix}", f"{i:04x}\n", role,
                      f"fixture/p{i}{suffix}")
            inputs.append({"role": "SUPPORT", "snapshot": row["origin_snapshot"],
                           "sha256": row["sha256"], "bytes": row["bytes"]})
        top = (
            "module m3_n32_resource;\n"
            "b_n32_event_audio_prom #(.N(32), .RESPONSE(1)) candidate (\n"
            ".inject_valid(1'b0), .inject_tag(77'd0), .inject_context(74'd0));\n"
            "endmodule\n"
        )
        top_row = put("sources/m3_n32_resource.sv", top, "top")
        self.patch_top = patch.object(guard, "TRUSTED_TOP_SHA", top_row["sha256"])
        self.patch_top.start()
        self.addCleanup(self.patch_top.stop)
        sources.append(top_row["path"])
        self.evidence = {}
        pins = {}
        for key in ("A", "B", "C", "B_plan", "A_result"):
            data = {"fixture": "SOFTWARE_ONLY", "key": key}
            if key == "B_plan":
                data["inputs"] = inputs
            if key == "A_result":
                data["status"] = "ALLOCATOR_COMPARISON_AND_MUTATIONS_PASS"
            row = put(f"evidence/{key}.json", json.dumps(data), "evidence")
            self.evidence[key] = {"path": row["path"], "sha256": row["sha256"]}
            pins[key] = row["sha256"]
        # Fixture-specific trust anchors are intentionally patched locally;
        # real integration uses the immutable production A/B/C/B-plan anchors.
        self.patch_pins = patch.dict(guard.TRUSTED_EVIDENCE, pins, clear=True)
        self.patch_pins.start()
        self.addCleanup(self.patch_pins.stop)
        self.project = {
            "gprj": "n32_resource.gprj", "tcl": "run_synthesis_only.tcl",
            "sdc": "clock.sdc", "top_source": "sources/m3_n32_resource.sv",
            "include_dirs": ["include"], "source_order": sources,
        }
        put("clock.sdc", guard.SDC, "sdc")
        xml = ET.Element("Project")
        ET.SubElement(xml, "Template").text = "FPGA"
        ET.SubElement(xml, "Version").text = "5"
        ET.SubElement(xml, "Device", name=guard.DEVICE["name"],
                      pn=guard.DEVICE["pn"]).text = guard.DEVICE["index"]
        listing = ET.SubElement(xml, "FileList")
        for name in sources + ["clock.sdc"]:
            ET.SubElement(listing, "File", path=(self.root / name).as_posix(),
                          type="file.sdc" if name.endswith(".sdc") else
                          "file.verilog", enable="1")
        put("n32_resource.gprj", ET.tostring(xml, encoding="unicode"), "gprj")
        put("run_synthesis_only.tcl",
            guard.tcl_text(self.root, self.project, "m3_n32_resource"), "tcl")
        tools = {}
        home = self.base / "fake_tool_bytes"
        for name, relative in guard.TOOL_PATHS.items():
            path = home / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("SOFTWARE_ONLY_NOT_EXECUTABLE " + name,
                            encoding="utf-8")
            tools[name] = {"path": str(path), "bytes": path.stat().st_size,
                           "sha256": guard.sha256(path), "availability": "AVAILABLE"}
        extra = home / "IDE/bin/extra.dll"
        extra.write_bytes(b"SOFTWARE_ONLY_FAKE_DLL_NOT_EXECUTABLE")
        inventory = {p.relative_to(home).as_posix():
                     {"bytes": p.stat().st_size, "sha256": guard.sha256(p)}
                     for folder in (home / "IDE/bin", home / "IDE/data/device/GW5AST-138C")
                     for p in folder.rglob("*") if p.is_file()}
        self.patch_inventory = patch.object(guard, "TRUSTED_TOOL_INVENTORY_SHA",
            hashlib.sha256(guard.canonical(inventory).encode("utf-8")).hexdigest())
        self.patch_inventory.start()
        self.addCleanup(self.patch_inventory.stop)
        row = put("evidence/prior_tool_reference.json", json.dumps(
            {"fixture": "SOFTWARE_ONLY", "tool": {"identities": tools}}), "evidence")
        self.evidence["prior_tool_reference"] = {"path": row["path"], "sha256": row["sha256"]}
        guard.TRUSTED_EVIDENCE["prior_tool_reference"] = row["sha256"]
        self.manifest = {
            "schema": "N32_D_PREPARE_V1", "status": "PREPARED_NOT_EXECUTED",
            "top": "m3_n32_resource", "configuration": copy.deepcopy(guard.CONFIGURATION),
            "device": copy.deepcopy(guard.DEVICE), "clock": copy.deepcopy(guard.CLOCK),
            "execution": copy.deepcopy(guard.EXECUTION), "T061_complete": False,
            "macros": [],
            "synthesis_default_frequency_mhz": 100,
            "synthesis_frequency_is_physical_sta": False,
            "project": self.project, "files": self.files,
            "evidence": self.evidence,
            "tool": {"machine": socket.gethostname(), "home": str(home),
                     "identities": tools, "static_inventory": inventory,
                     "inventory_scope": list(guard.INVENTORY_SCOPE),
                     "execution_ready": True, "missing_required": []},
        }
        self.write_manifest()

    def tearDown(self):
        self.temp.cleanup()

    def write_manifest(self):
        (self.root / "manifest.json").write_text(
            json.dumps(self.manifest, indent=2), encoding="utf-8")

    def resign(self, name):
        row = next(x for x in self.files if x["path"] == name)
        path = self.root / name
        row["bytes"], row["sha256"] = path.stat().st_size, guard.sha256(path)
        self.write_manifest()

    def change(self, name, old, new):
        path = self.root / name
        path.write_text(path.read_text(encoding="utf-8").replace(old, new),
                        encoding="utf-8")
        self.resign(name)

    def reject(self, diagnostic):
        self.write_manifest()
        with self.assertRaisesRegex(guard.ContractError, diagnostic):
            guard.validate(self.root)

    def test_software_fixture_positive(self):
        result = guard.validate(self.root)
        self.assertEqual(result["actual_tool_calls"], 0)
        self.assertEqual(result["STA"], "NOT_RUN")

    def test_missing_shell_is_preparation_not_execution(self):
        row = self.manifest["tool"]["identities"]["shell"]
        Path(row["path"]).unlink()
        row.update(bytes=None, sha256=None, availability="MISSING")
        self.manifest["tool"].update(execution_ready=False, missing_required=["shell"])
        del self.manifest["tool"]["static_inventory"][guard.TOOL_PATHS["shell"]]
        guard.TRUSTED_TOOL_INVENTORY_SHA = hashlib.sha256(guard.canonical(
            self.manifest["tool"]["static_inventory"]).encode("utf-8")).hexdigest()
        self.write_manifest()
        self.assertFalse(guard.validate(self.root)["tool_ready"])

    def test_missing_shell_ready_claim_rejected(self):
        row = self.manifest["tool"]["identities"]["shell"]
        Path(row["path"]).unlink()
        row.update(bytes=None, sha256=None, availability="MISSING")
        self.reject("D_TOOL_READINESS")

    def test_missing_shell_fake_null_rejected(self):
        self.manifest["tool"]["identities"]["shell"].update(
            bytes=None, sha256=None, availability="MISSING")
        self.reject("D_FAKE_MISSING_TOOL")

    def test_wrong_period_resigned(self):
        self.change("clock.sdc", "25.000", "10.000")
        self.reject("D_40MHZ_SDC_CONTRACT")

    def test_missing_setup_resigned(self):
        self.change("clock.sdc", "set_clock_uncertainty -setup 1.000 [get_clocks {sys_clk}]", "")
        self.reject("D_40MHZ_SDC_CONTRACT")

    def test_weakened_hold_resigned(self):
        self.change("clock.sdc", "0.650", "0.000")
        self.reject("D_40MHZ_SDC_CONTRACT")

    def test_extra_false_path_resigned(self):
        self.change("clock.sdc", guard.SDC, guard.SDC + "set_false_path -from [all_registers]\n")
        self.reject("D_40MHZ_SDC_CONTRACT")

    def test_commented_clock_resigned(self):
        self.change("clock.sdc", "create_clock", "# create_clock")
        self.reject("D_40MHZ_SDC_CONTRACT")

    def test_missing_sdc_in_gprj_resigned(self):
        path = self.root / "n32_resource.gprj"
        tree = ET.fromstring(path.read_text(encoding="utf-8"))
        tree.find("FileList").remove(list(tree.find("FileList"))[-1])
        path.write_text(ET.tostring(tree, encoding="unicode"), encoding="utf-8")
        self.resign("n32_resource.gprj")
        self.reject("D_GPRJ_SDC_SOURCE_TRANSMISSION")

    def test_disabled_sdc_resigned(self):
        self.change("n32_resource.gprj", 'type="file.sdc" enable="1"', 'type="file.sdc" enable="0"')
        self.reject("D_GPRJ_FILE_FIELDS")

    def test_wrong_tcl_top_resigned(self):
        self.change("run_synthesis_only.tcl", "-top_module m3_n32_resource", "-top_module old_top")
        self.reject("D_TCL_TOP_SDC_TRANSMISSION")

    def test_tcl_extra_execution_resigned(self):
        self.change("run_synthesis_only.tcl", "run syn", "run syn\nrun pnr")
        self.reject("D_TCL_TOP_SDC_TRANSMISSION")

    def test_wrong_top_source_resigned(self):
        self.change("sources/m3_n32_resource.sv", "module m3_n32_resource", "module wrong_top")
        self.reject("D_TOP_MODULE")

    def test_wrong_n_resigned(self):
        self.change("sources/m3_n32_resource.sv", ".N(32)", ".N(16)")
        self.reject("D_TOP_N32_R1")

    def test_top_hidden_change_resigned(self):
        self.change("sources/m3_n32_resource.sv", "endmodule",
                    "assign hidden = 1'b1;\nendmodule")
        self.reject("D_TOP_BYTE_CONTRACT")

    def test_injection_enabled_resigned(self):
        self.change("sources/m3_n32_resource.sv", ".inject_valid(1'b0)", ".inject_valid(1'b1)")
        self.reject("D_TOP_INJECTION_ENABLED")

    def test_changed_old_source_resigned(self):
        self.change("sources/s5.sv", "module s5", "module old_allocator")
        self.reject("D_OLD_OR_CHANGED_SOURCE")

    def test_rom_replaced_resigned(self):
        self.change("rom/p2.mem", "0002", "ffff")
        self.reject("D_OLD_OR_CHANGED_SOURCE")

    def test_misplaced_include_resigned(self):
        row = next(x for x in self.files if x["role"] == "include")
        old = self.root / row["path"]
        row["path"] = "rom/" + old.name
        old.rename(self.root / row["path"])
        self.reject("D_DEPENDENCY_LOCATION")

    def test_path_escape_resigned(self):
        self.files[0]["path"] = "../outside.sv"
        self.reject("D_PATH_ESCAPE")

    def test_duplicate_file(self):
        self.files.append(copy.deepcopy(self.files[0]))
        self.reject("D_DUPLICATE_FILE")

    def test_extra_old_report(self):
        (self.root / "old_timing.rpt").write_text("PASS 40MHz", encoding="utf-8")
        self.reject("D_UNMANIFESTED_OR_OLD_REPORT")

    def test_old_report_manifested(self):
        self.files.append({"path": "old_report", "role": "report"})
        self.reject("D_FILE_ROLE")

    def test_trusted_evidence_replaced_and_resigned(self):
        self.change("evidence/B.json", "SOFTWARE_ONLY", "FAKE_PASS")
        self.evidence["B"]["sha256"] = guard.sha256(self.root / "evidence/B.json")
        self.reject("D_TRUSTED_EVIDENCE_B")

    def test_boolean_tool_calls_not_zero(self):
        self.manifest["execution"]["tool_calls"] = False
        self.reject("D_EXECUTION_CONTRACT")

    def test_fake_resource_pass(self):
        self.manifest["execution"]["resources"] = "PASS"
        self.reject("D_EXECUTION_CONTRACT")

    def test_default100_not_sta40(self):
        self.manifest["synthesis_frequency_is_physical_sta"] = True
        self.reject("D_DEFAULT100_IS_NOT_STA40")

    def test_false_full_completion(self):
        self.manifest["T061_complete"] = True
        self.reject("D_COMPLETE_CLAIM")

    def test_mutant_macro_rejected(self):
        self.manifest["macros"] = ["B_N32_MUTANT_PCM"]
        self.reject("D_MACROS_FORBIDDEN")

    def test_machine_mismatch(self):
        self.manifest["tool"]["machine"] = "NOT_THIS_MACHINE"
        self.reject("D_MACHINE_BINDING")

    def test_inventory_removed_resigned(self):
        del self.manifest["tool"]["static_inventory"]
        self.reject("D_TOOL_INVENTORY_REQUIRED")

    def test_inventory_empty_resigned(self):
        self.manifest["tool"]["static_inventory"] = {}
        self.reject("D_TOOL_INVENTORY_REQUIRED")

    def test_inventory_scope_reduced_resigned(self):
        self.manifest["tool"]["inventory_scope"] = ["IDE/bin/**"]
        self.reject("D_TOOL_INVENTORY_SCOPE")

    def test_inventory_member_omitted_resigned(self):
        del self.manifest["tool"]["static_inventory"]["IDE/bin/extra.dll"]
        self.reject("D_TOOL_INVENTORY_MEMBER_SET")

    def test_inventory_actual_file_deleted(self):
        (Path(self.manifest["tool"]["home"]) / "IDE/bin/extra.dll").unlink()
        self.reject("D_TOOL_INVENTORY_MEMBER_SET")

    def test_inventory_extra_actual_file(self):
        (Path(self.manifest["tool"]["home"]) / "IDE/bin/surprise.dll").write_bytes(b"NEW")
        self.reject("D_TOOL_INVENTORY_MEMBER_SET")

    def test_inventory_file_tampered(self):
        (Path(self.manifest["tool"]["home"]) / "IDE/bin/extra.dll").write_bytes(b"CHANGED")
        self.reject("D_IDENTITY_TOOL_INVENTORY")

    def test_major_tool_replaced_and_resigned(self):
        row = self.manifest["tool"]["identities"]["engine"]
        path = Path(row["path"])
        path.write_bytes(b"REPLACED_TOOL_SOFTWARE_ONLY")
        row.update(bytes=path.stat().st_size, sha256=guard.sha256(path))
        self.manifest["tool"]["static_inventory"][guard.TOOL_PATHS["engine"]] = {
            "bytes": row["bytes"], "sha256": row["sha256"]}
        self.reject("D_TRUSTED_INSTALLED_TOOL_engine")

    def test_major_tool_moved_outside_home(self):
        self.manifest["tool"]["identities"]["engine"]["path"] = str(self.base / "other.exe")
        self.reject("D_TOOL_PATH_engine")

    def test_dll_inventory_and_manifest_all_resigned(self):
        path = Path(self.manifest["tool"]["home"]) / "IDE/bin/extra.dll"
        path.write_bytes(b"MALICIOUS_REPLACEMENT_SOFTWARE_FIXTURE")
        self.manifest["tool"]["static_inventory"]["IDE/bin/extra.dll"] = {
            "bytes": path.stat().st_size, "sha256": guard.sha256(path)}
        self.reject("D_TRUSTED_TOOL_INVENTORY")

    def test_deleted_dll_inventory_and_manifest_all_resigned(self):
        (Path(self.manifest["tool"]["home"]) / "IDE/bin/extra.dll").unlink()
        del self.manifest["tool"]["static_inventory"]["IDE/bin/extra.dll"]
        self.reject("D_TRUSTED_TOOL_INVENTORY")

    def test_anchor_rejects_resigned_manifest(self):
        original = guard.sha256(self.root / "manifest.json")
        self.manifest["new_claim"] = "irrelevant"
        self.write_manifest()
        with self.assertRaisesRegex(guard.ContractError, "D_MANIFEST_ANCHOR"):
            guard.validate(self.root, trusted_manifest_sha=original)

    def test_duplicate_json_key(self):
        path = self.root / "manifest.json"
        text = path.read_text(encoding="utf-8")
        path.write_text('{"schema":"fake",' + text[1:], encoding="utf-8")
        with self.assertRaisesRegex(guard.ContractError, "D_DUPLICATE_JSON_KEY"):
            guard.validate(self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
