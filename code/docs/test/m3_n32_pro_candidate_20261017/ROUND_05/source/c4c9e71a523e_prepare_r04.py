"""Preserve three signed normal cases; recheck N32 tail only, run new mutants."""
import json
from e4_common import ROOT,DOC,SOFT,identity,write_new

prior=DOC/"ROUND_03/RUN_RECEIPT.json"
assert identity(prior)["sha256"]=="9ab11f957def2aa78bde3ff3a520bd04b0fb1e78daa5f48cdd3c7b6964396fd7"
plan=json.loads((DOC/"CASE_PLAN.json").read_text(encoding="utf-8"))
plan["prior_normal_passes"]=[]
for name in ("normal_n4","normal_n8","normal_n16"):
    p=DOC/"ROUND_03"/name/"CHECK_RESULT.json"
    report=json.loads(p.read_text(encoding="utf-8"))
    assert report["status"]=="PASS_ISOLATED_FROZEN_PIANO_E4_PARTIAL"
    plan["prior_normal_passes"].append({"case":name,"result":identity(p),"receipt":identity(prior),"new_test_calls":0,"reason":"New checker change only applies to enabled retirement tail; N4/8/16 RETIRE=0 already passed"})
plan["cases"]=plan["cases"][3:]
old=json.loads(prior.read_text(encoding="utf-8"))
sim_index=old["cases"][-1]["simulate"]
assert old["cases"][-1]["case"]["name"]=="normal_n32" and old["calls"][sim_index]["exit_code"]==0
plan["cases"][0]["reuse_simulation"]={"receipt_relative":"ROUND_03/RUN_RECEIPT.json","receipt_sha256":identity(prior)["sha256"],"simulation_call_index":sim_index,"reason":"N32 source simulation and4802 all-lane retirement passed; checker-only tail-boundary repair"}
write_new(DOC/"CASE_PLAN_R04.json",plan)
write_new(DOC/"REPAIR_04.json",{"prior_round":3,"receipt":identity(prior),"failure":"N32 actual RTL/retirement PASS; checker resumed math one edge before actual reset, U1743651 after TAIL_END1743650 rejected","change":"Bound terminal-tail wait until actual reset within8cycles, no new business; bind TAIL_END completion mask to actual public D observations","checker":identity(SOFT/"check_e4.py"),"normal_n4_n8_n16_retested":False,"normal_n32_recompiled_or_resimulated":False,"next_cases":"N32 checker replay + unrun actual RTL mutants only","first_failure_preserved":True,"groups_already_consumed":3,"new_group":4})
print("R04_PREPARED_WITH_NORMAL_CAPTURE_REUSE")
