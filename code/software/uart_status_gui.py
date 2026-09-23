#!/usr/bin/env python3
"""T026 FPGA电子琴UART状态监视器图形界面。"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from collections import deque
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from uart_status_monitor import (
    CsvStatusLogger,
    StatusParseError,
    StatusSnapshot,
    discover_serial_ports,
    parse_status_line,
    serial_status_lines,
    simulate_status_lines,
    validate_serial_settings,
)


APP_TITLE = "FPGA 电子琴 · 串口调试助手"
FIFO_DEPTH = 32
POLL_INTERVAL_MS = 80
MAX_LOG_ROWS = 200

COLORS = {
    "background": "#08111F",
    "panel": "#111D2E",
    "panel_alt": "#16243A",
    "border": "#233653",
    "text": "#F4F7FB",
    "muted": "#8EA2BE",
    "cyan": "#35D4FF",
    "blue": "#5B8CFF",
    "green": "#3DDC97",
    "yellow": "#FFCC66",
    "red": "#FF647C",
}


def classify_snapshot(snapshot: StatusSnapshot) -> tuple[str, str, str]:
    """根据计数器给出保守提示，不代替硬件验收结论。"""

    if snapshot.event_fifo_overflow > 0 or snapshot.audio_underrun > 0:
        return "需要检查", "检测到溢出或欠载计数", COLORS["red"]
    if snapshot.clip_count > 0:
        return "注意", "检测到音频削波计数", COLORS["yellow"]
    return "数据有效", "当前状态行格式正确，未见异常计数", COLORS["green"]


class StatusCard(tk.Frame):
    """显示一个状态字段的卡片。"""

    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        unit: str = "",
        accent: str = COLORS["cyan"],
    ) -> None:
        super().__init__(
            parent,
            bg=COLORS["panel"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            padx=18,
            pady=14,
        )
        self.value = tk.StringVar(value="—")

        tk.Label(
            self,
            text=title,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 10),
            anchor="w",
        ).pack(fill="x")

        value_row = tk.Frame(self, bg=COLORS["panel"])
        value_row.pack(fill="x", pady=(8, 0))
        tk.Label(
            value_row,
            textvariable=self.value,
            bg=COLORS["panel"],
            fg=accent,
            font=("Segoe UI Semibold", 23),
            anchor="w",
        ).pack(side="left")
        if unit:
            tk.Label(
                value_row,
                text=unit,
                bg=COLORS["panel"],
                fg=COLORS["muted"],
                font=("Microsoft YaHei UI", 9),
                padx=6,
            ).pack(side="left", anchor="s", pady=(0, 4))

    def set_value(self, value: int | str) -> None:
        self.value.set(str(value))


class TrendChart(tk.Canvas):
    """绘制复音数和FIFO水位的轻量趋势图。"""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(
            parent,
            bg=COLORS["panel"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            height=180,
        )
        self.voice_history: deque[int] = deque(maxlen=80)
        self.fifo_history: deque[int] = deque(maxlen=80)
        self.bind("<Configure>", lambda _event: self.redraw())

    def append(self, snapshot: StatusSnapshot) -> None:
        self.voice_history.append(snapshot.active_voice_count)
        self.fifo_history.append(snapshot.event_fifo_level)
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 200)
        height = max(self.winfo_height(), 120)
        left, top, right, bottom = 46, 28, width - 20, height - 30

        self.create_text(
            18,
            13,
            text="实时趋势",
            anchor="w",
            fill=COLORS["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        self.create_text(
            width - 230,
            13,
            text="复音数",
            anchor="w",
            fill=COLORS["cyan"],
            font=("Microsoft YaHei UI", 9),
        )
        self.create_text(
            width - 140,
            13,
            text="FIFO 水位",
            anchor="w",
            fill=COLORS["blue"],
            font=("Microsoft YaHei UI", 9),
        )

        for index in range(5):
            y = top + (bottom - top) * index / 4
            self.create_line(left, y, right, y, fill=COLORS["border"])

        self.create_text(
            left - 8,
            top,
            text=str(FIFO_DEPTH),
            anchor="e",
            fill=COLORS["muted"],
            font=("Segoe UI", 8),
        )
        self.create_text(
            left - 8,
            bottom,
            text="0",
            anchor="e",
            fill=COLORS["muted"],
            font=("Segoe UI", 8),
        )

        self._draw_series(
            list(self.voice_history),
            left,
            top,
            right,
            bottom,
            max(4, max(self.voice_history, default=4)),
            COLORS["cyan"],
        )
        self._draw_series(
            list(self.fifo_history),
            left,
            top,
            right,
            bottom,
            FIFO_DEPTH,
            COLORS["blue"],
        )

    def _draw_series(
        self,
        values: list[int],
        left: float,
        top: float,
        right: float,
        bottom: float,
        maximum: int,
        color: str,
    ) -> None:
        if len(values) < 2:
            return
        points: list[float] = []
        for index, value in enumerate(values):
            x = left + (right - left) * index / (len(values) - 1)
            limited_value = max(0, min(value, maximum))
            y = bottom - (bottom - top) * limited_value / maximum
            points.extend((x, y))
        self.create_line(*points, fill=color, width=2, smooth=True)


class StatusMonitorApp:
    """T026桌面状态监视器。"""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1280x820")
        self.root.minsize(1050, 700)
        self.root.configure(bg=COLORS["background"])
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.message_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.csv_logger: CsvStatusLogger | None = None
        self.port_lookup: dict[str, str] = {}
        self.valid_count = 0
        self.error_count = 0

        self.port_var = tk.StringVar()
        self.baud_var = tk.StringVar()
        self.bytesize_var = tk.StringVar()
        self.parity_var = tk.StringVar()
        self.stopbits_var = tk.StringVar()
        self.connection_var = tk.StringVar(value="未连接")
        self.health_title_var = tk.StringVar(value="等待数据")
        self.health_detail_var = tk.StringVar(value="可以先启动模拟模式检查界面")
        self.counter_var = tk.StringVar(value="有效 0 · 错误 0")
        self.csv_var = tk.StringVar(value="CSV 未启用")

        self._configure_ttk_style()
        self._build_ui()
        self.refresh_ports(show_message=False)
        self.root.after(POLL_INTERVAL_MS, self._poll_queue)

    def _configure_ttk_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Dark.TCombobox",
            fieldbackground=COLORS["panel_alt"],
            background=COLORS["panel_alt"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["muted"],
            bordercolor=COLORS["border"],
            lightcolor=COLORS["border"],
            darkcolor=COLORS["border"],
            padding=7,
        )
        style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", COLORS["panel_alt"])],
            foreground=[("readonly", COLORS["text"])],
        )
        style.configure(
            "Dark.Treeview",
            background=COLORS["panel"],
            fieldbackground=COLORS["panel"],
            foreground=COLORS["text"],
            rowheight=28,
            borderwidth=0,
        )
        style.configure(
            "Dark.Treeview.Heading",
            background=COLORS["panel_alt"],
            foreground=COLORS["muted"],
            relief="flat",
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        style.map(
            "Dark.Treeview",
            background=[("selected", COLORS["border"])],
        )

    def _build_ui(self) -> None:
        container = tk.Frame(self.root, bg=COLORS["background"], padx=24, pady=20)
        container.pack(fill="both", expand=True)

        self._build_header(container)
        self._build_controls(container)
        self._build_cards(container)

        content = tk.Frame(container, bg=COLORS["background"])
        content.pack(fill="both", expand=True, pady=(16, 0))
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        self.chart = TrendChart(content)
        self.chart.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._build_log(content)

    def _build_header(self, parent: tk.Misc) -> None:
        header = tk.Frame(parent, bg=COLORS["background"])
        header.pack(fill="x", pady=(0, 16))

        title_area = tk.Frame(header, bg=COLORS["background"])
        title_area.pack(side="left")
        tk.Label(
            title_area,
            text=APP_TITLE,
            bg=COLORS["background"],
            fg=COLORS["text"],
            font=("Microsoft YaHei UI", 20, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_area,
            text="T026 · 状态解析 / 异常提示 / CSV 记录",
            bg=COLORS["background"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 10),
        ).pack(anchor="w", pady=(4, 0))

        health = tk.Frame(
            header,
            bg=COLORS["panel"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            padx=18,
            pady=10,
        )
        health.pack(side="right")
        self.health_title_label = tk.Label(
            health,
            textvariable=self.health_title_var,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 11, "bold"),
        )
        self.health_title_label.pack(anchor="e")
        tk.Label(
            health,
            textvariable=self.health_detail_var,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="e", pady=(3, 0))

    def _build_controls(self, parent: tk.Misc) -> None:
        panel = tk.Frame(
            parent,
            bg=COLORS["panel"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            padx=16,
            pady=14,
        )
        panel.pack(fill="x")

        fields = tk.Frame(panel, bg=COLORS["panel"])
        fields.pack(fill="x")

        self.port_combo = self._add_combo(fields, "串口", self.port_var, 24)
        self.port_combo.pack(side="left", padx=(0, 8))
        self._add_entry(fields, "波特率", self.baud_var, 10).pack(
            side="left", padx=(0, 8)
        )
        self._add_combo(
            fields,
            "数据位",
            self.bytesize_var,
            8,
            ("5", "6", "7", "8"),
        ).pack(side="left", padx=(0, 8))
        self._add_combo(
            fields,
            "校验",
            self.parity_var,
            8,
            ("N", "E", "O", "M", "S"),
        ).pack(side="left", padx=(0, 8))
        self._add_combo(
            fields,
            "停止位",
            self.stopbits_var,
            8,
            ("1", "1.5", "2"),
        ).pack(side="left", padx=(0, 12))

        self._button(fields, "刷新串口", self.refresh_ports, COLORS["panel_alt"]).pack(
            side="left", padx=(0, 8)
        )
        self._button(fields, "连接串口", self.start_serial, COLORS["blue"]).pack(
            side="left", padx=(0, 8)
        )
        self._button(fields, "模拟模式", self.start_simulation, COLORS["cyan"]).pack(
            side="left", padx=(0, 8)
        )
        self._button(fields, "停止", self.stop, COLORS["panel_alt"]).pack(side="left")

        footer = tk.Frame(panel, bg=COLORS["panel"])
        footer.pack(fill="x", pady=(12, 0))
        tk.Label(
            footer,
            textvariable=self.connection_var,
            bg=COLORS["panel"],
            fg=COLORS["green"],
            font=("Microsoft YaHei UI", 9, "bold"),
        ).pack(side="left")
        tk.Label(
            footer,
            text="  ·  ",
            bg=COLORS["panel"],
            fg=COLORS["border"],
        ).pack(side="left")
        tk.Label(
            footer,
            textvariable=self.counter_var,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left")
        self.csv_button = self._button(
            footer,
            "选择 CSV 日志",
            self.toggle_csv,
            COLORS["panel_alt"],
        )
        self.csv_button.pack(side="right")
        tk.Label(
            footer,
            textvariable=self.csv_var,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 9),
            padx=12,
        ).pack(side="right")

    def _add_combo(
        self,
        parent: tk.Misc,
        title: str,
        variable: tk.StringVar,
        width: int,
        values: tuple[str, ...] = (),
    ) -> tk.Frame:
        wrapper = tk.Frame(parent, bg=COLORS["panel"])
        tk.Label(
            wrapper,
            text=title,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 8),
        ).pack(anchor="w")
        combo = ttk.Combobox(
            wrapper,
            textvariable=variable,
            values=values,
            width=width,
            state="readonly",
            style="Dark.TCombobox",
        )
        combo.pack(pady=(3, 0))
        wrapper.combo = combo  # type: ignore[attr-defined]
        return wrapper

    def _add_entry(
        self,
        parent: tk.Misc,
        title: str,
        variable: tk.StringVar,
        width: int,
    ) -> tk.Frame:
        wrapper = tk.Frame(parent, bg=COLORS["panel"])
        tk.Label(
            wrapper,
            text=title,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 8),
        ).pack(anchor="w")
        tk.Entry(
            wrapper,
            textvariable=variable,
            width=width,
            bg=COLORS["panel_alt"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            font=("Segoe UI", 10),
        ).pack(fill="x", ipady=7, pady=(3, 0))
        return wrapper

    def _button(
        self,
        parent: tk.Misc,
        text: str,
        command: Callable[[], None],
        background: str,
    ) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=background,
            fg=COLORS["background"] if background == COLORS["cyan"] else COLORS["text"],
            activebackground=COLORS["border"],
            activeforeground=COLORS["text"],
            relief="flat",
            padx=13,
            pady=7,
            cursor="hand2",
            font=("Microsoft YaHei UI", 9, "bold"),
        )

    def _build_cards(self, parent: tk.Misc) -> None:
        cards = tk.Frame(parent, bg=COLORS["background"])
        cards.pack(fill="x", pady=(16, 0))
        for column in range(4):
            cards.grid_columnconfigure(column, weight=1, uniform="cards")

        definitions = (
            ("active_voice_count", "当前复音数", "voices", COLORS["cyan"]),
            ("clip_count", "削波计数", "events", COLORS["yellow"]),
            ("event_fifo_level", "FIFO 当前水位", f"/ {FIFO_DEPTH}", COLORS["blue"]),
            ("event_fifo_high_watermark", "FIFO 历史峰值", f"/ {FIFO_DEPTH}", COLORS["blue"]),
            ("event_fifo_overflow", "FIFO 溢出", "events", COLORS["red"]),
            ("audio_underrun", "音频欠载", "events", COLORS["red"]),
            ("max_processing_cycles", "最大处理周期", "cycles", COLORS["green"]),
        )
        self.cards: dict[str, StatusCard] = {}
        for index, (field, title, unit, accent) in enumerate(definitions):
            card = StatusCard(cards, title, unit, accent)
            card.grid(
                row=index // 4,
                column=index % 4,
                sticky="nsew",
                padx=(0 if index % 4 == 0 else 5, 0 if index % 4 == 3 else 5),
                pady=(0, 10 if index < 4 else 0),
            )
            self.cards[field] = card

    def _build_log(self, parent: tk.Misc) -> None:
        log_panel = tk.Frame(parent, bg=COLORS["panel"])
        log_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        columns = ("time", "kind", "message")
        self.log_tree = ttk.Treeview(
            log_panel,
            columns=columns,
            show="headings",
            style="Dark.Treeview",
        )
        self.log_tree.heading("time", text="时间")
        self.log_tree.heading("kind", text="类型")
        self.log_tree.heading("message", text="内容")
        self.log_tree.column("time", width=78, anchor="center", stretch=False)
        self.log_tree.column("kind", width=76, anchor="center", stretch=False)
        self.log_tree.column("message", width=380, anchor="w")
        self.log_tree.tag_configure("error", foreground=COLORS["red"])
        self.log_tree.tag_configure("valid", foreground=COLORS["text"])

        scrollbar = ttk.Scrollbar(log_panel, orient="vertical", command=self.log_tree.yview)
        self.log_tree.configure(yscrollcommand=scrollbar.set)
        self.log_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def refresh_ports(self, show_message: bool = True) -> None:
        try:
            ports = discover_serial_ports()
        except (ImportError, OSError, RuntimeError) as exc:
            messagebox.showerror("串口扫描失败", f"{exc}\n可尝试：python -m pip install pyserial")
            return

        self.port_lookup.clear()
        displays: list[str] = []
        for device, description_text in ports:
            description = description_text.strip()
            display = device if not description else f"{device} · {description}"
            displays.append(display)
            self.port_lookup[display] = device

        combo = self.port_combo.combo  # type: ignore[attr-defined]
        combo.configure(values=tuple(displays))
        if displays:
            if self.port_var.get() not in displays:
                self.port_var.set(displays[0])
            self.connection_var.set(f"发现 {len(displays)} 个串口")
        else:
            self.port_var.set("")
            self.connection_var.set("未发现串口")
            if show_message:
                messagebox.showinfo("串口", "当前未发现可用串口。")

    def start_serial(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            messagebox.showinfo("正在运行", "请先停止当前监视。")
            return

        display = self.port_var.get()
        port = self.port_lookup.get(display, display.strip())
        required = {
            "串口": port,
            "波特率": self.baud_var.get().strip(),
            "数据位": self.bytesize_var.get().strip(),
            "校验位": self.parity_var.get().strip(),
            "停止位": self.stopbits_var.get().strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            messagebox.showwarning(
                "参数未填写",
                "请根据 T025 已确认的协议填写：" + "、".join(missing),
            )
            return

        try:
            port, baud_rate, byte_size, parity, stop_bits = validate_serial_settings(
                port,
                required["波特率"],
                required["数据位"],
                required["校验位"],
                required["停止位"],
            )
        except ValueError as exc:
            messagebox.showerror("参数错误", str(exc))
            return

        self._prepare_worker(f"正在连接 {port}")
        self.worker = threading.Thread(
            target=self._serial_worker,
            args=(port, baud_rate, byte_size, parity, stop_bits),
            daemon=True,
        )
        self.worker.start()

    def start_simulation(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            messagebox.showinfo("正在运行", "请先停止当前监视。")
            return
        self._prepare_worker("模拟模式运行中")
        self.worker = threading.Thread(target=self._simulation_worker, daemon=True)
        self.worker.start()

    def _prepare_worker(self, text: str) -> None:
        self.stop_event.clear()
        self.connection_var.set(text)
        self.health_title_var.set("等待数据")
        self.health_detail_var.set("监视器已经启动")
        self.health_title_label.configure(fg=COLORS["muted"])

    def _serial_worker(
        self,
        port: str,
        baud_rate: int,
        byte_size: int,
        parity: str,
        stop_bits: float,
    ) -> None:
        try:
            for line in serial_status_lines(
                port,
                baud_rate,
                0.5,
                byte_size,
                parity,
                stop_bits,
                stop_requested=self.stop_event.is_set,
            ):
                self.message_queue.put(("line", line))
        except (OSError, RuntimeError, ValueError) as exc:
            self.message_queue.put(("fatal", str(exc)))
        finally:
            self.message_queue.put(("stopped", None))

    def _simulation_worker(self) -> None:
        try:
            for line in simulate_status_lines(0.35):
                if self.stop_event.is_set():
                    break
                self.message_queue.put(("line", line))
        finally:
            self.message_queue.put(("stopped", None))

    def stop(self) -> None:
        if self.worker is None or not self.worker.is_alive():
            self.connection_var.set("当前没有运行中的监视任务")
            return
        self.stop_event.set()
        self.connection_var.set("正在停止…")

    def toggle_csv(self) -> None:
        if self.csv_logger is not None:
            self.csv_logger.__exit__(None, None, None)
            self.csv_logger = None
            self.csv_var.set("CSV 未启用")
            self.csv_button.configure(text="选择 CSV 日志")
            return

        selected = filedialog.asksaveasfilename(
            title="选择 CSV 日志文件",
            defaultextension=".csv",
            filetypes=(("CSV 文件", "*.csv"), ("所有文件", "*.*")),
            initialfile="fpga_status.csv",
        )
        if not selected:
            return
        try:
            self.csv_logger = CsvStatusLogger(Path(selected)).__enter__()
        except OSError as exc:
            self.csv_logger = None
            messagebox.showerror("CSV 打开失败", str(exc))
            return
        self.csv_var.set(f"记录中 · {Path(selected).name}")
        self.csv_button.configure(text="停止 CSV 记录")

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.message_queue.get_nowait()
                if kind == "line":
                    self._handle_line(str(payload))
                elif kind == "fatal":
                    self._handle_fatal(str(payload))
                elif kind == "stopped" and self.stop_event.is_set():
                    self.worker = None
                    self.connection_var.set("已停止")
        except queue.Empty:
            pass
        self.root.after(POLL_INTERVAL_MS, self._poll_queue)

    def _handle_line(self, line: str) -> None:
        try:
            snapshot = parse_status_line(line)
        except StatusParseError as exc:
            self.error_count += 1
            self.health_title_var.set("数据格式错误")
            self.health_detail_var.set(str(exc))
            self.health_title_label.configure(fg=COLORS["red"])
            self._add_log("解析错误", f"{exc} · {line.strip()}", "error")
            self._update_counter()
            return

        self.valid_count += 1
        for field_name, card in self.cards.items():
            card.set_value(getattr(snapshot, field_name))
        self.chart.append(snapshot)

        title, detail, color = classify_snapshot(snapshot)
        self.health_title_var.set(title)
        self.health_detail_var.set(detail)
        self.health_title_label.configure(fg=color)
        self.connection_var.set("正在接收数据")
        self._add_log("有效", snapshot.format_human(), "valid")

        if self.csv_logger is not None:
            try:
                self.csv_logger.append(snapshot)
            except OSError as exc:
                self.csv_logger.__exit__(None, None, None)
                self.csv_logger = None
                self.csv_var.set("CSV 写入失败")
                self.csv_button.configure(text="选择 CSV 日志")
                self._add_log("CSV 错误", str(exc), "error")
        self._update_counter()

    def _handle_fatal(self, message: str) -> None:
        self.error_count += 1
        self.connection_var.set("连接失败")
        self.health_title_var.set("运行错误")
        self.health_detail_var.set(message)
        self.health_title_label.configure(fg=COLORS["red"])
        self._add_log("运行错误", message, "error")
        self._update_counter()

    def _add_log(self, kind: str, message: str, tag: str) -> None:
        self.log_tree.insert(
            "",
            "end",
            values=(datetime.now().strftime("%H:%M:%S"), kind, message),
            tags=(tag,),
        )
        rows = self.log_tree.get_children()
        if len(rows) > MAX_LOG_ROWS:
            self.log_tree.delete(rows[0])
        self.log_tree.yview_moveto(1.0)

    def _update_counter(self) -> None:
        self.counter_var.set(f"有效 {self.valid_count} · 错误 {self.error_count}")

    def close(self) -> None:
        self.stop_event.set()
        if self.csv_logger is not None:
            self.csv_logger.__exit__(None, None, None)
            self.csv_logger = None
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    StatusMonitorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
