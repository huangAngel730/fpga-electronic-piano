from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


SOFTWARE_DIR = Path(__file__).resolve().parents[1]
if str(SOFTWARE_DIR) not in sys.path:
    sys.path.insert(0, str(SOFTWARE_DIR))

from midi_monitor import (
    CsvMidiLogger,
    MidiStatistics,
    SimulatedMessage,
    describe_midi_message,
    midi_note_name,
    simulation_messages,
)


FIXED_TIME = datetime(2026, 9, 25, 12, 34, 56, 789000)


class MidiMonitorTests(unittest.TestCase):
    def test_note_names_cover_boundaries_and_middle_c(self) -> None:
        self.assertEqual(midi_note_name(0), "C-1")
        self.assertEqual(midi_note_name(60), "C4")
        self.assertEqual(midi_note_name(69), "A4")
        self.assertEqual(midi_note_name(127), "G9")

    def test_note_name_rejects_out_of_range_values(self) -> None:
        with self.assertRaises(ValueError):
            midi_note_name(-1)
        with self.assertRaises(ValueError):
            midi_note_name(128)

    def test_note_on_contains_channel_note_velocity_and_raw_bytes(self) -> None:
        message = SimulatedMessage(
            "note_on", channel=0, note=60, velocity=100, raw_bytes=(0x90, 0x3C, 0x64)
        )
        event = describe_midi_message(message, FIXED_TIME)
        self.assertEqual(event.timestamp, "2026-09-25T12:34:56.789")
        self.assertEqual(event.event_type, "note_on")
        self.assertEqual(event.channel, 1)
        self.assertEqual(event.note, 60)
        self.assertEqual(event.note_name, "C4")
        self.assertEqual(event.velocity, 100)
        self.assertEqual(event.raw_hex, "90 3C 64")

    def test_note_on_velocity_zero_is_displayed_as_note_off(self) -> None:
        message = SimulatedMessage(
            "note_on", channel=2, note=64, velocity=0, raw_bytes=(0x92, 0x40, 0x00)
        )
        event = describe_midi_message(message, FIXED_TIME)
        self.assertEqual(event.event_type, "note_off")
        self.assertEqual(event.channel, 3)
        self.assertIn("velocity 0", event.description)

    def test_modulation_and_sustain_are_named(self) -> None:
        modulation = describe_midi_message(
            SimulatedMessage(
                "control_change", channel=0, control=1, value=81, raw_bytes=(0xB0, 0x01, 0x51)
            ),
            FIXED_TIME,
        )
        sustain = describe_midi_message(
            SimulatedMessage(
                "control_change", channel=0, control=64, value=127, raw_bytes=(0xB0, 0x40, 0x7F)
            ),
            FIXED_TIME,
        )
        self.assertEqual(modulation.controller_name, "Modulation (CC1)")
        self.assertEqual(sustain.controller_name, "Sustain Pedal (CC64)")
        self.assertIn("ON", sustain.description)

    def test_pitch_bend_keeps_signed_value(self) -> None:
        event = describe_midi_message(
            SimulatedMessage("pitchwheel", channel=0, pitch=-4096, raw_bytes=(0xE0, 0x00, 0x20)),
            FIXED_TIME,
        )
        self.assertEqual(event.pitch, -4096)
        self.assertIn("-4096", event.description)

    def test_statistics_tracks_active_notes_and_velocity_range(self) -> None:
        stats = MidiStatistics()
        for message in (
            SimulatedMessage("note_on", channel=0, note=60, velocity=20, raw_bytes=(0x90, 60, 20)),
            SimulatedMessage("note_on", channel=0, note=64, velocity=110, raw_bytes=(0x90, 64, 110)),
            SimulatedMessage("note_off", channel=0, note=60, velocity=0, raw_bytes=(0x80, 60, 0)),
        ):
            stats.update(describe_midi_message(message, FIXED_TIME))
        self.assertEqual(stats.message_count, 3)
        self.assertEqual(stats.note_on_count, 2)
        self.assertEqual(stats.note_off_count, 1)
        self.assertEqual(stats.active_note_count, 1)
        self.assertEqual(stats.velocity_range_text, "20–110")

    def test_statistics_tracks_mod_sustain_and_pitch(self) -> None:
        stats = MidiStatistics()
        for message in (
            SimulatedMessage("control_change", channel=0, control=1, value=35, raw_bytes=(0xB0, 1, 35)),
            SimulatedMessage("control_change", channel=0, control=64, value=127, raw_bytes=(0xB0, 64, 127)),
            SimulatedMessage("pitchwheel", channel=0, pitch=2048, raw_bytes=(0xE0, 0, 80)),
        ):
            stats.update(describe_midi_message(message, FIXED_TIME))
        self.assertEqual(stats.modulation_value, 35)
        self.assertEqual(stats.sustain_value, 127)
        self.assertEqual(stats.pitch_value, 2048)

    def test_simulation_covers_required_t036_message_types(self) -> None:
        types = {message.type for message in simulation_messages()}
        self.assertTrue({"note_on", "note_off", "control_change", "pitchwheel"}.issubset(types))
        controls = {message.control for message in simulation_messages() if message.type == "control_change"}
        self.assertIn(1, controls)
        self.assertIn(64, controls)

    def test_csv_logger_writes_header_and_appends_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "capture.csv"
            first_event = describe_midi_message(simulation_messages()[0], FIXED_TIME)
            second_event = describe_midi_message(simulation_messages()[1], FIXED_TIME)
            logger = CsvMidiLogger(path)
            logger.write(first_event)
            logger.close()
            logger = CsvMidiLogger(path)
            logger.write(second_event)
            logger.close()
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["raw_hex"], "90 3C 18")
            self.assertEqual(rows[1]["event_type"], "note_off")


if __name__ == "__main__":
    unittest.main()
