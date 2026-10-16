"""Bind sole monitor repair; retain all already signed normal and bad cases."""
import json
from e4_common import ROOT,DOC,SOFT,identity,write_new

prior=DOC/"ROUND_04/RUN_RECEIPT.json"
assert identity(prior)["sha256"]=="e4ae54cfcfa3fe3a3f085970a7085167b400029099bc924664968bc06915df02"
plan=json.loads((DOC/"CASE_PLAN.json").read_text(encoding="utf-8"))
plan["cases"]=plan["cases"][11:]
plan["reuse_signed_normal_sources"]="All four normal frozen-piano source/ROM/transport bytes unchanged; only TB immediate result-ID monitor added. Original normal captures/checks are retained, not rerun or relabeled as new TB executions."
plan["previous_normal_check_receipts"]=[identity(DOC/"ROUND_03/RUN_RECEIPT.json"),identity(prior)]
old=json.loads(prior.read_text(encoding="utf-8"))
plan["previous_actual_bad_cases"]=[x for x in old["cases"] if x["status"]=="ACTUAL_RTL_TARGET_REJECTED"]
assert len(plan["previous_actual_bad_cases"])==7 and len(plan["cases"])==4
write_new(DOC/"CASE_PLAN_R05.json",plan)
write_new(DOC/"REPAIR_05.json",{"prior_round":4,"receipt":identity(prior),"failure":"bad_result_id actual RTL rejects at E4_DEADLINE_OPEN rather than predeclared E4_ID because wrong ID permanently prevents downstream ready","diagnostic_not_accepted_as_pass":True,"change":"Only new TB immediately checks public result_id against independently saved accepted sample_id whenever valid and no cancel/abort, before F/K; no waiting for result_ready","fixed_tb":identity(ROOT/"code/tb/audio/m3_n32_pro_candidate_20261017/tb_e4_n32.sv"),"unchanged_business_RTL":True,"normal_four_scales_and_previous_seven_negatives_rerun":False,"actual_RTL_bad_id_retest":True,"additional_unrun_bad_cases":["bad_transport_left","bad_clipped_metadata","bad_retirement"],"original_failed_evidence_unchanged":True,"groups_consumed_before":4,"new_group":5})
print("R05_ONLY_ONE_REPAIRED_AND_THREE_UNRUN_BAD_CASES_PREPARED")
