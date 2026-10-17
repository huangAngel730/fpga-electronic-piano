"""One real or mutant pair: exit0 partial boundary audio math, exit1 math error.

Infrastructure errors are exit7, not a successfully rejected counterexample.
"""
import argparse
import json
from pathlib import Path

from strict_capture import CaptureError, parse_f, parse_jsonl
from timeline import replay
from router_model import derive, compare_router


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", type=Path, required=True)
    parser.add_argument("--f-capture", type=Path, required=True)
    parser.add_argument("--rom-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        roms = [[int(word, 16) for word in (args.rom_root / name).read_text(encoding="utf-8").split()]
                for name in ("oct_ratio_q16.mem", "sub_ratio_q16.mem", "lfo_sine_q15.mem")]
        j = parse_jsonl(args.jsonl.read_text(encoding="utf-8"))
        f = parse_f(args.f_capture.read_text(encoding="utf-8"))
        audio_roms = [[int(word, 16) for word in (args.rom_root / name).read_text(encoding="utf-8").split()]
                      for name in ("velocity_gain_rom.mem", "piano_band_4x256_8191.mem")]
        # Keep established specific arithmetic diagnostics, then eliminate the
        # old observed-router boundary on every successful pair. Finally replay
        # audio again with independently derived strobes and occupancy.
        replay(j, f, roms, audio_roms)
        router = compare_router(derive(f, audio_roms[0]), j, f)
        result = replay(j, f, roms, audio_roms, router=router)
        for key in ("state_actual_cycles", "predicted_states", "predicted_n", "predicted_q"):
            router.pop(key)
        result["router"] = router
        exit_code = 0
    except CaptureError as error:
        result, exit_code = {"status": "REJECTED_CONTRACT_OR_MATH", "diagnostic": str(error)}, 1
    except (OSError, UnicodeError, ValueError) as error:
        result, exit_code = {"status": "INFRASTRUCTURE_ERROR", "error": str(error)}, 7
    print(json.dumps(result, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
