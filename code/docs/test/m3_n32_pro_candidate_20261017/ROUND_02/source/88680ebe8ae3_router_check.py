"""Read-only independent router + existing complete arithmetic, exact capture2."""
import argparse
import json
from pathlib import Path

from router_model import derive, compare_router
from strict_capture import CaptureError, parse_f, parse_jsonl
from timeline import replay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("f_capture", type=Path)
    parser.add_argument("--rom-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        j = parse_jsonl(args.jsonl.read_text(encoding="utf-8"))
        f = parse_f(args.f_capture.read_text(encoding="utf-8"))
        roms = [[int(w, 16) for w in (args.rom_root / name).read_text(encoding="utf-8").split()]
                for name in ("oct_ratio_q16.mem", "sub_ratio_q16.mem", "lfo_sine_q15.mem",
                             "velocity_gain_rom.mem", "piano_band_4x256_8191.mem")]
        model = derive(f, roms[3])
        router = compare_router(model, j, f)
        arithmetic = replay(j, f, roms[:3], roms[3:], router=router)
        for key in ("state_actual_cycles", "predicted_states", "predicted_n", "predicted_q"):
            router.pop(key)
        print(json.dumps(dict(status="ROUTER_AND_AUDIO_MATCH_AWAITING_M2", router=router,
                              arithmetic=arithmetic, t060_complete=False), sort_keys=True))
        return 0
    except CaptureError as error:
        print(json.dumps(dict(status="REJECTED_ROUTER", diagnostic=str(error))))
        return 1
    except (OSError, UnicodeError, ValueError) as error:
        print(json.dumps(dict(status="INFRASTRUCTURE_FAILURE", diagnostic=str(error))))
        return 7


if __name__ == "__main__":
    raise SystemExit(main())
