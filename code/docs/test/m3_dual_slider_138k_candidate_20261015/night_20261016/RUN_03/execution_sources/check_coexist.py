"""D coexistence evidence. Reuse frozen C public-interface decoder read-only."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
C_CHECK = ROOT / "code/software/m3_40mhz_pcm_i2s_latency_20261015/check_capture.py"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check(audio_path, visual_path):
    spec = importlib.util.spec_from_file_location("frozen_c_decoder", C_CHECK)
    decoder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(decoder)
    audio = decoder.check(audio_path, expected_underflows=0)
    # Reset cancels old in-flight work; do not call that cross-reset no-loss.
    cancelled = []
    reset_serial_incomplete = []
    for item in audio["request_ledger"]:
        if item["epoch"] == 1 and item["status"] in ("IN_FLIGHT", "COMMITTED"):
            item["status"] = "RESET_CANCELLED"
            cancelled.append(item["id"])
        elif item["epoch"] == 1 and item["status"] == "ADOPTED":
            item["status"] = "RESET_INTERRUPTED_SERIAL_AFTER_ADOPTION"
            reset_serial_incomplete.append(item["id"])
        elif item["epoch"] == 2 and item["status"] in ("IN_FLIGHT", "COMMITTED", "ADOPTED"):
            item["status"] = "WINDOW_END_NOT_FULLY_OBSERVED"
    require(cancelled == [96], "D_RESET_OUTSTANDING_REQUEST")
    require(reset_serial_incomplete == [95], "D_RESET_INTERRUPTED_SERIAL")
    text = Path(visual_path).read_text(encoding="ascii").splitlines()
    require(text[0] == "D_AUDIO_VISUAL_COEXIST_V1,ACCELERATED_DISPLAY_FRAMES,40000000,25000000",
            "D_VISUAL_HEADER")
    require(text[-1] == "END,58", "D_VISUAL_END_OR_CHECK_COUNT")
    expected = {
        "RESET_RELEASE_NO_DISPLAY_GHOST", "HELD_RISE_WITH_REAL_AUDIO",
        "RELEASE_RISE_WITH_REAL_AUDIO", "MODE_MAILBOX_DELIVERED_PENDING_FRAME",
        "FALLING_MODE_WITH_REAL_AUDIO", "FALLING_MOVES_WITH_REAL_AUDIO",
        "FALLING_EXIT_WITH_REAL_AUDIO", "SWITCH_BACK_WITH_REAL_AUDIO",
        "NO_DISPLAY_DROP_DESYNC",
    }
    checks = {1: [], 2: []}
    frames = {1: [], 2: []}
    for line in text[1:-1]:
        row = line.split(",")
        require(row[0] in ("CHECK", "FRAME"), "D_VISUAL_ROW_KIND")
        epoch = int(row[2])
        require(epoch in checks, "D_VISUAL_EPOCH")
        if row[0] == "CHECK":
            require(len(row) == 8, "D_CHECK_FIELDS")
            checks[epoch].append(row[3])
        else:
            require(len(row) == 11, "D_FRAME_FIELDS")
            frames[epoch].append(list(map(int, row[1:])))
    coverage = {}
    for epoch in (1, 2):
        counts = Counter(checks[epoch])
        require(set(counts) == expected | {"PCM_COMMIT_AND_FRAME_DURING_MOVEMENT"}
                and all(counts[k] == 1 for k in expected)
                and counts["PCM_COMMIT_AND_FRAME_DURING_MOVEMENT"] == 20,
                "D_VISUAL_CHECK_COMPLETENESS")
        sequence = frames[epoch]
        require(len(sequence) == 20 and [r[2] for r in sequence] == list(range(1, 21)),
                "D_VISUAL_FRAME_COMPLETENESS")
        require([r[3] for r in sequence] == [0]*4 + [1]*15 + [0], "D_MODE_CALENDAR")
        require(sequence[0][5] == sequence[1][5] == 1
                and sequence[1][6] < sequence[0][6]
                and sequence[2][5] == 0 and sequence[3][7] < sequence[2][7],
                "D_LIVE_GEOMETRY")
        require(sequence[5][8] == sequence[6][8] == 1
                and sequence[6][9] > sequence[5][9] and sequence[-2][8] == 0,
                "D_FALLING_GEOMETRY")
        observed = [r for r in audio["serial_frames"] if r["epoch"] == epoch]
        # Require actual decoded frames in each display regime, not cadence counts.
        live = [r for r in observed if sequence[0][0] < r["end"] < sequence[3][0]]
        falling = [r for r in observed if sequence[4][0] < r["end"] < sequence[-2][0]]
        require(live and falling, "D_NO_SERIAL_DURING_DISPLAY_REGIME")
        coverage[str(epoch)] = {
            "display_frames": 20, "checks": len(checks[epoch]),
            "decoded_live_frames": len(live), "decoded_falling_frames": len(falling),
            "serial_frame_continuity": True,
        }
    return {
        **audio, "scope": "D_ISOLATED_DISPLAY_AND_ORIGINAL_AUDIO_MODULE_COEXISTENCE",
        "evidence_kind": "DIAGNOSTIC_PCM_PRODUCER_NOT_R05",
        "visual_sha256": hashlib.sha256(Path(visual_path).read_bytes()).hexdigest(),
        "visual_audio_coverage": coverage,
        "reset_cancelled_request_ids_epoch1": cancelled,
        "reset_interrupted_serial_ids_epoch1": reset_serial_incomplete,
        "display_frame_rate": "ACCELERATED_FIXTURE_NOT_FULL_RASTER",
        "real_r05_algorithm": "UNKNOWN_NOT_RUN", "full_top": "NOT_TESTED",
        "hit_flash": "KNOWN_FAIL_DEFERRED_NOT_TESTED", "hardware": "NOT_TESTED",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("visual", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = check(args.audio, args.visual)
        code = 0
    except (ValueError, OSError, UnicodeError, IndexError) as exc:
        result = {"passed": False, "diagnostic": str(exc), "board_release_allowed": False}
        code = 1
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("request_ledger", "serial_frames")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
