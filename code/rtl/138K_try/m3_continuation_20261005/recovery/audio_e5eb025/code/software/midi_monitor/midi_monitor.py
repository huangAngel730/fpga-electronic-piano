#!/usr/bin/env python3
"""MIDI message formatting, statistics, simulation, and CSV logging.

This module deliberately has no GUI and no mandatory third-party dependency.
The desktop UI imports it, while unit tests use the small SimulatedMessage
class below. Real USB MIDI input is provided by mido + python-rtmidi in the UI.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
CONTROLLER_NAMES = {
    1: "Modulation (CC1)",
    7: "Channel Volume (CC7)",
    10: "Pan (CC10)",
    11: "Expression (CC11)",
    64: "Sustain Pedal (CC64)",
    120: "All Sound Off (CC120)",
    121: "Reset Controllers (CC121)",
    123: "All Notes Off (CC123)",
}


def midi_note_name(note: int) -> str:
    """Return the conventional MIDI note name, where note 60 is C4."""

    if not 0 <= note <= 127:
        raise ValueError("MIDI note must be in the range 0..127")
    return f"{NOTE_NAMES[note % 12]}{note // 12 - 1}"


def _message_bytes(message: Any) -> list[int]:
    bytes_method = getattr(message, "bytes", None)
    if callable(bytes_method):
        return [int(value) & 0xFF for value in bytes_method()]
    raw_bytes = getattr(message, "raw_bytes", ())
    return [int(value) & 0xFF for value in raw_bytes]


def _channel_number(message: Any) -> int | None:
    channel = getattr(message, "channel", None)
    return None if channel is None else int(channel) + 1


@dataclass(frozen=True)
class MidiEvent:
    """A presentation-friendly snapshot of one received MIDI message."""

    timestamp: str
    event_type: str
    channel: int | None
    note: int | None
    note_name: str
    velocity: int | None
    controller: int | None
    controller_name: str
    value: int | None
    pitch: int | None
    raw_hex: str
    description: str

    @classmethod
    def csv_fieldnames(cls) -> list[str]:
        return [field.name for field in fields(cls)]

    def csv_row(self) -> dict[str, object]:
        return {field.name: getattr(self, field.name) for field in fields(self)}


def describe_midi_message(message: Any, timestamp: datetime | None = None) -> MidiEvent:
    """Convert a mido-compatible message into the project's display format."""

    current_time = timestamp or datetime.now()
    time_text = current_time.isoformat(timespec="milliseconds")
    message_type = str(getattr(message, "type", "unknown"))
    channel = _channel_number(message)
    note: int | None = None
    note_name = ""
    velocity: int | None = None
    controller: int | None = None
    controller_name = ""
    value: int | None = None
    pitch: int | None = None
    description = message_type

    if message_type in ("note_on", "note_off"):
        note = int(getattr(message, "note", 0))
        velocity = int(getattr(message, "velocity", 0))
        note_name = midi_note_name(note)
        normalized_type = "note_off" if message_type == "note_on" and velocity == 0 else message_type
        if normalized_type == "note_on":
            description = f"{note_name} pressed, velocity {velocity}"
        elif message_type == "note_on":
            description = f"{note_name} released (Note On velocity 0)"
        else:
            description = f"{note_name} released, velocity {velocity}"
        message_type = normalized_type
    elif message_type == "control_change":
        controller = int(getattr(message, "control", 0))
        value = int(getattr(message, "value", 0))
        controller_name = CONTROLLER_NAMES.get(controller, f"CC{controller}")
        if controller == 64:
            state = "ON" if value >= 64 else "OFF"
            description = f"Sustain pedal {state}, value {value}"
        else:
            description = f"{controller_name}, value {value}"
    elif message_type == "pitchwheel":
        pitch = int(getattr(message, "pitch", 0))
        description = f"Pitch Bend {pitch:+d} (center 0)"
    elif message_type == "polytouch":
        note = int(getattr(message, "note", 0))
        note_name = midi_note_name(note)
        value = int(getattr(message, "value", 0))
        description = f"Poly pressure {note_name}, value {value}"
    elif message_type == "aftertouch":
        value = int(getattr(message, "value", 0))
        description = f"Channel pressure, value {value}"
    elif message_type == "program_change":
        value = int(getattr(message, "program", 0))
        description = f"Program Change {value}"
    elif message_type == "sysex":
        description = f"System Exclusive, {len(getattr(message, 'data', ())) } data bytes"
    elif message_type == "clock":
        description = "MIDI Clock"
    elif message_type == "active_sensing":
        description = "Active Sensing"

    raw_hex = " ".join(f"{byte:02X}" for byte in _message_bytes(message))
    return MidiEvent(
        timestamp=time_text,
        event_type=message_type,
        channel=channel,
        note=note,
        note_name=note_name,
        velocity=velocity,
        controller=controller,
        controller_name=controller_name,
        value=value,
        pitch=pitch,
        raw_hex=raw_hex,
        description=description,
    )


@dataclass
class MidiStatistics:
    """Session counters used by the GUI and CSV evidence summary."""

    message_count: int = 0
    note_on_count: int = 0
    note_off_count: int = 0
    min_velocity: int | None = None
    max_velocity: int | None = None
    sustain_value: int = 0
    modulation_value: int = 0
    pitch_value: int = 0

    def __post_init__(self) -> None:
        self.active_notes: set[tuple[int, int]] = set()

    def update(self, event: MidiEvent) -> None:
        self.message_count += 1
        if event.event_type == "note_on" and event.note is not None:
            self.note_on_count += 1
            self.active_notes.add((event.channel or 0, event.note))
            if event.velocity is not None:
                if self.min_velocity is None or event.velocity < self.min_velocity:
                    self.min_velocity = event.velocity
                if self.max_velocity is None or event.velocity > self.max_velocity:
                    self.max_velocity = event.velocity
        elif event.event_type == "note_off" and event.note is not None:
            self.note_off_count += 1
            self.active_notes.discard((event.channel or 0, event.note))
        elif event.event_type == "control_change":
            if event.controller == 1 and event.value is not None:
                self.modulation_value = event.value
            elif event.controller == 64 and event.value is not None:
                self.sustain_value = event.value
        elif event.event_type == "pitchwheel" and event.pitch is not None:
            self.pitch_value = event.pitch

    @property
    def active_note_count(self) -> int:
        return len(self.active_notes)

    @property
    def velocity_range_text(self) -> str:
        if self.min_velocity is None or self.max_velocity is None:
            return "—"
        return f"{self.min_velocity}–{self.max_velocity}"


class CsvMidiLogger:
    """Append UTF-8 CSV rows and write the header only for a new file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not self.path.exists() or self.path.stat().st_size == 0
        self._handle = self.path.open("a", encoding="utf-8-sig", newline="")
        self._writer = csv.DictWriter(self._handle, fieldnames=MidiEvent.csv_fieldnames())
        if is_new:
            self._writer.writeheader()
            self._handle.flush()

    def write(self, event: MidiEvent) -> None:
        self._writer.writerow(event.csv_row())
        self._handle.flush()

    def close(self) -> None:
        if not self._handle.closed:
            self._handle.close()


@dataclass(frozen=True)
class SimulatedMessage:
    """Small mido-compatible object used by simulation and unit tests."""

    type: str
    channel: int | None = None
    note: int = 0
    velocity: int = 0
    control: int = 0
    value: int = 0
    pitch: int = 0
    program: int = 0
    raw_bytes: tuple[int, ...] = ()

    def bytes(self) -> Iterable[int]:
        return self.raw_bytes


def simulation_messages() -> tuple[SimulatedMessage, ...]:
    """Return a repeatable tour of the fields that T036 must observe."""

    return (
        SimulatedMessage("note_on", 0, note=60, velocity=24, raw_bytes=(0x90, 0x3C, 0x18)),
        SimulatedMessage("note_off", 0, note=60, velocity=40, raw_bytes=(0x80, 0x3C, 0x28)),
        SimulatedMessage("note_on", 0, note=64, velocity=72, raw_bytes=(0x90, 0x40, 0x48)),
        SimulatedMessage("note_on", 0, note=67, velocity=114, raw_bytes=(0x90, 0x43, 0x72)),
        SimulatedMessage("control_change", 0, control=1, value=86, raw_bytes=(0xB0, 0x01, 0x56)),
        SimulatedMessage("pitchwheel", 0, pitch=4096, raw_bytes=(0xE0, 0x00, 0x60)),
        SimulatedMessage("control_change", 0, control=64, value=127, raw_bytes=(0xB0, 0x40, 0x7F)),
        SimulatedMessage("note_off", 0, note=64, velocity=0, raw_bytes=(0x80, 0x40, 0x00)),
        SimulatedMessage("note_off", 0, note=67, velocity=0, raw_bytes=(0x80, 0x43, 0x00)),
        SimulatedMessage("control_change", 0, control=64, value=0, raw_bytes=(0xB0, 0x40, 0x00)),
        SimulatedMessage("pitchwheel", 0, pitch=0, raw_bytes=(0xE0, 0x00, 0x40)),
        SimulatedMessage("control_change", 0, control=1, value=0, raw_bytes=(0xB0, 0x01, 0x00)),
    )
