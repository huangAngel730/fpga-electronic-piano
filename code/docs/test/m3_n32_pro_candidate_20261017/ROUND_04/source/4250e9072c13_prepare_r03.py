"""Static bounded repair/source plan and Pro build precheck, no tool execution."""
import json
from pathlib import Path
from e4_common import ROOT,DOC,SOFT,identity,write_new
from run_e4 import sources

prior=DOC/"ROUND_02/RUN_RECEIPT.json"
assert identity(prior)["sha256"]=="7d67a0bd3c1430cd9d22214da4bac50adfcde40c36e183ba3a1751fcbd960232"
plan=json.loads((DOC/"CASE_PLAN.json").read_text(encoding="utf-8"))
plan["cases"][0]["reuse_simulation"]={"receipt_relative":"ROUND_02/RUN_RECEIPT.json","receipt_sha256":identity(prior)["sha256"],"simulation_call_index":2,"reason":"N4 HDL already passed; checker-only R-END and independent serial/submit guards repaired"}
write_new(DOC/"CASE_PLAN_R03.json",plan)
write_new(DOC/"REPAIR_03.json",{"prior_round":2,"receipt":identity(prior),"failure":"N4 real simulation PASS, checker RESET_BASE_ROW_CONFLICT at final same-cycle R then END","change":"Allow only ordered terminal R->END with no unclosed work and strict count; bind S play and DIN expectations to independent T commit/buffer ledger, add manual P/K<833 guard; negative policy requires sole first target Fatal and fixed ModelSim exit0","checker":identity(SOFT/"check_e4.py"),"runner":identity(SOFT/"run_e4.py"),"normal_n4_recompiled":False,"normal_n4_resimulated":False,"remaining_unrun_cases":"N8/N16/N32 and behavioral faults","original_failed_evidence_unchanged":True,"groups_already_consumed":2,"new_group":3})
build=ROOT/"code/build/138k_polyphony_resource/m3_n32_pro_candidate_20261017"
build.mkdir(exist_ok=False)
closure={str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p):identity(p) for p in sources()}
write_new(build/"SIMULATION_SOURCE_MANIFEST.json",{"scope":"FOUR_SCALE_ISOLATED_FROZEN_PIANO_COMPOSITION","source_list_order":list(closure),"files":closure,"ROM_policy":"unchanged embedded pROM INIT_RAM and frozen reference ROM numeric words","original_interface":identity(ROOT/"code/rtl/common/m3_n32_allocator_candidate_20261013/B/b_n32_c_interface.json"),"new_candidate_not_formal_top":True})
write_new(build/"PRO_BUILD_PRECHECK.json",{"status":"NOT_RUN_BLOCKED_MISSING_PRO_IDENTITY_AND_COMMERCIAL_LICENSE","physical_rounds_consumed":0,"conditional_limit":2,"round_limit_s":1800,"requested_package":"FPG676","confirmed_full_target_part":None,"commercial_license_verified":False,"M2_new_Pro_source_manifest_received":False,"Pro_ROM_and_IP_manifest_received":False,"candidate_Pro_CST_SDC_received":False,"independent_whole_project_clocks_resets_constraints_complete":False,"simulation_only_clock_hz":40000000,"nominal_sample_rate_hz":48000,"pure_sine_test_mode_and_ROM":"M1_CONFIRMATION_REQUIRED_FROZEN_PIANO_ONLY","formal_admission":False,"new_fs_generated":False,"hardware_downloads":0,"source_manifest":identity(build/"SIMULATION_SOURCE_MANIFEST.json"),"historical_PG484_resources_reused_as_Pro":False,"board_release_allowed":False})
print("R03_REUSE_AND_PHYSICAL_NOT_RUN_PRECHECK_PREPARED")
