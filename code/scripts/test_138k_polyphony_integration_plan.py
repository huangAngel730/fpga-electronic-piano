"""New static budget/identity fault checks, no RTL or EDA."""
import argparse
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import audit_138k_polyphony_integration_plan as plan


class Tests(unittest.TestCase):
    def test_known_source_calendar(self):
        for n,r,first in ((4,1,68),(8,1,108),(16,1,188),(32,1,348),(32,8,572),(32,16,828)):
            self.assertEqual(plan.budget(n,r)["first_valid_after_sample_accept"],first)

    def test_unknown_is_not_admitted(self):
        r=plan.budget(32,1)
        self.assertIsNone(r["conditioned_before_next_frame"])
        self.assertEqual(r["general_service_deadline"],"UNKNOWN")
        self.assertFalse(r["physical_STA_passed"])

    def test_strict_next_frame_boundary(self):
        self.assertTrue(plan.budget(32,1,event_wait=481)["conditioned_before_next_frame"])
        self.assertFalse(plan.budget(32,1,event_wait=482)["conditioned_before_next_frame"])

    def test_bad_parameters(self):
        for n,r in ((True,1),(32,True),(0,1),(32,0),(32,65)):
            with self.assertRaises(ValueError): plan.budget(n,r)
        with self.assertRaises(ValueError): plan.budget(32,1,frame_to_admission=0)
        with self.assertRaises(ValueError): plan.budget(32,1,event_wait=True)

    def test_five_blockers_preserved(self):
        self.assertEqual(len(self.report["required_changes"]),5)
        self.assertFalse(self.report["integration_RTL_written"])
        self.assertFalse(self.report["board_release_allowed"])

    def test_rom_path_differences_and_old_constraints_not_reused(self):
        self.assertEqual(set(self.report["proven_only_ROM_path_literal_differences"]),
                         {"sources/adsr_piano_envelope.sv","sources/pitch_mod_fcw_pipeline.sv"})
        self.assertFalse(self.report["old_audio_constraints_reusable_without_new_endpoint_mapping"])
        self.assertGreaterEqual(len(self.report["old_audio_hierarchy_constraints"]),6)

    def test_changed_frozen_receipt(self):
        old=Path.read_bytes
        target=(self.resource/"frozen_receipt.json").resolve()
        def changed(p):
            return old(p)+b" " if p.resolve()==target else old(p)
        with patch.object(Path,"read_bytes",changed),self.assertRaisesRegex(ValueError,"EXACT_RESOURCE_FROZEN"):
            plan.audit(self.resource,self.baseline)

    def test_changed_baseline(self):
        old=Path.read_bytes
        target=(self.baseline/"inputs/sources/midi_event_parser.sv").resolve()
        def changed(p):
            return old(p)+b"//changed" if p.resolve()==target else old(p)
        with patch.object(Path,"read_bytes",changed),self.assertRaisesRegex(ValueError,"BASELINE_SOURCE_DRIFT"):
            plan.audit(self.resource,self.baseline)

    def test_calendar_drift(self):
        old=plan.backend_calendar
        def changed(*a):
            c=old(*a)
            return type(c)(c.advance,c.lanes,c.backend_first+1)
        with patch.object(plan,"backend_calendar",changed),self.assertRaisesRegex(ValueError,"CALENDAR_FORMULA_MISMATCH"):
            plan.budget(32,1)


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--resource-project",type=Path,required=True)
    cli.add_argument("--baseline-project",type=Path,required=True)
    cli.add_argument("--output",type=Path,required=True)
    a=cli.parse_args()
    root=(plan.ROOT/"code/output").resolve()
    out=a.output.resolve()
    if out==root or not out.is_relative_to(root) or out.exists(): raise ValueError("OUTPUT_SCOPE_OR_EXISTS")
    Tests.resource=a.resource_project.resolve()
    Tests.baseline=a.baseline_project.resolve()
    Tests.report=plan.audit(Tests.resource,Tests.baseline)
    out.mkdir(parents=True,exist_ok=False)
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    result=dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),exit_code=0 if r.wasSuccessful() else 1,
                kind="Static source/conditional budget only",RTL_runs=0,Gowin_runs=0)
    (out/"receipt.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    return result["exit_code"]


if __name__=="__main__": raise SystemExit(main())
