"""T026 UART状态监视器单元测试。"""

from __future__ import annotations

import csv
import io
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SOFTWARE_DIR = Path(__file__).resolve().parents[1]
if str(SOFTWARE_DIR) not in sys.path:
    sys.path.insert(0, str(SOFTWARE_DIR))

from uart_status_monitor import (  # noqa: E402
    CsvStatusLogger,
    StatusParseError,
    consume_status_lines,
    parse_status_line,
    serial_status_lines,
    simulate_status_lines,
)
from uart_status_gui import classify_snapshot  # noqa: E402


VALID_LINE = (
    "STAT active_voice_count=4 clip_count=2 event_fifo_level=3 "
    "event_fifo_high_watermark=7 event_fifo_overflow=1 "
    "audio_underrun=0 max_processing_cycles=1024"
)


class ParseStatusLineTests(unittest.TestCase):
    def test_parses_valid_decimal_line(self) -> None:
        snapshot = parse_status_line(VALID_LINE)

        self.assertEqual(snapshot.active_voice_count, 4)
        self.assertEqual(snapshot.clip_count, 2)
        self.assertEqual(snapshot.event_fifo_level, 3)
        self.assertEqual(snapshot.event_fifo_high_watermark, 7)
        self.assertEqual(snapshot.event_fifo_overflow, 1)
        self.assertEqual(snapshot.audio_underrun, 0)
        self.assertEqual(snapshot.max_processing_cycles, 1024)

    def test_accepts_reordered_fields_and_hex_values(self) -> None:
        line = (
            "STAT max_processing_cycles=0x400 audio_underrun=0 "
            "event_fifo_overflow=0 event_fifo_high_watermark=0x7 "
            "event_fifo_level=0x3 clip_count=0x2 active_voice_count=0x4"
        )

        snapshot = parse_status_line(line)

        self.assertEqual(snapshot.max_processing_cycles, 1024)
        self.assertEqual(snapshot.event_fifo_level, 3)

    def test_rejects_wrong_prefix(self) -> None:
        with self.assertRaisesRegex(StatusParseError, "must start"):
            parse_status_line(VALID_LINE.replace("STAT", "STATE", 1))

    def test_rejects_missing_field(self) -> None:
        line = VALID_LINE.replace(" audio_underrun=0", "")

        with self.assertRaisesRegex(StatusParseError, "missing status fields"):
            parse_status_line(line)

    def test_rejects_duplicate_field(self) -> None:
        line = VALID_LINE + " clip_count=3"

        with self.assertRaisesRegex(StatusParseError, "duplicate status field"):
            parse_status_line(line)

    def test_rejects_unknown_field(self) -> None:
        line = VALID_LINE + " temperature=25"

        with self.assertRaisesRegex(StatusParseError, "unknown status field"):
            parse_status_line(line)

    def test_rejects_noninteger_and_out_of_range_values(self) -> None:
        bad_integer = VALID_LINE.replace("clip_count=2", "clip_count=two")
        too_large = VALID_LINE.replace(
            "clip_count=2",
            "clip_count=4294967296",
        )

        with self.assertRaisesRegex(StatusParseError, "not an integer"):
            parse_status_line(bad_integer)
        with self.assertRaisesRegex(StatusParseError, "outside uint32 range"):
            parse_status_line(too_large)

    def test_rejects_fifo_level_above_high_watermark(self) -> None:
        line = VALID_LINE.replace("event_fifo_level=3", "event_fifo_level=8")

        with self.assertRaisesRegex(StatusParseError, "cannot exceed"):
            parse_status_line(line)


class MonitorFlowTests(unittest.TestCase):
    def test_monitor_reports_bad_line_and_continues(self) -> None:
        output = io.StringIO()
        errors = io.StringIO()
        second_valid = VALID_LINE.replace(
            "active_voice_count=4",
            "active_voice_count=2",
        )

        stats = consume_status_lines(
            (VALID_LINE, "BROKEN", second_valid),
            max_valid_lines=2,
            output_stream=output,
            error_stream=errors,
        )

        self.assertEqual(stats.input_line_count, 3)
        self.assertEqual(stats.valid_line_count, 2)
        self.assertEqual(stats.parse_error_count, 1)
        self.assertEqual(output.getvalue().count("voices="), 2)
        self.assertIn("PARSE_ERROR", errors.getvalue())

    def test_simulator_generates_parseable_lines(self) -> None:
        line_source = simulate_status_lines(0.0)

        snapshots = [parse_status_line(next(line_source)) for _ in range(8)]

        self.assertEqual(len(snapshots), 8)
        self.assertEqual(snapshots[0].active_voice_count, 0)
        self.assertEqual(snapshots[2].active_voice_count, 4)
        self.assertEqual(snapshots[4].active_voice_count, 0)

    def test_csv_logger_writes_header_and_values(self) -> None:
        # 不自动删除该临时目录，遵守“测试过程中只写不删”的工程约束。
        output_dir = Path(tempfile.mkdtemp(prefix="t026_csv_test_"))
        csv_path = output_dir / "status.csv"
        timestamp = datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc)

        with CsvStatusLogger(csv_path) as logger:
            logger.append(parse_status_line(VALID_LINE), timestamp=timestamp)

        with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
            rows = list(csv.DictReader(csv_file))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["timestamp_utc"], timestamp.isoformat())
        self.assertEqual(rows[0]["active_voice_count"], "4")
        self.assertEqual(rows[0]["max_processing_cycles"], "1024")


class SerialReaderTests(unittest.TestCase):
    def test_serial_reader_honors_stop_callback(self) -> None:
        class FakeSerialPort:
            def __enter__(self) -> "FakeSerialPort":
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def readline(self) -> bytes:
                return (VALID_LINE + "\n").encode("ascii")

        fake_serial = SimpleNamespace(Serial=lambda **_kwargs: FakeSerialPort())
        stop_checks = iter((False, True))

        with patch("uart_status_monitor._load_pyserial", return_value=fake_serial):
            lines = serial_status_lines(
                "COM_TEST",
                1,
                0.0,
                8,
                "N",
                1.0,
                stop_requested=lambda: next(stop_checks),
            )
            self.assertEqual(next(lines).strip(), VALID_LINE)
            with self.assertRaises(StopIteration):
                next(lines)


class GuiHelperTests(unittest.TestCase):
    def test_gui_marks_zero_error_counters_as_valid(self) -> None:
        snapshot = parse_status_line(
            VALID_LINE.replace("clip_count=2", "clip_count=0").replace(
                "event_fifo_overflow=1",
                "event_fifo_overflow=0",
            )
        )

        title, detail, _color = classify_snapshot(snapshot)

        self.assertEqual(title, "数据有效")
        self.assertIn("未见异常计数", detail)

    def test_gui_prioritizes_overflow_warning(self) -> None:
        snapshot = parse_status_line(VALID_LINE)

        title, detail, _color = classify_snapshot(snapshot)

        self.assertEqual(title, "需要检查")
        self.assertIn("溢出或欠载", detail)


if __name__ == "__main__":
    unittest.main()
