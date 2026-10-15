"""Synthetic SMF byte fixtures, independent of the importer under test.

These are development inputs, not user-authored or licensed music recordings.
"""
from __future__ import annotations

import struct


def vlq(value):
    if not 0 <= value <= 0x0FFFFFFF:
        raise ValueError("fixture VLQ range")
    result = [value & 127]
    while value > 127:
        value >>= 7
        result.insert(0, 128 | (value & 127))
    return bytes(result)


def event(delta, payload):
    return vlq(delta) + bytes(payload)


def meta(delta, kind, payload=b""):
    return event(delta, b"\xff" + bytes([kind]) + vlq(len(payload)) + payload)


def tempo(delta, microseconds):
    return meta(delta, 0x51, microseconds.to_bytes(3, "big"))


def note_on(delta=0, note=60, velocity=100, channel=0):
    return event(delta, [0x90 | channel, note, velocity])


def note_off(delta=480, note=60, velocity=0, channel=0):
    return event(delta, [0x80 | channel, note, velocity])


def end(delta=0):
    return meta(delta, 0x2F)


def smf(*tracks, division=480, midi_format=None):
    if midi_format is None:
        midi_format = int(len(tracks) > 1)
    header = b"MThd" + struct.pack(">IHHH", 6, midi_format, len(tracks), division)
    return header + b"".join(
        b"MTrk" + struct.pack(">I", len(track)) + track for track in tracks
    )


def basic(*, division=480, channel=0, note=60, release_velocity=0):
    return smf(note_on(channel=channel, note=note)
               + note_off(division, channel=channel, note=note,
                          velocity=release_velocity) + end(), division=division)


def capacity(note_events=512):
    body = bytearray()
    for index in range(note_events):
        body.extend(note_on(0, note=60) if index % 2 == 0
                    else note_off(1, note=60))
    body.extend(end())
    return smf(bytes(body))


def expected_event(tick, kind, channel=0, note=60, velocity=0):
    return {"tick": tick, "type": kind, "channel": channel,
            "note": note, "velocity": velocity}


def development_cases():
    """Small deterministic CLI inputs and independently specified event ticks."""
    return {
        "type0_basic": basic(),
        "type1_tempo": smf(
            tempo(0, 500000) + tempo(480, 1000000) + end(480),
            note_on() + note_off(960) + end()),
        "running_status": smf(note_on() + event(480, [60, 0]) + end()),
        "capacity_512": capacity(),
    }
