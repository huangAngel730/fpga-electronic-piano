"""Audit exact inputs and derive the proposed N32-to-frame integration budget.

Static source evidence only. Never executes EDA, RTL simulation or production
patches. The proposed frame adapter does not exist yet; timing is conditional.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PIN = "52ad3dc5e27f499bc79bad5c1a6b8d4bbf8a4387"
EXPECTED_FROZEN = "883297182d9705788d5d04855b597ad8620ab2b1b8ca38727a8b06492a0454e9"
PLAN_VERSION = "night_n32_integration_contract_v1"
sys.path.insert(0, str(ROOT / "code/software/polyphony_scaling_candidate"))
from b2_clock import backend_calendar  # noqa: E402


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(path, pin=PIN):
    result = subprocess.run(["git", "show", pin + ":" + path], cwd=ROOT,
                            capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError("PINNED_INPUT_MISSING:" + path)
    return result.stdout


def budget(n, response, frame_to_admission=1, event_wait=None):
    if type(n) is not int or n not in (4, 8, 16, 32):
        raise ValueError("VOICE_CONFIGURATION")
    if type(response) is not int or not 1 <= response <= 64:
        raise ValueError("ROM_CONFIGURATION")
    if type(frame_to_admission) is not int or frame_to_admission < 1:
        raise ValueError("FRAME_ADMISSION_DELAY")
    if event_wait is not None and (type(event_wait) is not int or event_wait < 0):
        raise ValueError("EVENT_WAIT")
    launch = 12 + 6 * n
    calendar = backend_calendar(launch, n, response)
    first = 28 + 9 * n + n * response
    if first != calendar.wrapper_first:
        raise ValueError("SOURCE_CALENDAR_FORMULA_MISMATCH")
    # Consumer=result_hold accepts on first PRE-NBA visible valid; the frame
    # buffer accepts its registered PCM on the following edge, Ffirst+1.
    # Reserve a second edge for an eventual adapter boundary; this conservative
    # extra edge is a proposal, not observed integration latency.
    proposed_commit_reserve = 2
    scheduled_commit = frame_to_admission + first + proposed_commit_reserve
    normal_next_ready = frame_to_admission + first + 3
    total = None if event_wait is None else scheduled_commit + event_wait
    return dict(N=n, response=response, backend_launch_after_sample_accept=launch,
                backend_advance_after_sample_accept=calendar.advance,
                first_valid_after_sample_accept=first,
                last_lane_GAIN_after_sample_accept=calendar.lanes[-1],
                frame_to_sample_accept_proposed=frame_to_admission,
                result_to_frame_commit_reserved_edges=proposed_commit_reserve,
                earliest_proposed_commit_from_frame=scheduled_commit,
                normal_next_ready_from_frame=normal_next_ready,
                quiescent_833_headroom=833 - scheduled_commit,
                quiescent_commit_strictly_before_next_frame=scheduled_commit < 833,
                event_and_read_wait_cycles=event_wait,
                conditioned_total_commit_cycles=total,
                conditioned_before_next_frame=None if total is None else total < 833,
                general_service_deadline="UNKNOWN",
                adapter_implemented=False, physical_STA_passed=False)


def anchor(raw, needle, name):
    text = raw.decode("utf-8")
    if needle not in text:
        raise ValueError("SOURCE_ANCHOR_DRIFT:" + name)
    return dict(source=name, line=text[:text.index(needle)].count("\n") + 1,
                needle=needle)


def audit(resource_project, baseline_project):
    resource_project, baseline_project = resource_project.resolve(), baseline_project.resolve()
    frozen_raw = (resource_project / "frozen_receipt.json").read_bytes()
    if digest(frozen_raw) != EXPECTED_FROZEN:
        raise ValueError("EXACT_RESOURCE_FROZEN_RECEIPT")
    resource = json.loads(frozen_raw)
    if resource["source_pin"] != PIN or resource["synthesis_authorized"] is not False:
        raise ValueError("RESOURCE_PIN_OR_EXECUTION_STATE")
    actual = {p.relative_to(resource_project).as_posix() for p in resource_project.rglob("*") if p.is_file()}
    if actual != set(resource["artifacts"]) | {"frozen_receipt.json"}:
        raise ValueError("RESOURCE_EXACT_FILE_SET")
    for name, item in resource["artifacts"].items():
        raw = (resource_project / name).read_bytes()
        if len(raw) != item["bytes"] or digest(raw) != item["sha256"]:
            raise ValueError("RESOURCE_FILE_DRIFT:" + name)
    base_raw = (baseline_project / "frozen_receipt.json").read_bytes()
    base = json.loads(base_raw)
    if (base["version"] != "night_cache_parser_hold_20261010_v1" or
            base["input_count"] != 62 or base["project_file_count"] != 53 or
            base["new_RAM_reference_commit"] != "5e1d13c398fd1cf749c613a30b9238d1a46319b4"):
        raise ValueError("EXACT_BASELINE_CONFIGURATION")
    for name, item in base["inputs"].items():
        raw = (baseline_project / "inputs" / name).read_bytes()
        if digest(raw) != item["adapted_sha256"]:
            raise ValueError("BASELINE_SOURCE_DRIFT:" + name)
    paths = ["code/rtl/common/polyphony_scaling_candidate/b2d_event_audio.sv",
             "code/rtl/common/polyphony_scaling_candidate/b2_audio_backend.sv",
             "code/software/polyphony_scaling_candidate/b2_clock.py",
             "code/software/polyphony_scaling_candidate/b2j_check.py"]
    sources = {}
    raw_sources = {}
    for name in paths:
        raw = (ROOT / name).read_bytes()
        source_pin = "b2cf48c" if name.endswith("b2j_check.py") else PIN
        pinned = blob(name, source_pin)
        if raw.replace(b"\r\n", b"\n") != pinned:
            raise ValueError("CANDIDATE_OR_CALENDAR_DRIFT:" + name)
        raw_sources[name] = raw
        sources[name] = dict(pin=source_pin, raw_sha256=digest(raw), git_LF_sha256=digest(pinned))
    candidate = raw_sources[paths[0]]
    backend = raw_sources[paths[1]]
    top = (baseline_project / "inputs/sources/audio_visual_coexistence_top.sv").read_bytes()
    anchors = [anchor(candidate, "sample_ready = rst_n && idle && !cancel && !read_valid", paths[0]),
               anchor(candidate, "wire be_valid, be_ready, be_clipped, be_late", paths[0]),
               anchor(candidate, ".clipped(be_clipped)", paths[0]),
               anchor(candidate, "assign publish=state==HOLD && result_valid && result_ready && !stop", paths[0]),
               anchor(top, "u_audio_core.u_bank.slot_notes[6:0]", "baseline_top"),
               anchor(top, "u_audio_core.u_commit.pcm_valid", "baseline_top")]
    header = candidate.decode("utf-8").split(");", 1)[0]
    if re.search(r"output[^;]*\bclipped\b", header):
        raise ValueError("CLIP_INTERFACE_CHANGED_REAUDIT")
    matrix = [budget(n, response) for n in (4, 8, 16, 32) for response in range(1, 65)]
    matches = []
    different = []
    path_only = []
    for item in resource["original_inputs"]:
        staged = item["staged"]
        if staged in base["inputs"]:
            original_lf = item["original"]["lf_sha256"]
            current = (baseline_project / "inputs" / staged).read_bytes().replace(b"\r\n", b"\n")
            if digest(current) == original_lf:
                matches.append(staged)
            else:
                different.append(staged)
                original = blob(item["original"]["path"])
                normalize = lambda raw: re.sub(
                    rb'"[^"\r\n]*[/\\]([^/\\"\r\n]+\.mem)"',
                    rb'"MEM_ROOT/\1"', raw.replace(b"\r\n", b"\n"))
                if normalize(current) == normalize(original):
                    path_only.append(staged)
    sdc = (baseline_project / "inputs/constraints/audio_visual_hold055.sdc").read_text("utf-8")
    audio_hierarchy_constraints = [dict(line=i, text=line) for i, line in enumerate(sdc.splitlines(), 1)
                                   if "g_polyphonic.u_audio_core/u_bank" in line]
    if not audio_hierarchy_constraints:
        raise ValueError("EXPECTED_OLD_AUDIO_HIERARCHY_CONSTRAINTS_MISSING")
    return dict(schema=1, version=PLAN_VERSION,
                status="STATIC_INPUT_AND_INTEGRATION_PLAN_AUDITED_NOT_CONNECTED",
                resource_project=str(resource_project), baseline_project=str(baseline_project),
                resource_frozen_sha256=digest(frozen_raw), baseline_frozen_sha256=digest(base_raw),
                baseline_input_count=62, resource_artifacts=28,
                candidate_sources=sources, source_anchors=anchors,
                exact_common_sources=matches,
                common_sources_requiring_path_or_content_diff=different,
                proven_only_ROM_path_literal_differences=path_only,
                old_audio_hierarchy_constraints=audio_hierarchy_constraints,
                old_audio_constraints_reusable_without_new_endpoint_mapping=False,
                timing_matrix=matrix, representative=budget(32, 1),
                general_deadline="UNKNOWN", actual_resources="UNKNOWN",
                synthesis_authorized=False, Gowin_runs=0, integration_RTL_written=False,
                required_changes=[
                    dict(id="FRAME_REQUEST_GATE", reason="cancel=frame forces sample_ready low on frame; cannot use as same-edge calc_ready",
                         proposal="Separate frame admission credit and single pending 32bit-ID request; cancel old result, dispatch only on actual ready, never queue audio frames"),
                    dict(id="PREMIXED_PCM_COMMIT", reason="N32 already saturates/mixes PCM24; original commit accepts four lanes and mixes again",
                         proposal="New isolated stereo commit wrapper using unchanged pcm_result_hold/frame_buffer/clip_counter, no second mix"),
                    dict(id="CLIP_METADATA", reason="be_clipped is internal and final PCM cannot reveal exact-limit versus saturation",
                         proposal="Candidate successor copies frozen source and exposes/latches clipped with result ID; no math/ROM change; requires explicit source change review"),
                    dict(id="STATUS_AND_READ_PROFILE", reason="resource probe retains public READ; integration diagnostics/status choices change optimizations",
                         proposal="Preserve READ for initial integration or label new narrower profile and obtain its own resources; compute active population from occupied, register status, preserve real clip/commit count"),
                    dict(id="TOP_HIERARCHICAL_ALIASES", reason="old four-lane u_bank/u_commit hierarchy does not exist in b2d wrapper",
                         proposal="Isolated top successor wires explicit public PCM/ID/commit/debug ports, fixes note debug alias, retains existing PCM sender observer and display CDC; production unchanged")],
                new_combination_validation_required=True, original_4voice_fallback_preserved=True,
                physical_STA_passed=False, board_release_allowed=False, T060_T061_complete=False)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--resource-project", type=Path, required=True)
    cli.add_argument("--baseline-project", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    output.relative_to((ROOT / "code/output").resolve())
    if output == (ROOT / "code/output").resolve() or output.exists():
        raise ValueError("REFUSE_OUTPUT_ROOT_OR_EXISTING")
    result = audit(args.resource_project, args.baseline_project)
    output.mkdir(parents=True, exist_ok=False)
    payload = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (output / "integration_audit.json").write_bytes(payload)
    summary = dict(command=sys.argv, report_sha256=digest(payload),
                   producer_contract_source="Source analysis, not CodeGraph HDL index",
                   new_RTL_simulation=False, new_Gowin=False,
                   provisional_adapter_not_implemented=True)
    (output / "receipt.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(status=result["status"], rows=len(result["timing_matrix"]),
                         representative=result["representative"], required_changes=5)))


if __name__ == "__main__":
    main()
