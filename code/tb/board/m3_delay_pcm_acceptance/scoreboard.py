"""H independent accepted-sample recurrence, mixer and actual PCM transport."""
from collections import defaultdict
from pathlib import Path


def signed(value, width):
    return value - (1 << width) if value & (1 << (width - 1)) else value


def sat(value):
    return max(-8388608, min(8388607, value))


def check_capture(path: Path):
    lines = path.read_text(encoding="ascii").splitlines()
    assert lines and lines[0].startswith("H1 "), "missing H header"
    depth = int(lines[0].split()[1])
    assert depth in (16, 1024) and lines[-1].startswith("END "), "incomplete H capture"
    counts = defaultdict(int)
    history, ptr, work, outputs = [0] * depth, 0, {}, {}
    mixed = None
    pending, held = None, 0
    ever = False
    old_frame, current = 0, 0
    epoch_underrun = 0
    raw_writes_for_cancel = 0
    cancelled_ids = set()
    for number, line in enumerate(lines[1:-1], 2):
        f = line.split()
        assert f and f[0] in ("R", "X", "K", "B", "E", "W", "O", "C"), f"bad record {number}"
        cycle = int(f[1])
        try:
            if f[0] == "R":
                counts["reset_epochs"] += 1
                counts["reset_dropped_results"] += len(outputs)
                history, ptr, work, outputs = [0] * depth, 0, {}, {}
                mixed, pending, held, ever = None, None, 0, False
                old_frame, current = 0, 0
                epoch_underrun = 0
                cancelled_ids.clear()
            elif f[0] == "B":
                assert len(f) == 11
                ident = int(f[2]); waves, env, mask, actual, lanes = map(lambda x: int(x, 16), f[3:8])
                pcm, mode, active = map(int, f[8:])
                real = []
                for lane in range(4):
                    wave = signed(waves >> (16 * lane) & 65535, 16)
                    gain = env >> (16 * lane) & 65535
                    assert gain <= 32767, "envelope range"
                    real.append(((wave * gain >> 15) * 256) if mask >> lane & 1 else 0)
                decoded = [signed(actual >> (24 * k) & 0xffffff, 24) for k in range(4)]
                assert decoded == real, "real Q15 gain mismatch"
                fixture = {0: real, 1: [4000000, 0, 0, 0], 2: [0] * 4,
                           3: [8388607] * 4, 4: [-8388608] * 4}[mode]
                assert [signed(lanes >> (24 * k) & 0xffffff, 24) for k in range(4)] == fixture, "mixer inputs"
                assert pcm == sat(sum(fixture)), "real mixer saturation"
                mixed = (cycle, ident, pcm)
                counts["bank_gain_mixer_results"] += 1
                counts["mixer_clips"] += int(sum(fixture) != pcm)
                counts["fourvoice_inputs"] += int(mode == 0 and active == 4)
            elif f[0] == "E":
                assert len(f) == 10
                ident, pcm, delay, dry, wet, fb, mode, active = map(int, f[2:])
                assert mixed == (cycle, ident, pcm), "effect input not actual mixer result"
                assert 0 <= delay < depth and all(0 <= g <= 32767 for g in (dry, wet, fb)), "effect parameters"
                delayed = history[(ptr - delay) % depth]
                raw = (pcm * dry >> 15) + (delayed * wet >> 15)
                value, write = sat(raw), sat(pcm + (delayed * fb >> 15))
                assert not work and not outputs, "unexpected overlapping effect work"
                work[cycle + 2] = (ident, ptr, write)
                outputs[ident] = (value, cycle)
                counts["accepted_samples"] += 1
                counts["effect_clips"] += int(value != raw)
                counts["dry_only_requests"] += int(wet == 0)
                counts["impulse_requests"] += int(mode == 1)
                if mode == 0 and active == 0:
                    assert pcm == 0, "retired voice input not zero"
                    counts["zero_voice_requests"] += 1
                    counts["nonzero_tail_results"] += int(value != 0)
                if mode == 2:
                    counts["fixture_feedback_results"] += int(value != 0)
            elif f[0] == "W":
                assert len(f) == 5 and cycle in work, "unexpected/missing history commit"
                ident, expected_ptr, write = work.pop(cycle)
                address, next_ptr, actual = map(int, f[2:])
                assert (address, next_ptr, actual) == (expected_ptr, (ptr + 1) % depth, write), "feedback history/address mismatch"
                history[ptr] = write
                ptr = next_ptr
                counts["raw_writes"] += 1
                if ident in cancelled_ids:
                    raw_writes_for_cancel += 1
            elif f[0] == "X":
                cancelled_ids.update(outputs)
                counts["cancelled_results"] += len(outputs)
                outputs.clear()  # history/work intentionally NOT rolled back
            elif f[0] == "O":
                assert len(f) == 5
                ident, value, ready = map(int, f[2:])
                assert ident in outputs, "stale/cancelled result"
                expected, launch = outputs[ident]
                assert cycle >= launch + 4 and value == expected, "wet/tail PCM mismatch"
                assert ident == current, "wrong effect frame id"
                if ready:
                    counts["result_consumed"] += 1
                    outputs.pop(ident)
                    counts["expected_pcm_commits"] += 1
                    mixed = ("commit", ident, value)
                else:
                    counts["output_stalls"] += 1
            elif f[0] == "C":
                assert len(f) == 5
                ident, left, right = map(int, f[2:])
                assert mixed == ("commit", ident, left) and left == right and ident == current, "PCM tag/data commit mismatch"
                assert pending is None, "duplicate PCM frame commit"
                pending = left
                counts["pcm_commits"] += 1
            elif f[0] == "K":
                assert len(f) == 8
                ident, valid, left, right, underrun, phase = map(int, f[2:])
                if old_frame:
                    assert cycle - old_frame in (1041, 1042), "normal 48k cadence"
                old_frame = cycle
                assert ident == current and valid == int(pending is not None), "frame generation/pending mismatch"
                assert underrun == epoch_underrun, "actual underrun counter mismatch"
                assert left == right == (pending if valid else held), "actual frame buffer consumption mismatch"
                if valid:
                    held, pending, ever = pending, None, True
                elif ever:
                    counts["intentional_missing_frames"] += 1
                    epoch_underrun += 1
                if phase == 1:
                    assert valid, "normal PCM underrun"
                    counts["normal_frames"] += 1
                current = (ident + 1) & 0xffffffff
                counts["frame_edges"] += 1
        except (AssertionError, ValueError, IndexError, KeyError) as error:
            raise AssertionError(f"{error}; line={number} cycle={cycle}") from error
    final = list(map(int, lines[-1].split()[1:]))
    assert len(final) == 4 and final[1] == counts["normal_frames"] >= 512, "required normal frames"
    assert counts["zero_voice_requests"] >= depth and counts["nonzero_tail_results"] > 0, "echo tail coverage"
    assert counts["fixture_feedback_results"] > 0 and counts["effect_clips"] > 0 and counts["mixer_clips"] > 0, "boundary coverage"
    assert counts["dry_only_requests"] >= 8 and counts["impulse_requests"] >= 2, "dry/impulse coverage"
    assert counts["pcm_commits"] == counts["expected_pcm_commits"], "commit conservation"
    assert counts["cancelled_results"] >= 4 and raw_writes_for_cancel >= 2 and counts["reset_epochs"] >= 2, "cancel/reset lifecycle coverage"
    assert not work and not outputs, "incomplete pipeline"
    assert counts["accepted_samples"] == counts["result_consumed"] + counts["cancelled_results"] + counts["reset_dropped_results"], "effect transaction conservation"
    return dict(depth=depth, cancelled_history_writes=raw_writes_for_cancel, **counts)
