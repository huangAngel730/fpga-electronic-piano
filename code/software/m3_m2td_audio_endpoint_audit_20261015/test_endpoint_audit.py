"""Software-only tests; no RTL, ModelSim, Gowin or device commands."""

from copy import deepcopy
import json
import unittest

import endpoint_audit as audit
import fixtures


class EndpointTests(unittest.TestCase):
    def expect(self, code, data, plan, **kwargs):
        with self.assertRaises(audit.AuditError) as caught:
            audit.check_report(data, plan, **kwargs)
        self.assertEqual(code, caught.exception.code)

    def test_complete_synthetic_matrix(self):
        for name, data, plan, expected in fixtures.matrix():
            with self.subTest(name=name):
                if expected == "SPECIFIED_REPORT_ENDPOINTS_SHOWN":
                    result = audit.check_report(data, plan)
                    self.assertEqual(result["status"], expected)
                    self.assertEqual(len(result["observations"]), 2)
                    self.assertFalse(result["board_release_allowed"])
                    self.assertFalse(result["new_sta_executed"])
                else:
                    self.expect(expected, data, plan)

    def test_directed_positive(self):
        data, plan = fixtures.synthetic(directed=True)
        plan["targets"][0]["require_directed"] = True
        result = audit.check_report(data, plan)
        self.assertEqual(len(result["observations"]), 2)

    def test_summary_not_directed(self):
        data, plan = fixtures.synthetic()
        plan["targets"][0]["require_directed"] = True
        self.expect("DIRECTED_COMMAND_ABSENT", data, plan)

    def test_conflicting_directed_selector(self):
        data, plan = fixtures.synthetic(directed=True)
        data = data.replace(b" -max_paths", b" -from [get_regs {wrong}] -max_paths")
        plan["source"]["report_sha256"] = audit.sha256(data)
        plan["targets"][0]["require_directed"] = True
        self.expect("DIRECTED_COMMAND_ABSENT", data, plan)

    def test_ram_pin_is_not_get_regs(self):
        data, plan = fixtures.synthetic(directed=True)
        data = data.replace(b"-to [get_pins", b"-to [get_regs")
        plan["source"]["report_sha256"] = audit.sha256(data)
        plan["targets"][0]["require_directed"] = True
        self.expect("DIRECTED_COMMAND_ABSENT", data, plan)

    def test_unescaped_index_query_rejected(self):
        data, plan = fixtures.synthetic(directed=True)
        data = data.replace(b"\\[", b"[").replace(b"\\]", b"]")
        plan["source"]["report_sha256"] = audit.sha256(data)
        plan["targets"][0]["require_directed"] = True
        self.expect("DIRECTED_COMMAND_ABSENT", data, plan)

    def test_wrong_index_query_rejected(self):
        data, plan = fixtures.synthetic(directed=True)
        data = data.replace(b"AD\\[7\\]", b"AD\\[6\\]")
        plan["source"]["report_sha256"] = audit.sha256(data)
        plan["targets"][0]["require_directed"] = True
        self.expect("DIRECTED_COMMAND_ABSENT", data, plan)

    def test_literal_index_selector_generation(self):
        _, plan = fixtures.synthetic()
        target = plan["targets"][0]
        command = audit.directed_prefixes("setup", target)[0]
        self.assertIn("g_lane\\[3\\]", command)
        self.assertIn("-to [get_pins", command)
        self.assertIn("/AD\\[7\\]}", command)
        self.assertNotIn("-to [get_regs", command)

    def test_ff_d_pin_collection_forms(self):
        _, plan = fixtures.synthetic()
        target = plan["targets"][0]
        target["to_node"] = "audio/capture_s0/D"
        commands = audit.directed_prefixes("hold", target)
        self.assertEqual(len(commands), 2)
        self.assertIn("-to [get_pins {audio/capture_s0/D}]", commands[0])
        self.assertIn("-to [get_regs {audio/capture_s0}]", commands[1])

    def test_register_enable_uses_full_pin(self):
        _, plan = fixtures.synthetic()
        target = plan["targets"][0]
        target["to_node"] = "audio/capture_s0/CE"
        commands = audit.directed_prefixes("setup", target)
        self.assertEqual(len(commands), 1)
        self.assertIn("-to [get_pins {audio/capture_s0/CE}]", commands[0])

    def test_report_tamper_without_resign(self):
        data, plan = fixtures.synthetic()
        self.expect("REPORT_SHA", data + b"\n", plan)

    def test_wrong_metadata_even_with_resigned_report(self):
        data, plan = fixtures.synthetic()
        data = data.replace(b"design.vg", b"other.vg")
        plan["source"]["report_sha256"] = audit.sha256(data)
        self.expect("REPORT_IDENTITY", data, plan)

    def test_raw_bytes_bound_spans(self):
        data, plan = fixtures.synthetic()
        result = audit.check_report(data, plan)
        for observation in result["observations"]:
            for name in ("row_span", "table_span"):
                source = observation[name]
                raw = data[source["byte_start"]:source["byte_end_exclusive"]]
                self.assertEqual(audit.sha256(raw), source["fragment_sha256"])
                self.assertIn(fixtures.FROM.encode("utf-8"), raw)
        self.assertIn(b"\r\r\n", data)

    def test_unicode_bound_spans(self):
        data, plan = fixtures.synthetic()
        data = data.replace(b"<body>", "<body><!-- 中文 -->".encode("utf-8"))
        plan["source"]["report_sha256"] = audit.sha256(data)
        for item in audit.check_report(data, plan)["observations"]:
            source = item["row_span"]
            raw = data[source["byte_start"]:source["byte_end_exclusive"]]
            self.assertEqual(audit.sha256(raw), source["fragment_sha256"])

    def test_strict_boolean(self):
        data, plan = fixtures.synthetic()
        for value in (0, 1, "false", None):
            altered = deepcopy(plan)
            altered["targets"][0]["require_directed"] = value
            self.expect("TARGET_SCHEMA", data, altered)

    def test_duplicate_targets(self):
        data, plan = fixtures.synthetic()
        plan["targets"].append(deepcopy(plan["targets"][0]))
        self.expect("TARGET_SCHEMA", data, plan)

    def test_endpoint_wildcard_forbidden(self):
        data, plan = fixtures.synthetic()
        for wildcard in ("*", "?"):
            changed = deepcopy(plan)
            changed["targets"][0]["from_node"] += wildcard
            self.expect("TARGET_SCHEMA", data, changed)

    def test_one_target_cannot_substitute_for_another(self):
        data, plan = fixtures.synthetic()
        other = deepcopy(plan["targets"][0])
        other.update({"id": "second", "to_node": "nonexistent/D"})
        plan["targets"].append(other)
        self.expect("ENDPOINT_ABSENT", data, plan)

    def test_nonfinite_slack(self):
        data, plan = fixtures.synthetic()
        for value in (b"NaN", b"Infinity", b"-Infinity", b"unknown", b"PASS"):
            changed = data.replace(b"0.125", value)
            modified = deepcopy(plan)
            modified["source"]["report_sha256"] = audit.sha256(changed)
            self.expect("INVALID_NUMBER", changed, modified)

    def test_wrong_period_frequency_relation(self):
        data, plan = fixtures.synthetic()
        for old, new, code in (
            (b"<td>25.000</td>", b"<td>20.000</td>", "CLOCK_PERIOD"),
            (b"<td>40.000</td>", b"<td>50.000</td>", "CLOCK_FREQUENCY"),
        ):
            changed = data.replace(old, new, 1)
            modified = deepcopy(plan)
            modified["source"]["report_sha256"] = audit.sha256(changed)
            self.expect(code, changed, modified)

    def test_wrong_relation(self):
        data, plan = fixtures.synthetic()
        changed = data.replace(b"<td>25.000</td>", b"<td>20.000</td>")
        # Restore clock period only: the setup row remains invalid.
        changed = changed.replace(b"<td>20.000</td>", b"<td>25.000</td>", 1)
        plan["source"]["report_sha256"] = audit.sha256(changed)
        self.expect("PATH_RELATION", changed, plan)

    def test_incomplete_html(self):
        data, plan = fixtures.synthetic()
        data = data.replace(b"</table>", b"", 1)
        plan["source"]["report_sha256"] = audit.sha256(data)
        self.expect("HTML_STRUCTURE", data, plan)

    def test_synthetic_cannot_be_relabeled_real(self):
        data, plan = fixtures.synthetic()
        plan["source"]["kind"] = "M2_NEW_REPORT"
        self.expect("SYNTHETIC_SOURCE", data, plan)

    def test_duplicate_json_key(self):
        with self.assertRaises(audit.AuditError) as caught:
            audit.strict_json(b'{"schema":1,"schema":2}')
        self.assertEqual(caught.exception.code, "DUPLICATE_JSON_KEY")

    def test_only_structured_json_is_not_a_report(self):
        data = json.dumps({"active": True, "setup": 1, "hold": 1}).encode()
        _, plan = fixtures.synthetic()
        plan["source"]["report_sha256"] = audit.sha256(data)
        self.expect("REPORT_FORMAT", data, plan)

    def test_error_before_and_after_path_tables(self):
        for marker in (b"Error: fixture", b"FATAL: fixture", b"Failure: fixture", b"Errors: 1"):
            for before in (True, False):
                with self.subTest(marker=marker, before=before):
                    data, plan = fixtures.synthetic()
                    if before:
                        data = data.replace(b"<body>", b"<body><p>" + marker + b"</p>")
                    else:
                        data = data.replace(b"</body>", b"<p>" + marker + b"</p></body>")
                    plan["source"]["report_sha256"] = audit.sha256(data)
                    self.expect("REPORT_DIAGNOSTIC", data, plan)

    def test_empty_clock_object(self):
        data, plan = fixtures.synthetic()
        data = data.replace(b"SYNTHETIC/PLL/CLKOUT2", b"")
        plan["source"]["report_sha256"] = audit.sha256(data)
        self.expect("CLOCK_INACTIVE", data, plan)

    def test_zero_error_summary_not_failure(self):
        data, plan = fixtures.synthetic()
        data = data.replace(b"</body>", b"<p>Errors: 0</p></body>")
        plan["source"]["report_sha256"] = audit.sha256(data)
        self.assertEqual(
            audit.check_report(data, plan)["status"], "SPECIFIED_REPORT_ENDPOINTS_SHOWN",
        )


class OriginalReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.parsed = fixtures.original()

    def test_original_report_is_not_synthetic(self):
        self.assertEqual(audit.sha256(self.data), audit.FROZEN_REPORT_SHA)
        self.assertEqual(len(self.data), 2715163)
        self.assertEqual(self.parsed["metadata"]["Tool Version"], "V1.9.11.03 Education")
        self.assertEqual(self.parsed["clocks"]["sys_clk"]["period_ns"], "25.000")
        self.assertEqual(len(self.parsed["paths"]), 269)

    def test_actual_pitch_hold_is_not_setup_plus_hold(self):
        plan = fixtures.target_plan(self.data, self.parsed["metadata"], frozen=True)
        with self.assertRaises(audit.AuditError) as caught:
            audit.check_report(
                self.data, plan, archive_sha=audit.FROZEN_ZIP_SHA,
                member="pnr/timing.html",
            )
        self.assertEqual(caught.exception.code, "MISSING_SETUP")

    def test_missing_old_pitch_name_rejected(self):
        plan = fixtures.target_plan(self.data, self.parsed["metadata"], frozen=True)
        plan["targets"][0]["from_node"] = "base_s1_18_s0/Q"
        plan["targets"][0]["to_node"] = "base_s2_18_s0/D"
        with self.assertRaises(audit.AuditError) as caught:
            audit.check_report(
                self.data, plan, archive_sha=audit.FROZEN_ZIP_SHA,
                member="pnr/timing.html",
            )
        self.assertEqual(caught.exception.code, "ENDPOINT_ABSENT")

    def test_frozen_source_requires_archive_identity(self):
        plan = fixtures.target_plan(self.data, self.parsed["metadata"], frozen=True)
        with self.assertRaises(audit.AuditError) as caught:
            audit.check_report(self.data, plan)
        self.assertEqual(caught.exception.code, "ARCHIVE_SHA")


if __name__ == "__main__":
    unittest.main(verbosity=2)
