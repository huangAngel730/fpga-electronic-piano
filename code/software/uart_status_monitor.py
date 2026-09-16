#!/usr/bin/env python3
"""FPGA电子琴UART状态监视器。

当前T025尚未实现时可以使用 ``--simulate`` 验证解析、显示与CSV记录；
接入真实串口时必须显式给出全部串口参数，避免猜测硬件配置。
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, TextIO


STATUS_PREFIX = "STAT"
STATUS_FIELDS = (
    "active_voice_count",
    "clip_count",
    "event_fifo_level",
    "event_fifo_high_watermark",
    "event_fifo_overflow",
    "audio_underrun",
    "max_processing_cycles",
)
UINT32_MAX = (1 << 32) - 1


class StatusParseError(ValueError):
    """UART状态行格式不符合约定。"""


@dataclass(frozen=True)
class StatusSnapshot:
    """一行UART状态日志解析后的固定字段。"""

    active_voice_count: int
    clip_count: int
    event_fifo_level: int
    event_fifo_high_watermark: int
    event_fifo_overflow: int
    audio_underrun: int
    max_processing_cycles: int

    def format_human(self) -> str:
        """返回便于人在终端中阅读的一行摘要。"""

        return (
            f"voices={self.active_voice_count} "
            f"clip={self.clip_count} "
            f"fifo={self.event_fifo_level}/"
            f"{self.event_fifo_high_watermark} "
            f"overflow={self.event_fifo_overflow} "
            f"underrun={self.audio_underrun} "
            f"max_cycles={self.max_processing_cycles}"
        )


@dataclass
class MonitorStats:
    """本次监视过程的统计结果。"""

    input_line_count: int = 0
    valid_line_count: int = 0
    parse_error_count: int = 0


def _parse_uint32(field_name: str, raw_value: str) -> int:
    """解析十进制或0x开头的十六进制32位无符号整数。"""

    try:
        base = 16 if raw_value.lower().startswith("0x") else 10
        value = int(raw_value, base)
    except ValueError as exc:
        raise StatusParseError(
            f"field {field_name!r} is not an integer: {raw_value!r}"
        ) from exc

    if not 0 <= value <= UINT32_MAX:
        raise StatusParseError(
            f"field {field_name!r} is outside uint32 range: {value}"
        )
    return value


def parse_status_line(line: str) -> StatusSnapshot:
    """把固定 ``STAT key=value ...`` 文本解析为状态快照。

    字段允许改变排列顺序，但不得缺失、重复或出现未知字段。严格检查能尽早
    发现FPGA端协议变更，避免上位机悄悄显示错误数据。
    """

    text = line.strip()
    if not text:
        raise StatusParseError("empty status line")

    tokens = text.split()
    if tokens[0] != STATUS_PREFIX:
        raise StatusParseError(
            f"line must start with {STATUS_PREFIX!r}: {tokens[0]!r}"
        )

    parsed: dict[str, int] = {}
    for token in tokens[1:]:
        field_name, separator, raw_value = token.partition("=")
        if separator != "=" or not field_name or not raw_value:
            raise StatusParseError(f"invalid key=value token: {token!r}")
        if field_name not in STATUS_FIELDS:
            raise StatusParseError(f"unknown status field: {field_name!r}")
        if field_name in parsed:
            raise StatusParseError(f"duplicate status field: {field_name!r}")
        parsed[field_name] = _parse_uint32(field_name, raw_value)

    missing_fields = [name for name in STATUS_FIELDS if name not in parsed]
    if missing_fields:
        raise StatusParseError(
            "missing status fields: " + ", ".join(missing_fields)
        )

    if parsed["event_fifo_level"] > parsed["event_fifo_high_watermark"]:
        raise StatusParseError(
            "event_fifo_level cannot exceed event_fifo_high_watermark"
        )

    return StatusSnapshot(**parsed)


class CsvStatusLogger:
    """把有效状态快照追加保存为CSV。"""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._file: TextIO | None = None
        self._writer: csv.DictWriter[str] | None = None

    def __enter__(self) -> "CsvStatusLogger":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        file_exists = self.path.exists() and self.path.stat().st_size > 0
        self._file = self.path.open("a", encoding="utf-8", newline="")
        self._writer = csv.DictWriter(
            self._file,
            fieldnames=("timestamp_utc", *STATUS_FIELDS),
        )
        if not file_exists:
            self._writer.writeheader()
            self._file.flush()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._file is not None:
            self._file.close()
        self._file = None
        self._writer = None

    def append(
        self,
        snapshot: StatusSnapshot,
        timestamp: datetime | None = None,
    ) -> None:
        """写入一行并立即刷新，程序异常退出时也尽量保留已有记录。"""

        if self._writer is None or self._file is None:
            raise RuntimeError("CsvStatusLogger must be used as a context manager")

        current_time = timestamp or datetime.now(timezone.utc)
        row: dict[str, object] = {
            "timestamp_utc": current_time.isoformat(),
            **asdict(snapshot),
        }
        self._writer.writerow(row)
        self._file.flush()


def simulate_status_lines(interval_seconds: float) -> Iterator[str]:
    """循环生成合法模拟日志，用于T025完成前的软件开发和演示。"""

    sample_lines = (
        "STAT active_voice_count=0 clip_count=0 event_fifo_level=0 "
        "event_fifo_high_watermark=0 event_fifo_overflow=0 "
        "audio_underrun=0 max_processing_cycles=0",
        "STAT active_voice_count=1 clip_count=0 event_fifo_level=1 "
        "event_fifo_high_watermark=1 event_fifo_overflow=0 "
        "audio_underrun=0 max_processing_cycles=620",
        "STAT active_voice_count=4 clip_count=0 event_fifo_level=2 "
        "event_fifo_high_watermark=4 event_fifo_overflow=0 "
        "audio_underrun=0 max_processing_cycles=910",
        "STAT active_voice_count=2 clip_count=1 event_fifo_level=0 "
        "event_fifo_high_watermark=4 event_fifo_overflow=0 "
        "audio_underrun=0 max_processing_cycles=910",
    )

    while True:
        for line in sample_lines:
            yield line
            if interval_seconds > 0:
                time.sleep(interval_seconds)


def _load_pyserial() -> Any:
    """按需导入pyserial，使模拟模式和单元测试不依赖第三方包。"""

    try:
        import serial  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "live serial mode needs pyserial; install it with: "
            "python -m pip install pyserial"
        ) from exc
    return serial


def serial_status_lines(
    port: str,
    baud_rate: int,
    timeout_seconds: float,
    byte_size: int,
    parity: str,
    stop_bits: float,
    stop_requested: Callable[[], bool] | None = None,
) -> Iterator[str]:
    """从真实串口逐行读取ASCII状态文本。"""

    serial_module = _load_pyserial()
    with serial_module.Serial(
        port=port,
        baudrate=baud_rate,
        bytesize=byte_size,
        parity=parity,
        stopbits=stop_bits,
        timeout=timeout_seconds,
    ) as serial_port:
        while stop_requested is None or not stop_requested():
            raw_line = serial_port.readline()
            if raw_line:
                yield raw_line.decode("ascii", errors="replace")


def list_serial_ports(output_stream: TextIO = sys.stdout) -> int:
    """列出pyserial能够发现的串口。"""

    try:
        _load_pyserial()
        from serial.tools import list_ports  # type: ignore[import-not-found]
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports found.", file=output_stream)
        return 0

    for port in ports:
        print(f"{port.device}: {port.description}", file=output_stream)
    return 0


def consume_status_lines(
    lines: Iterable[str],
    *,
    max_valid_lines: int = 0,
    logger: CsvStatusLogger | None = None,
    output_stream: TextIO = sys.stdout,
    error_stream: TextIO = sys.stderr,
) -> MonitorStats:
    """解析并显示输入流；错误行被报告但不会让长期监视立即退出。"""

    stats = MonitorStats()
    for line in lines:
        stats.input_line_count += 1
        try:
            snapshot = parse_status_line(line)
        except StatusParseError as exc:
            stats.parse_error_count += 1
            print(f"PARSE_ERROR: {exc}; raw={line.rstrip()!r}", file=error_stream)
            continue

        stats.valid_line_count += 1
        print(snapshot.format_human(), file=output_stream)
        if logger is not None:
            logger.append(snapshot)

        if max_valid_lines > 0 and stats.valid_line_count >= max_valid_lines:
            break

    return stats


def _positive_int(value: str) -> int:
    parsed = int(value, 10)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value, 10)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _byte_size(value: str) -> int:
    parsed = int(value, 10)
    if parsed not in (5, 6, 7, 8):
        raise argparse.ArgumentTypeError("bytesize must be 5, 6, 7, or 8")
    return parsed


def _parity(value: str) -> str:
    parsed = value.upper()
    if parsed not in ("N", "E", "O", "M", "S"):
        raise argparse.ArgumentTypeError("parity must be N, E, O, M, or S")
    return parsed


def _stop_bits(value: str) -> float:
    parsed = float(value)
    if parsed not in (1.0, 1.5, 2.0):
        raise argparse.ArgumentTypeError("stopbits must be 1, 1.5, or 2")
    return parsed


def build_argument_parser() -> argparse.ArgumentParser:
    """建立命令行参数解析器。"""

    parser = argparse.ArgumentParser(
        description="Monitor fixed-field status lines from the FPGA UART.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--simulate",
        action="store_true",
        help="use built-in mock status lines instead of a serial port",
    )
    mode_group.add_argument(
        "--list-ports",
        action="store_true",
        help="list serial ports and exit",
    )
    parser.add_argument("--port", help="serial port, for example COM5")
    parser.add_argument(
        "--baud",
        type=_positive_int,
        help="baud rate; required in live serial mode",
    )
    parser.add_argument(
        "--bytesize",
        type=_byte_size,
        help="UART data bits; required in live serial mode",
    )
    parser.add_argument(
        "--parity",
        type=_parity,
        help="UART parity N/E/O/M/S; required in live serial mode",
    )
    parser.add_argument(
        "--stopbits",
        type=_stop_bits,
        help="UART stop bits 1/1.5/2; required in live serial mode",
    )
    parser.add_argument(
        "--timeout",
        type=_nonnegative_float,
        default=1.0,
        help="serial read timeout in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--interval",
        type=_nonnegative_float,
        default=0.2,
        help="mock-line interval in seconds (default: 0.2)",
    )
    parser.add_argument(
        "--count",
        type=_nonnegative_int,
        default=0,
        help="stop after this many valid lines; 0 means mode default",
    )
    parser.add_argument(
        "--log",
        type=Path,
        help="optional CSV output path",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """运行命令行状态监视器并返回进程退出码。"""

    parser = build_argument_parser()
    args = parser.parse_args(argv)

    if args.list_ports:
        return list_serial_ports()

    if args.simulate:
        lines = simulate_status_lines(args.interval)
        max_valid_lines = args.count if args.count > 0 else 8
    else:
        if (
            not args.port
            or args.baud is None
            or args.bytesize is None
            or args.parity is None
            or args.stopbits is None
        ):
            parser.error(
                "live serial mode requires --port, --baud, --bytesize, "
                "--parity, and --stopbits; "
                "use --simulate before T025 is available"
            )
        lines = serial_status_lines(
            args.port,
            args.baud,
            args.timeout,
            args.bytesize,
            args.parity,
            args.stopbits,
        )
        max_valid_lines = args.count

    try:
        if args.log is None:
            stats = consume_status_lines(
                lines,
                max_valid_lines=max_valid_lines,
            )
        else:
            with CsvStatusLogger(args.log) as logger:
                stats = consume_status_lines(
                    lines,
                    max_valid_lines=max_valid_lines,
                    logger=logger,
                )
    except (OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Stopped by user.")
        return 0

    print(
        "SUMMARY "
        f"input={stats.input_line_count} "
        f"valid={stats.valid_line_count} "
        f"parse_errors={stats.parse_error_count}"
    )
    return 0 if stats.parse_error_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
