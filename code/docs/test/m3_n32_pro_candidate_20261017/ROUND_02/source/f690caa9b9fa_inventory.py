"""Audited logical storage inventory of frozen L, NOT a generic SV parser.

Packed buses are split into per-voice fields without removing duplicate storage.
Candidate N>4 widths are proposals; frozen declarations remain four-lane.
"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FROZEN = ROOT / "code/rtl/138K_try/hold_trials_20261005/L_locations_guard065"
BASELINE = "6f3e813"


def identity(path):
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "lf_sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()}


def slot_width(n):
    if type(n) is not int or n not in (4, 8, 16, 32):
        raise ValueError("N_NOT_SUPPORTED")
    return (n - 1).bit_length()


# Each group retains exact field names, source anchor, bit width and copy class.
# 'slot' and 'scan' are proposed scalable widths, not claims about frozen RTL.
GROUPS = [
    ("piano_dds_oscillator", "logic [31:0] phase_acc", "voice_context",
     {"phase_acc": 32}, "sample tick; reset clears; cancel does not roll back"),
    ("piano_dds_oscillator", "logic [10:0] attack_samples_left", "voice_context",
     {"attack_samples_left": 11}, "note-on loads; tick decrements; reset clears"),
    ("piano_dds_oscillator", "logic [1:0] active_table", "voice_context",
     {"active_table": 2, "pending_table": 2, "table_change_pending": 1},
     "note-on/tick/wrap table policy; reset clears pending"),
    ("piano_dds_oscillator", "output logic signed [15:0] dout", "voice_work",
     {"dout": 16}, "synchronous wave ROM read every clock; qualify by context"),
    ("adsr_piano_envelope", "logic [3:0] state", "voice_context",
     {"state": 4}, "event/preparation clocks/tick; reset IDLE; keep private states"),
    ("adsr_piano_envelope", "logic [31:0] level_q16", "voice_context",
     {"level_q16": 32, "start_q16": 32, "peak_q16": 32, "sustain_q16": 32},
     "event/preparation/tick; sustain uses previous registered product"),
    ("adsr_piano_envelope", "logic signed [32:0] step_q16", "voice_context",
     {"step_q16": 33, "elapsed": 13, "pending_tick": 1,
      "release_start_q16": 32, "rom_addr": 10},
     "event and preparation/tick; retain Release and pending tick on context switch"),
    ("adsr_piano_envelope", "logic signed [32:0] step_delta_q", "voice_work",
     {"step_delta_q": 33, "reciprocal_q": 26, "step_product_q": 59,
      "sustain_product_q": 45, "rom_dout": 16},
     "continuous pipeline/ROM; NOT safely discardable until B2 equivalence proves it"),
    ("pitch_mod_fcw_pipeline", "logic[31:0]lfo_phase", "voice_context",
     {"lfo_phase": 32}, "note-on resets; accepted enable advances; cancel no rollback"),
    ("pitch_mod_fcw_pipeline", "logic signed[15:0]sine_s0", "voice_work",
     {"sine_s0": 16, "depth_s0": 10, "semi_s0": 17, "semi_s1": 17,
      "sine_product_s1": 26, "total_s2": 18, "oct_s3": 20, "sub_s3": 20,
      "ratio_s4": 40, "fcw_product_s5": 57, "base_s0": 32, "base_s1": 32,
      "base_s2": 32, "base_s3": 32, "base_s4": 32, "valid_pipe": 6,
      "fcw_out": 32, "fcw_valid": 1},
     "enable/valid-qualified pipeline; reset invalidates; retain pending work conservatively"),
    ("voice_allocator_4", "typedef struct packed", "voice_context",
     {"note_active": 1, "in_release": 1, "source": 4, "channel": 4,
      "note": 8, "age": "slot"},
     "allocation/release/retire; relative LRU ranks, not an unbounded age counter"),
    ("polyphonic_event_router", "output logic [3:0] slot_note_on", "voice_context",
     {"slot_note_on": 1, "slot_note_off": 1, "slot_occupied": 1,
      "slot_releasing": 1, "slot_velocity": 10, "slot_fcw": 32,
      "slot_notes": 8, "slot_sources": 4, "slot_channels": 4,
      "slot_generation": 32, "retire_pending": 1, "retire_generation": 32},
     "registered router state; generation wraps modulo 2^32; full identity guards retire"),
    ("sustain_controller", "logic [3:0] occupied", "voice_context",
     {"occupied": 1, "key_down": 1, "deferred": 1, "releasing": 1,
      "pending_mask": 1, "pending_generations": 32, "source_mem": 4,
      "channel_mem": 4, "note_mem": 7, "generation_mem": 32},
     "accepted command/ACK; pending release payload immutable until ACK; reset clears"),
    ("performance_control_snapshot", "logic [28:0] control_mem", "identity",
     {"control_mem.range": 5, "control_mem.mod": 12, "control_mem.bend": 12,
      "initialized": 1}, "identity=source4 concatenated channel4; write event/read snapshot; reset invalidates"),
    ("sustain_controller", "logic [255:0] pedal_down", "identity",
     {"pedal_down": 1}, "256 independent source/channel pedals; panic/reset clears"),
    ("performance_control_snapshot", "output logic snapshot_valid", "snapshot",
     {"snapshot_occupied": 1, "snapshot_sources": 4, "snapshot_channels": 4,
      "snapshot_generations": 32, "snapshot_pitch_bend": 12,
      "snapshot_modulation": 12, "snapshot_pitch_range": 5},
     "one shared control read per cycle; events locked until snapshot ends"),
    ("pitch_mod_snapshot_pipeline", "logic[3:0]held_occupied", "snapshot",
     {"held_occupied": 1, "held_sources": 4, "held_channels": 4,
      "held_generations": 32, "result_occupied": 1, "result_sources": 4,
      "result_channels": 4, "result_generations": 32, "result_fcw": 32},
     "accept holds identity; result handshake or frame cancel invalidates token"),
    ("polyphonic_envelope_bank", "logic [127:0] frozen_base", "snapshot",
     {"frozen_base": 32, "computed_fcw": 32, "frozen_occupied": 1,
      "frozen_sources": 4, "frozen_channels": 4, "frozen_generations": 32,
      "result_envelopes": 16, "result_waves": 16, "result_fcw": 32,
      "result_occupied": 1, "result_states": 3},
     "CAPTURE freezes; ADVANCE once; HOLD until consumed; frame cancels result, not DSP"),
    ("voice_allocator_4", "output logic [1:0] allocated_slot", "global",
     {"allocated_slot": "slot", "slot_valid": 1, "release_slot": "slot",
      "release_target_valid": 1}, "registered allocation/release outputs; reset clears"),
    ("polyphonic_event_router", "performance_event_t held_event", "global",
     {"held_event": 64, "state": 4, "target_slot": "slot", "release_index": "scan"},
     "one event held; scan index includes N sentinel; reset IDLE"),
    ("performance_control_snapshot", "logic busy", "global",
     {"busy": 1, "read_slot": "slot", "control_applied": 1, "invalid_range": 1,
      "snapshot_valid": 1, "snapshot_id": 32}, "atomic request; hold valid; reset clears"),
    ("pitch_mod_snapshot_pipeline", "logic busy,cancelled", "global",
     {"busy": 1, "cancelled": 1, "age": 3, "held_id": 32,
      "result_valid": 1, "result_id": 32}, "one math token; cancel drains; no LFO rollback"),
    ("polyphonic_envelope_bank", "logic [3:0] phase", "global",
     {"phase": 4, "delay_count": 3, "pending_req_id": 32, "resume_requested": 1,
      "result_valid": 1, "result_req_id": 32}, "frame enters DRAIN; pending request survives drain"),
    ("pcm_result_hold", "logic request_window", "global",
     {"request_window": 1, "pcm_valid": 1, "pcm_req_id": 32,
      "pcm_left": 24, "pcm_right": 24, "pcm_clip_any": 1},
     "current request only; once; frame expires; reset clears valid"),
    ("pcm_frame_buffer", "logic ever_committed", "global",
     {"sample_req": 1, "sample_req_id": 32, "pending_valid": 1,
      "pending_left": 24, "pending_right": 24, "held_left": 24, "held_right": 24,
      "ever_committed": 1, "request_active": 1, "audio_frame_count": 32,
      "pcm_request_count": 32, "pcm_commit_count": 32, "audio_underrun": 32},
     "one pending stereo pair; frame holds old PCM on underrun; reset clears"),
    ("system_status_counters", "logic [31:0] elapsed", "global",
     {"elapsed": 32, "request_active": 1, "max_processing_cycles": 32},
     "accepted request/commit; saturation; reset clears"),
    ("pcm_clip_counter", "output logic [COUNTER_WIDTH-1:0] clip_count", "global",
     {"clip_count": 32}, "increment only successful clipped commit; reset clears"),
]


def inventory(n):
    slot = slot_width(n)
    rows = []
    for module, anchor, category, fields, lifecycle in GROUPS:
        path = FROZEN / "sources" / (module + ".sv")
        lines = path.read_text(encoding="utf-8").splitlines()
        matches = [i + 1 for i, line in enumerate(lines) if anchor in line]
        if len(matches) != 1:
            raise ValueError(f"SOURCE_ANCHOR_MISMATCH:{module}:{anchor}")
        widths = {name: (slot if width == "slot" else slot + 1
                         if width == "scan" else width)
                  for name, width in fields.items()}
        copies = 256 if category == "identity" else 1 if category == "global" else n
        rows.append({"module": module, "fields": widths, "class": category,
                     "copies": copies, "bits": sum(widths.values()) * copies,
                     "source": identity(path), "line": matches[0],
                     "anchor": anchor, "rw_lifecycle_invalidation": lifecycle})
    return rows


ROM_SHAPES = {
    "lfo_sine_q15.mem": (1024, 16, True, "lfo_lut; sync read"),
    "oct_ratio_q16.mem": (50, 20, True, "oct_lut; sync read"),
    "sub_ratio_q16.mem": (1024, 20, True, "sub_lut; XOR-permuted physical address in L"),
    "velocity_gain_rom.mem": (1024, 16, True, "gain_rom; sync read"),
    "piano_band_4x256_8191.mem": (1024, 16, True, "rom_data; piano mode sync read"),
    "sine_1024_8192.mem": (1024, 16, False, "alternative sine mode, not extra piano ROM"),
    "sine_1024_32767.mem": (1024, 16, False, "unused bank default overridden by audio core"),
}


def rom_inventory():
    rows = []
    for name, (depth, width, active, use) in ROM_SHAPES.items():
        path = FROZEN / "rom" / name
        words = path.read_text(encoding="utf-8").split()
        if len(words) != depth or any(not re.fullmatch(r"[0-9a-fA-F]+", w)
                                      or int(w, 16) >= 1 << width for w in words):
            raise ValueError(f"ROM_GEOMETRY:{name}")
        rows.append({"name": name, "depth": depth, "width": width,
                     "bits_per_copy": depth * width, "active_piano": active,
                     "use": use, "read_ports_per_copy": 1, "source": identity(path)})
    return rows


def capacities():
    path = FROZEN / "impl/pnr/audio_visual_coexistence_top.rpt.txt"
    raw = path.read_text(encoding="utf-8")
    rows = {}
    for resource, expected, unit in (("Logic", 138240, "tool Logic units, NOT LUT"),
                                      ("Register", 139095, "registers"),
                                      ("DSP", 298, "DSP blocks"),
                                      ("BSRAM", 340, "BSRAM blocks, NOT KiB")):
        match = re.search(rf"^  {resource}\s+\|\s+(\d+)/(\d+)", raw, re.M)
        if not match or int(match[2]) != expected:
            raise ValueError(f"CAPACITY_SOURCE:{resource}")
        rows[resource] = {"capacity": expected, "old_whole_design_used": int(match[1]),
                          "unit": unit}
    return {"source": identity(path), "resources": rows, "SSRAM_capacity": None,
            "not_a_new_synthesis": True}


def verify_manifest():
    path = FROZEN / "input_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    entries = manifest["inputs"]
    if len(entries) != 56 or len({e["path"] for e in entries}) != 56:
        raise ValueError("FROZEN_LIST_NOT_56_UNIQUE")
    actual = []
    for entry in entries:
        child = FROZEN / entry["path"]
        child.resolve().relative_to(FROZEN.resolve())
        item = identity(child)
        # V0208 already records exactly these three Git LF carriers of CRLF
        # originals. Recover in MEMORY only; do not rewrite the frozen ROMs.
        recovery = {
            "rom/lfo_sine_q15.mem": "6f68f32afdf43cb8cbe6ff7bf4db155282d8ebf8783b94ebf690a5cd0d137060",
            "rom/oct_ratio_q16.mem": "65185caf2722c98cd5406ecff0819f8b011cbbe6a5b9ae1974d3a03f4cf15fbd",
            "rom/sub_ratio_q16.mem": "9530577dfbc9b901d83abaa1a6f1c929241f7c092b5fc556b106b0c8bffc984e",
        }
        item["original_manifest_sha256"] = entry["candidate_SHA256"]
        item["original_recovery"] = "identity_LF"
        if item["lf_sha256"] != entry["candidate_SHA256"]:
            restored = child.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            if (recovery.get(entry["path"]) != item["lf_sha256"]
                    or hashlib.sha256(restored).hexdigest() != entry["candidate_SHA256"]):
                raise ValueError(f"FROZEN_HASH:{entry['path']}")
            item["original_recovery"] = "exact_documented_LF_to_CRLF_in_memory"
        actual.append(item)
    if sum("/rom/" in e["path"] for e in actual) != 7:
        raise ValueError("FROZEN_ROM_COUNT")
    return actual
