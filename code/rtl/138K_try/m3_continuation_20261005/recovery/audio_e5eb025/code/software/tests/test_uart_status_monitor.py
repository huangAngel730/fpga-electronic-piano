"""T026 UART状态监视器单元测试。"""

from __future__ import annotations

import csv
import io
import queue
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


UART_TEST_DIR = Path(__file__).resolve().parents[1] / "uart_test"
if str(UART_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(UART_TEST_DIR))

from uart_status_monitor import (  # noqa: E402
    CsvStatusLogger,
    StatusParseError,
    consume_status_lines,
    list_serial_ports,
    main,
    parse_status_line,
    serial_status_lines,
    simulate_status_lines,
    validate_serial_settings,
)
from uart_status_gui import StatusMonitorApp, classify_snapshot  # noqa: E402


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

    def test_csv_appends_multiple_rows_after_reopening(self) -> None:
        output_dir = Path(tempfile.mkdtemp(prefix="t026_csv_append_"))
        csv_path = output_dir / "status.csv"
        snapshot = parse_status_line(VALID_LINE)
        for batch_size in (3, 2):
            with CsvStatusLogger(csv_path) as logger:
                for _ in range(batch_size):
                    logger.append(snapshot)
        with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
            rows = list(csv.reader(csv_file))
        self.assertEqual(len(rows), 6)  # One header plus five data rows.
        self.assertEqual(rows[0].count("active_voice_count"), 1)
        self.assertEqual([row[1] for row in rows[1:]], ["4"] * 5)

    def test_cli_requires_all_live_settings(self) -> None:
        with patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as caught:
                main(["--port", "COM7", "--baud", "9600"])
        self.assertEqual(caught.exception.code, 2)

    def test_cli_rejects_invalid_settings_with_exit_two(self) -> None:
        valid = ["--port", "COM7", "--baud", "9600", "--bytesize", "8",
                 "--parity", "N", "--stopbits", "1"]
        for switch, wrong in (("--baud", "0"), ("--bytesize", "9"),
                              ("--parity", "X"), ("--stopbits", "3"),
                              ("--timeout", "nan")):
            args = valid.copy()
            if switch in args:
                args[args.index(switch) + 1] = wrong
            else:
                args.extend((switch, wrong))
            with self.subTest(switch=switch), patch("sys.stderr", new_callable=io.StringIO):
                with self.assertRaises(SystemExit) as caught:
                    main(args)
                self.assertEqual(caught.exception.code, 2)

    def test_cli_open_failure_returns_two(self) -> None:
        with patch("uart_status_monitor._load_pyserial", return_value=SimpleNamespace(
            Serial=lambda **_kwargs: (_ for _ in ()).throw(OSError("port busy"))
        )), patch("sys.stderr", new_callable=io.StringIO) as errors:
            result = main(["--port", "COM7", "--baud", "9600", "--bytesize", "8",
                           "--parity", "N", "--stopbits", "1", "--count", "1"])
        self.assertEqual(result, 2)
        self.assertIn("port busy", errors.getvalue())

    def test_list_ports_present_empty_and_missing_dependency(self) -> None:
        output = io.StringIO()
        with patch("uart_status_monitor.discover_serial_ports",
                   return_value=[("COM7", "USB UART")]):
            self.assertEqual(list_serial_ports(output), 0)
        self.assertIn("COM7: USB UART", output.getvalue())
        output = io.StringIO()
        with patch("uart_status_monitor.discover_serial_ports", return_value=[]):
            self.assertEqual(list_serial_ports(output), 0)
        self.assertIn("No serial ports", output.getvalue())
        with patch("uart_status_monitor.discover_serial_ports",
                   side_effect=RuntimeError("pyserial missing")), \
             patch("sys.stderr", new_callable=io.StringIO) as errors:
            self.assertEqual(list_serial_ports(io.StringIO()), 2)
        self.assertIn("pyserial missing", errors.getvalue())


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

    def test_reader_interrupt_propagates_to_cli_for_clean_stop(self) -> None:
        class InterruptedPort:
            def __enter__(self) -> "InterruptedPort":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def readline(self) -> bytes:
                raise KeyboardInterrupt()

        with patch("uart_status_monitor._load_pyserial", return_value=SimpleNamespace(
            Serial=lambda **_kwargs: InterruptedPort()
        )), patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(main(["--port", "COM7", "--baud", "9600",
                                   "--bytesize", "8", "--parity", "N",
                                   "--stopbits", "1"]), 0)

    def test_cli_disconnect_while_reading_returns_two(self) -> None:
        class DisconnectedPort:
            def __enter__(self) -> "DisconnectedPort":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def readline(self) -> bytes:
                raise OSError("connection lost")

        with patch("uart_status_monitor._load_pyserial", return_value=SimpleNamespace(
            Serial=lambda **_kwargs: DisconnectedPort()
        )), patch("sys.stderr", new_callable=io.StringIO) as errors:
            result = main(["--port", "COM7", "--baud", "9600",
                           "--bytesize", "8", "--parity", "N", "--stopbits", "1"])
        self.assertEqual(result, 2)
        self.assertIn("connection lost", errors.getvalue())

    def test_non_ascii_line_is_reported_and_next_line_read(self) -> None:
        class MixedPort:
            def __init__(self) -> None:
                self.lines = iter((b"\xff\n", (VALID_LINE + "\n").encode("ascii")))

            def __enter__(self) -> "MixedPort":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def readline(self) -> bytes:
                return next(self.lines)

        with patch("uart_status_monitor._load_pyserial", return_value=SimpleNamespace(
            Serial=lambda **_kwargs: MixedPort()
        )):
            lines = serial_status_lines("COM7", 9600, 0.1, 8, "N", 1.0)
            output, errors = io.StringIO(), io.StringIO()
            stats = consume_status_lines(lines, max_valid_lines=1,
                                         output_stream=output, error_stream=errors)
        self.assertEqual((stats.parse_error_count, stats.valid_line_count), (1, 1))
        self.assertIn("PARSE_ERROR", errors.getvalue())

    def test_cli_non_ascii_error_sets_exit_one(self) -> None:
        class NonAsciiPort:
            def __init__(self) -> None:
                self.lines = iter((b"\xff\n", (VALID_LINE + "\n").encode("ascii")))

            def __enter__(self) -> "NonAsciiPort":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def readline(self) -> bytes:
                return next(self.lines)

        with patch("uart_status_monitor._load_pyserial", return_value=SimpleNamespace(
            Serial=lambda **_kwargs: NonAsciiPort()
        )), patch("sys.stdout", new_callable=io.StringIO), \
             patch("sys.stderr", new_callable=io.StringIO):
            result = main(["--port", "COM7", "--baud", "9600", "--bytesize", "8",
                           "--parity", "N", "--stopbits", "1", "--count", "1"])
        self.assertEqual(result, 1)


class FakeVar:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class GuiConnectionTests(unittest.TestCase):
    def make_app(self) -> StatusMonitorApp:
        # Test GUI control logic without needing a monitor or Tk mainloop.
        app = object.__new__(StatusMonitorApp)
        app.worker = None
        app.stop_event = threading.Event()
        app.message_queue = queue.Queue()
        app.port_lookup = {}
        app.port_var = FakeVar("COM7")
        app.baud_var = FakeVar("9600")
        app.bytesize_var = FakeVar("8")
        app.parity_var = FakeVar("N")
        app.stopbits_var = FakeVar("1")
        app.connection_var = FakeVar()
        app.health_title_var = FakeVar()
        app.health_detail_var = FakeVar()
        app.health_title_label = SimpleNamespace(configure=lambda **_kwargs: None)
        app.counter_var = FakeVar()
        app.error_count = 0
        app.port_combo = SimpleNamespace(combo=SimpleNamespace(
            configure=lambda **kwargs: setattr(app, "port_values", kwargs["values"])))
        return app

    def test_gui_port_enumeration_and_empty_list(self) -> None:
        app = self.make_app()
        with patch("uart_status_gui.discover_serial_ports",
                   return_value=[("COM7", "USB UART")]):
            app.refresh_ports()
        self.assertEqual(app.port_lookup["COM7 · USB UART"], "COM7")
        self.assertEqual(app.port_var.get(), "COM7 · USB UART")
        with patch("uart_status_gui.discover_serial_ports", return_value=[]):
            app.refresh_ports(show_message=False)
        self.assertEqual(app.port_var.get(), "")
        self.assertEqual(app.connection_var.get(), "未发现串口")

    def test_gui_port_enumeration_failure_shows_error(self) -> None:
        app = self.make_app()
        with patch("uart_status_gui.discover_serial_ports",
                   side_effect=RuntimeError("pyserial missing")), \
             patch("uart_status_gui.messagebox.showerror") as showerror:
            app.refresh_ports()
        showerror.assert_called_once()
        self.assertIn("pyserial missing", showerror.call_args.args[1])

    def test_gui_rejects_invalid_settings_before_starting_worker(self) -> None:
        app = self.make_app()
        for variable, wrong in ((app.baud_var, "0"), (app.bytesize_var, "9"),
                                (app.parity_var, "X"), (app.stopbits_var, "3")):
            old = variable.get()
            variable.set(wrong)
            with self.subTest(wrong=wrong), patch("uart_status_gui.messagebox.showerror") as error:
                app.start_serial()
                error.assert_called_once()
                self.assertIsNone(app.worker)
            variable.set(old)

    def test_gui_connection_failure_can_retry(self) -> None:
        app = self.make_app()
        with patch("uart_status_gui.serial_status_lines", side_effect=OSError("disconnected")):
            app._serial_worker("COM7", 9600, 8, "N", 1.0)
        kind, message = app.message_queue.get_nowait()
        self.assertEqual((kind, message), ("fatal", "disconnected"))
        self.assertEqual(app.message_queue.get_nowait()[0], "stopped")
        app._add_log = lambda *_args: None
        app._update_counter = lambda: None
        app._handle_fatal(message)
        self.assertEqual(app.connection_var.get(), "连接失败")
        with patch("uart_status_gui.threading.Thread") as thread_class:
            app.start_serial()
            thread_class.return_value.start.assert_called_once()
        self.assertEqual(app.connection_var.get(), "正在连接 COM7")

    def test_gui_uses_same_validators_as_cli(self) -> None:
        self.assertEqual(validate_serial_settings(" COM7 ", "9600", "5", "m", "1.5"),
                         ("COM7", 9600, 5, "M", 1.5))


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
