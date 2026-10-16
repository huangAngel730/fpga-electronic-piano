"""Input-owned Python serial fixture, NOT Pro RTL or recorded board data."""
import json
from pathlib import Path

M = 1 << 32
STEP = 659706977
HEADER = {"kind": "HEADER", "schema": "D_PT8211_FIXTURE_V1",
          "origin": "ISOLATED_PYTHON_FIXTURE_NOT_PRO_DUT", "clock_hz": 40000000}
# Explicit hand boundary values (PCM24 left/right, expected signed DAC16 L/R).
VECTORS = [(0, -1, 0, 0), (8388607, -8388608, 32767, -32768),
           (8388480, 8388479, 32767, 32767), (127, 128, 0, 1),
           (129, -127, 1, 0), (-128, -129, 0, -1), (-255, -256, -1, -1),
           (-257, 255, -1, 1), (256, 257, 1, 1),
           (1234567, -2345678, 4823, -9163),
           (-8388480, -8388481, -32767, -32768),
           (7654321, -6543210, 29900, -25559),
           (32768, -32768, 128, -128), (65535, -65535, 256, -256),
           (8388352, -8388352, 32767, -32767), (1, -257, 0, -1)]


def build_plan():
    epochs = [{"epoch": 0, "reset_start": 1, "active_start": 7, "stable_start": 23, "end": 19000},
              {"epoch": 1, "reset_start": 19001, "active_start": 19005, "stable_start": 19021, "end": 38000}]
    frames = []
    for e in epochs:
        index = 1
        while True:
            # Independent closed-form calendar; producer uses a running NCO.
            cycle = e["active_start"] - 1 + (index * 128 * M + STEP - 1) // STEP
            if cycle > e["end"]:
                break
            frames.append({"epoch": e["epoch"], "frame": index, "cycle": cycle,
                           "request_cycle": cycle + 1, "request_id": index,
                           "vector_index": (index - 1) % len(VECTORS)})
            index += 1
    return {"schema": "D_INPUT_PLAN_V1", "origin": HEADER["origin"], "clock_hz": 40000000,
            "sample_rate_nominal_hz": 48000, "bclk_nco_step": STEP, "cycles": 38000,
            "epochs": epochs, "frames": frames,
            "vectors": [{"left": a, "right": b, "dac_left": c, "dac_right": d} for a, b, c, d in VECTORS],
            "pa_en_active_high": True, "fixture_stable_wait_cycles": 8,
            "fixture_commit_delay_cycles": 32, "Pro_hardware_stable_wait": "UNKNOWN",
            "Pro_source_ROM_trace": "MISSING", "board_release_allowed": False}


def producer_quantize(value, unsigned_bug=False):
    if unsigned_bug and value < 0:
        value += 1 << 24
    shifted = (value + 128) >> 8
    return min(32767, max(-32768, shifted))


def records(plan, fault=None):
    yield HEADER
    phase = bclk = ws = din = slot = shift = 0
    held = (0, 0, 0)
    pending = None
    request_cycle = commit_at = None
    req_id = frame_id = stable_count = 0
    latched = (0, 0)
    epoch_index = 0
    for cycle in range(1, plan["cycles"] + 1):
        if cycle > plan["epochs"][epoch_index]["end"]:
            epoch_index += 1
        e = plan["epochs"][epoch_index]
        epoch = e["epoch"]
        reset = cycle < e["active_start"]
        stable = cycle >= e["stable_start"]
        if reset:
            phase = bclk = ws = din = slot = shift = 0
            held = (0, 0, 0); pending = None
            request_cycle = commit_at = None
            req_id = frame_id = stable_count = 0
            latched = (0, 0)
        stable_count = stable_count + 1 if not reset and stable else 0
        pa_en = int(stable_count >= plan["fixture_stable_wait_cycles"])
        if fault == "pa_wrong_active_polarity" and pa_en:
            pa_en = 0
        if fault == "pa_early" and not reset and not stable:
            pa_en = 1
        if fault == "pa_reset" and reset:
            pa_en = 1
        carry = int(not reset and phase + STEP >= M)
        frame_tick = int(bool(carry and bclk and slot == 63))
        request = int(not reset and request_cycle == cycle)
        commit = int(not reset and commit_at == cycle)
        if fault == "miss_deadline" and epoch == 0 and req_id == 1:
            commit = 0
        vector = plan["vectors"][(max(1, req_id) - 1) % len(VECTORS)]
        play = pending if pending is not None else held
        row = {"kind": "TICK", "cycle": cycle, "epoch": epoch, "rst_n": int(not reset),
               "clock_stable": int(stable), "pa_en": pa_en, "frame_tick": frame_tick,
               "request": request, "request_id": req_id, "commit": commit,
               "pcm_epoch": epoch, "pcm_id": req_id, "left": vector["left"], "right": vector["right"],
               "pending": int(pending is not None), "play_epoch": epoch,
               "play_id": play[2], "play_left": play[0], "play_right": play[1],
               "bclk": bclk, "ws": ws, "din": din}
        if fault == "old_epoch" and epoch == 1 and commit:
            row["pcm_epoch"] = 0
        if fault == "reset_not_silent" and reset and cycle == 19002:
            row["din"] = 1
        if fault == "missing_frame" and epoch == 0 and frame_id == 1 and frame_tick:
            row["frame_tick"] = 0
        if fault == "x_pin" and cycle == 10000:
            row["din"] = "x"
        yield row
        if reset:
            continue
        phase = (phase + STEP) % M
        if carry:
            if bclk:
                ws = slot // 32
                if fault == "ws_boundary":
                    ws = int(31 <= slot <= 62)
                if slot % 32 == 16:
                    value = latched[0 if slot >= 32 else 1]
                    value = producer_quantize(value, fault == "sign_extension")
                    shift = (value & 65535) << 16
                    if fault == "shift_one_bit":
                        shift = (shift << 1) & 0xFFFFFFFF
                else:
                    shift = (shift << 1) & 0xFFFFFFFF
                din = shift >> 31
                slot = (slot + 1) % 64
            bclk ^= 1
        if frame_tick:
            latched = play[:2]
            if fault == "left_right_swap":
                latched = tuple(reversed(latched))
            if pending is not None:
                held = pending; pending = None
            frame_id += 1
            request_cycle = cycle + 1
            req_id = frame_id
            commit_at = cycle + plan["fixture_commit_delay_cycles"]
        elif commit:
            pending = (vector["left"], vector["right"], req_id)
    yield {"kind": "END", "cycle": plan["cycles"], "epoch": plan["epochs"][-1]["epoch"]}


def emit(path, plan, fault=None):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        for row in records(plan, fault):
            stream.write(json.dumps(row, separators=(",", ":")) + "\n")
