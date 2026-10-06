"""Independent event ledger, published duration bars, raster hashes and PCM miter.

Geometry/math follows tb_renderer_geometry_equiv.golden and the reviewed
held_bar_semantics_20261002 contract. It does not use DUT private valid_q.
"""
import base64
from functools import lru_cache
from pathlib import Path


def read_rows(path):
    data = Path(path).read_bytes()
    if Path(path).suffix == ".b64":
        data = base64.b64decode(b"".join(data.split()), validate=True)
    return [line.split() for line in data.decode("utf-8").splitlines()]


def fields(word):
    word = int(word, 16)
    return ((word >> 61) & 7, (word >> 57) & 15, (word >> 53) & 15,
            (word >> 46) & 127, (word >> 36) & 1023)


def midi_event(status, note, value):
    channel = status & 15
    if status >> 4 in (8, 9):
        velocity = (value << 3) | (value >> 4)
        event_type = 0 if status >> 4 == 9 and value else 1
        return (event_type << 61) | (channel << 53) | (note << 46) | (velocity << 36)
    if status >> 4 == 11 and note == 64:
        return (4 << 61) | (channel << 53) | (6 << 18) | (((value << 5) | (value >> 2)) << 6)
    raise ValueError("UNSUPPORTED_STIMULUS")


def pack(slots):
    valid = held = notes = tops = ends = velocities = keys = 0
    for index, slot in enumerate(slots):
        if slot is None:
            continue
        note, source, channel, top, end, velocity, holding = slot
        valid |= 1 << index
        held |= int(holding) << index
        notes |= note << (7 * index)
        tops |= top << (10 * index)
        ends |= end << (10 * index)
        velocities |= velocity << (10 * index)
        if holding:
            keys |= 1 << note
    return valid, held, notes, tops, ends, velocities, keys


def unpack(pub):
    valid, _, notes, tops, ends, velocities, _ = pub
    return tuple(((notes >> (7*i)) & 127, (tops >> (10*i)) & 1023,
                  (ends >> (10*i)) & 1023, (velocities >> (10*i)) & 1023)
                 for i in range(8) if valid & (1 << i))


@lru_cache(maxsize=512)
def row_hash(active, bars, desync, previous_first_pixel=None):
    digest = 0x811C9DC5
    for x in range(800):
        rgb = 0
        if active and x < 640:
            lane = x * 49 // 640
            left, right = lane * 640 // 49, (lane + 1) * 640 // 49
            rgb = 0x18283C if x == left else 0x081020
            if left < x and x + 2 <= right:
                for note, velocity in bars:
                    if note == lane + 36:
                        velocity >>= 2
                        rgb = ((48 + (velocity >> 1)) << 16) | ((112 + (velocity >> 1)) << 8) | (160 + (velocity >> 2))
            if desync:
                rgb = 0xFF2828 if x & 16 else 0x800808
        if x == 0 and previous_first_pixel is not None:
            rgb = previous_first_pixel
        digest = ((digest ^ rgb) * 16777619) & 0xFFFFFFFF
    return digest


def check_capture(path, scenario):
    rows = read_rows(path)
    if not rows or rows[-1][0] != "END":
        raise ValueError("MISSING_END_OR_TIMEOUT")
    sizes = {"U": 3, "A": 5, "R": 3, "P": 10, "D": 4, "V": 3,
             "B": 4, "C": 13, "L": 9, "F": 13, "X": 7, "END": 6}
    if any(not row or len(row) != sizes.get(row[0], -1) for row in rows):
        raise ValueError("MALFORMED_CAPTURE")
    records = lambda kind: [row for row in rows if row[0] == kind]
    overflow = scenario == "overflow"
    end = list(map(int, rows[-1][1:]))
    if end[0] != int(overflow):
        raise ValueError("SCENARIO_ID")
    uart = records("U")
    stimulus = [(0x90, 60, 100), (0x90, 64, 80), (0x90, 67, 90),
                (0x80, 67, 0), (0xB0, 64, 127), (0x80, 60, 0)]
    if overflow:
        stimulus = [(0x90 if n % 2 == 0 else 0x80, 72, 100 if n % 2 == 0 else 0) for n in range(36)]
    raw = [byte for msg in stimulus for byte in msg]
    if [int(row[2], 16) for row in uart] != raw:
        raise ValueError("ZERO_OR_WRONG_UART_EVENTS")
    expected = [midi_event(*msg) for msg in stimulus]
    a, r, v = records("A"), records("R"), records("V")
    if [int(row[2], 16) for row in r] != expected:
        raise ValueError("UART_REFERENCE_EVENT")
    if len(a) != len(r) or any(row[1:3] != other[1:3] for row, other in zip(a, r)):
        raise ValueError("AUDIO_ACCEPT_BACKPRESSURE")
    # At 31250 baud every message is separated by ~0.96ms, far beyond ACK
    # return latency. Capacity is 32 queued + one held mailbox, not 32 total.
    kept, consumed, dropped = [], 0, 0
    ordered = sorted([(float(row[1]), 0, row) for row in a] +
                     [(float(row[1]), 1, row) for row in v])
    for _, kind, row in ordered:
        if kind == 0:
            if len(kept) - consumed >= 33:
                dropped += 1
            else:
                kept.append(row[2])
        else:
            if consumed >= len(kept) or row[2] != kept[consumed]:
                raise ValueError("VIDEO_EVENT_MAPPING_OR_DUPLICATE")
            consumed += 1
    if consumed != len(kept) or not consumed:
        raise ValueError("VIDEO_EVENT_LOSS_OR_ZERO")
    drops = records("D")
    if end[3] != dropped or dropped != (3 if overflow else 0) or len(drops) != dropped:
        raise ValueError("FINITE_QUEUE_DROP_CONTRACT")
    if [int(row[2]) for row in drops] != list(range(1, dropped+1)) or end[4] != (32 if overflow else 3):
        raise ValueError("QUEUE_COUNTER_OR_PEAK")
    blocks = records("B")
    duration = 36000000 if overflow else 4000000
    if len(blocks) != 2 or list(map(int, blocks[0][2:])) != [1, duration] or list(map(int, blocks[1][2:])) != [0, duration] or float(blocks[1][1])-float(blocks[0][1]) != duration:
        raise ValueError("MISSING_BOUNDED_BACKPRESSURE")
    inside = [row for row in a if float(blocks[0][1]) <= float(row[1]) < float(blocks[1][1])]
    if len(inside) != (36 if overflow else 4):
        raise ValueError("BACKPRESSURE_EVENT_COVERAGE")
    pcm = records("P")
    if len(pcm) < 4000:
        raise ValueError("ZERO_OR_SHORT_PCM_COMPARISON")
    for index, row in enumerate(pcm):
        values = list(map(int, row[2:]))
        if values[:2] != [1, 1] or values[2:5] != values[5:8] or values[2] != index + 1:
            raise ValueError("PCM_COEXISTENCE_COMPARE")
    if end[1] != len(pcm) or end[2] != 0 or not any(int(row[5]) for row in pcm):
        raise ValueError("PCM_COMMIT_OR_UNDERRUN")
    pubs, completed, lines = records("F"), records("C"), records("L")
    if len(completed) != 6 or len(pubs) != 7 or len(lines) != 6*525:
        raise ValueError("MISSING_COMPLETE_RASTER_FRAMES")
    if records("X"):
        raise ValueError("RENDER_REFERENCE_MISMATCH")
    slots, vid_index, expected_pubs, first_drop = [None]*8, 0, {}, float(drops[0][1]) if drops else float("inf")
    for index, row in enumerate(pubs):
        frame = int(row[2])
        timestamp = float(row[1])-1  # F is captured after publication NBA.
        if frame != index+1 or int(row[12]) != frame or (index and timestamp-(float(pubs[index-1][1])-1) != 16800000):
            raise ValueError("RASTER_FRAME_TIME_OR_PUBLICATION")
        while vid_index < len(v) and float(v[vid_index][1]) < timestamp:
            ev = fields(v[vid_index][2])
            if ev[0] in (0, 1) and float(v[vid_index][1]) < first_drop:
                for slot in slots:
                    if slot is not None and slot[:3] == [ev[3], ev[1], ev[2]] and slot[6]:
                        slot[6] = False
                if ev[0] == 0 and ev[4]:
                    free = next((n for n, slot in enumerate(slots) if slot is None), None)
                    if free is None:
                        raise ValueError("UNEXPECTED_VISUAL_SLOT_OVERFLOW")
                    slots[free] = [ev[3], ev[1], ev[2], 470, 480, ev[4], True]
            vid_index += 1
        desync = timestamp > first_drop
        if desync:
            slots = [None]*8
        pub = pack(slots)
        actual = tuple(int(value, 16) for value in row[3:10])
        if actual != pub or int(row[10]) != desync or int(row[11]) != 0:
            raise ValueError(f"PUBLISHED_BAR_STATE frame={frame} got={actual} expected={pub}")
        expected_pubs[frame] = (pub, desync)
        for n, slot in enumerate(slots):
            if slot is not None:
                slot[3] = max(0, slot[3]-4)
                if not slot[6]:
                    slot[4] = max(0, slot[4]-4)
                    if not slot[4]:
                        slots[n] = None
    for index, row in enumerate(lines):
        frame, y, pixels, active, hslow = map(int, row[2:7])
        if (frame, y) != (index//525+1, index%525) or pixels != 800 or active != (640 if y < 480 else 0) or hslow != 96 or int(row[8]) != 800:
            raise ValueError("RASTER_LINE_GEOMETRY")
        pub, desync = expected_pubs[frame]
        bars = tuple((note, vel) for note, top, end_y, vel in unpack(pub) if top <= y < end_y)
        # The boundary register samples x=0 before that edge's frame publication.
        # This one pixel uses the previous snapshot, not a shortened frame.
        previous = None
        if y == 0:
            old_desync = expected_pubs.get(frame-1, (None, False))[1]
            previous = 0x800808 if old_desync else 0x18283C
        expected_hash = row_hash(y < 480, bars, desync and y < 18, previous)
        if int(row[7], 16) != expected_hash:
            raise ValueError(f"RASTER_RENDER_HASH frame={frame} line={y}")
    per_frame = []
    for index, row in enumerate(completed):
        vals = list(map(int, row[2:]))
        frame, pixels, active, hslow, vslow, checks, errors, start, stop, under0, under1 = vals
        start_time = float(pubs[index][1])-1
        stop_time = float(row[1])
        count = sum(start_time <= float(p[1]) < stop_time for p in pcm)
        if vals[:7] != [index+1, 420000, 307200, 50400, 1600, 420000, 0] or stop-start != count or under0 or under1 or not 805 <= count <= 807:
            raise ValueError("FRAME_PCM_OR_FULL_SCAN_COVERAGE")
        per_frame.append(count)
    if not overflow:
        p3, p4, p5, p6 = [unpack(expected_pubs[n][0]) for n in (3, 4, 5, 6)]
        if [slot[0] for slot in p3] != [60, 64] or p3[0][1:3] != (470, 480) or p4[0][1:3] != (466, 480) or p5[0][1:3] != (462, 480) or p6[0][1:3] != (458, 476):
            raise ValueError("PRESS_HOLD_RELEASE_NEXT_FRAME")
        if expected_pubs[5][0][1] != 2:
            raise ValueError("CC64_MUST_NOT_VISUALLY_HOLD")
    return {"passed": True, "scenario": scenario, "complete_video_frames": 6,
            "pixel_comparisons": 6*420000, "line_hash_comparisons": len(lines),
            "audio_events": len(a), "video_events": len(v), "visual_drops": dropped,
            "pcm_comparisons": len(pcm), "pcm_in_complete_frames": per_frame,
            "underruns": end[2], "blocked_audio_events": len(inside)}
