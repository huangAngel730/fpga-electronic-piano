"""Independent integer PCM oracle and physical-WS stereo reconstruction."""
from bisect import bisect_right
import base64
from pathlib import Path


def pcm16(value):
    if not -8388608 <= value <= 8388607:
        raise ValueError("PCM24_RANGE")
    # Python floor division defines the approved signed arithmetic shift;
    # ties round toward +infinity, NOT symmetric/away-from-zero rounding.
    return max(-32768, min(32767, (value + 128) // 256))


def check_capture(path, scenario):
    path = Path(path)
    data = path.read_bytes()
    if path.suffix == ".b64":
        data = base64.b64decode(b"".join(data.split()), validate=True)
    rows = [line.split() for line in data.decode("utf-8").splitlines()]
    if not rows or rows[-1][:2] != ["END", scenario]:
        raise ValueError("MISSING_END_OR_TIMEOUT")
    allowed = {"H": 6, "A": 6, "V": 6, "S": 8, "U": 3, "E": 3,
               "SCENE": 4, "STATE": 5, "G": 4, "D": 6, "END": 4}
    for row in rows:
        if len(row) != allowed.get(row[0], -1):
            raise ValueError("MALFORMED_RECORD")
    pending = None
    held = (0, 0)
    ever = False
    hs = 0
    last_id = 0
    under = 0
    last_adoption = 0
    adopt = []
    times = []
    verified_v = 0
    misses = []
    last_time = -1
    for row in rows[:-1]:
        timestamp = float(row[1])
        if not timestamp >= last_time:
            raise ValueError("TIME_ORDER")
        last_time = timestamp
        kind = row[0]
        if kind == "H":
            identity, current, left, right = map(int, row[2:])
            if identity != current or identity != last_adoption or pending is not None:
                raise ValueError("HANDSHAKE_ID_OR_DUPLICATE")
            if identity <= last_id:
                raise ValueError("HANDSHAKE_OLD_FRAME")
            pending = (identity, left, right)
            pcm16(left); pcm16(right)
            last_id = identity
            hs += 1
        elif kind == "A":
            number, current, left, right = map(int, row[2:])
            if number != last_adoption + 1 or current != number - 1:
                raise ValueError("ADOPTION_SEQUENCE")
            if pending is not None:
                if pending[0] != current:
                    raise ValueError("ADOPTION_OLD_FRAME")
                held = pending[1:]
                pending = None
                ever = True
            elif ever:
                under += 1
                misses.append(number)
            if (left, right) != held:
                raise ValueError(f"BUFFER_ADOPTION frame={number} got={(left,right)} expected={held}")
            times.append(timestamp)
            adopt.append({"number": number, "pcm": held, "expected": tuple(map(pcm16, held)),
                          "under": under, "hs": hs})
            last_adoption = number
        elif kind == "V":
            number, frames, commits, actual_under = map(int, row[2:])
            if number != verified_v + 1 or number != last_adoption or frames != number or commits != hs or actual_under != under:
                raise ValueError("COUNTER_MISMATCH")
            verified_v += 1
    if not adopt or verified_v != len(adopt) or hs < 24:
        raise ValueError("EMPTY_ADOPTION_OR_HANDSHAKE")
    serial = [r for r in rows if r[0] == "S"]
    right_half = None
    pairs = []
    for index, row in enumerate(serial):
        number, ws, edges = map(int, row[2:5])
        word = int(row[5], 16)
        start, last, end = float(row[6]), float(row[7]), float(row[1])
        if number != index + 1 or ws != (1 if index % 2 == 0 else 0) or edges != 32:
            raise ValueError("PHYSICAL_WS_SLOT")
        if index and start != float(serial[index-1][1]):
            raise ValueError("PHYSICAL_SLOT_GAP")
        # All 32 actual BCLK rising edges are included. Fill=0 and the low
        # 16 bits end at the LAST edge preceding the physical WS transition.
        if word >> 16 or not start < last < end or not 10000 < last-start < 10200:
            raise ValueError("LSBJ_PADDING_OR_TIMING")
        value = word & 65535
        if value >= 32768:
            value -= 65536
        if ws == 0:
            right_half = (value, start)
        elif right_half is not None:
            position = bisect_right(times, right_half[1]) - 1
            if position < 0:
                raise ValueError("SERIAL_WITHOUT_ADOPTION")
            selected = adopt[position]
            actual = (value, right_half[0])  # WS high LEFT / low RIGHT
            if actual != selected["expected"]:
                raise ValueError(f"SERIAL_SAMPLE frame={selected['number']} got={actual} expected={selected['expected']}")
            if pairs and selected["number"] != pairs[-1]["number"] + 1:
                raise ValueError("SERIAL_DROPPED_OR_DUPLICATE_FRAME")
            pairs.append({**selected, "time": right_half[1]})
            right_half = None
    if not pairs or pairs[0]["number"] != 1 or len(pairs) < len(adopt)-2:
        raise ValueError("INCOMPLETE_STEREO_COVERAGE")
    result = {"scenario": scenario, "stereo_frames": len(pairs),
              "sample_comparisons": 2*len(pairs), "handshakes": hs,
              "adoptions": len(adopt), "underruns": under,
              "physical_half_slots": len(serial), "passed": True}
    period = (float(serial[-1][1])-float(serial[0][6]))/(32*len(serial))
    if not 325.3 < period < 325.8:
        raise ValueError("BCLK_RATE")
    result["bclk_average_period_ns"] = period
    if scenario == "normal":
        scenes = {r[2]: (float(r[1]), int(r[3])) for r in rows if r[0] == "SCENE"}
        names = {"FOUR", "OFF_BEGIN", "RELEASE0", "RELEASE1", "RELEASE2", "RELEASE3", "SILENT"}
        if scenes.keys() != names or scenes["FOUR"][1] != 4 or scenes["SILENT"][1] != 0:
            raise ValueError("MISSING_FOUR_RELEASE_TAIL_SCENES")
        four = [p for p in pairs if scenes["FOUR"][0] <= p["time"] < scenes["OFF_BEGIN"][0]]
        tail = [p for p in pairs if scenes["RELEASE3"][0] <= p["time"]]
        states = [tuple(map(int, r[2:])) for r in rows if r[0] == "STATE"]
        if states != [(n, (1 << (n+1))-1, 15) for n in range(4)]:
            raise ValueError("INDIVIDUAL_RELEASE_STATES")
        if len(pairs) < 256 or len(four) < 256 or len(tail) < 4800 or under != 0:
            raise ValueError("NORMAL_COVERAGE_OR_UNDERRUN")
        if not any(p["expected"] != (0, 0) for p in four) or not any(p["expected"] != (0, 0) for p in tail[:128]) or pairs[-1]["expected"] != (0, 0):
            raise ValueError("NONZERO_MUSIC_OR_RELEASE_TO_SILENCE")
        uart = [int(r[2], 16) for r in rows if r[0] == "U"]
        expected_uart = []
        for status, velocity in [(144, 100), (128, 0)]:
            for n in range(4):
                expected_uart += [status, 60+3*n, velocity]
        if uart != expected_uart or len([r for r in rows if r[0] == "E"]) != 8:
            raise ValueError("UART_MESSAGE_COVERAGE")
        result.update(four_voice_frames=len(four), tail_frames=len(tail), uart_bytes=len(uart))
    elif scenario == "diagnostic":
        diagnostics = [tuple(map(int, r[2:])) for r in rows if r[0] == "D"]
        gaps = [int(r[2]) for r in rows if r[0] == "G"]
        boundary = {0, 1, -1, 127, 128, 129, -127, -128, -129, 8388607,
                    8388479, 8388480, -8388608, -8388481, -8388480}
        observed = {v for p in pairs for v in p["pcm"]}
        if not boundary <= observed or not any(p["pcm"][0] != p["pcm"][1] for p in pairs):
            raise ValueError("DIAGNOSTIC_BOUNDARY_OR_STEREO_COVERAGE")
        if len(diagnostics) < 24 or len(gaps) != 3 or gaps != list(range(gaps[0], gaps[0]+3)) or under != 3 or misses != [n+1 for n in gaps]:
            raise ValueError("THREE_UNDERRUN_CONTRACT")
        by_number = {p["number"]: p for p in pairs}
        previous = by_number[misses[0]-1]["pcm"]
        if any(by_number[n]["pcm"] != previous for n in misses) or by_number[misses[-1]+1]["pcm"] == previous:
            raise ValueError("UNDERRUN_HOLD_OR_RECOVERY")
        result.update(held_frames=misses, recovery_frame=misses[-1]+1,
                      boundary_values_verified=len(boundary))
    else:
        raise ValueError("UNKNOWN_SCENARIO")
    return result
