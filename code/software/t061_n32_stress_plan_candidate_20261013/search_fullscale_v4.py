"""Input-only exact fullscale search and full frozen-model witness replay."""
from pathlib import Path
import json
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_v4 import FrameOracle, ROM_NAMES
from dds_model import note_fcw, signed


def search():
    start = time.monotonic()
    oracle = FrameOracle()
    gain, piano = oracle.rom[ROM_NAMES[0]], oracle.rom[ROM_NAMES[1]]
    for note in (60, 57, 64, 48, 72, 36):
        fcw = note_fcw(note)
        for tick in range(1, 241):
            if time.monotonic()-start >= 300:
                raise ValueError("SEARCH_300_SECOND_BOUND")
            phase = (fcw*tick) & 0xffffffff
            values = []
            for velocity in range(1024):
                table = 0 if velocity >= 256 else 1
                wave = signed(piano[(table << 8) | (phase >> 24)], 16)
                step = ((gain[velocity] << 16)*17895697) >> 32
                envelope = (step*tick) >> 16 if tick < 240 else gain[velocity]
                values.append((wave*envelope) >> 15)
            inverse = {value: velocity for velocity, value in enumerate(values)}
            for velocity, value in enumerate(values):
                target = -32768-30*value
                for other, first in inverse.items():
                    second = inverse.get(target-other)
                    if second is None:
                        continue
                    # Every candidate is independently replayed with all
                    # Router events and clocked Envelope/DDS registers.
                    witness = FrameOracle()
                    witness.apply(0, {"op": "reset"})
                    for lane in range(32):
                        witness.apply(lane+1, dict(op="note_on", source=lane//16,
                            channel=lane%16, note=note, expression=900,
                            velocity=velocity if lane < 30 else first if lane == 30 else second))
                    for sample in range(tick):
                        result = witness.apply(sample+33, dict(op="sample", result_id=sample,
                                                              disposition="PUBLISH"))
                    if result["left_pcm"] == -8388608 and result["clipped"] == 0:
                        return dict(status="INPUT_ONLY_EXACT_FULLSCALE_WITNESS", note=note,
                                    tick=tick, velocities=[velocity, first, second],
                                    voice_counts=[30, 1, 1], left_pcm=-8388608, right_pcm=-8388608,
                                    clipped=0, slot_pcm=result["slot_pcm"],
                                    elapsed_seconds=time.monotonic()-start,
                                    source="FROZEN_ROUTER_ENVELOPE_DDS_ROM_NO_DUT_INPUT")
    raise ValueError("NO_WITNESS_IN_SEARCH_DOMAIN")


if __name__ == "__main__":
    print(json.dumps(search(), sort_keys=True))
