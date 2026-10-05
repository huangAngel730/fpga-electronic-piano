#!/usr/bin/env python3
"""FPGA electronic-piano team USB MIDI monitor GUI."""

from __future__ import annotations

import itertools
import queue
import time
import tkinter as tk
from collections import deque
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from midi_monitor import (
    CsvMidiLogger,
    MidiEvent,
    MidiStatistics,
    describe_midi_message,
    simulation_messages,
)
from midi_input_worker import MidiInputWorker


APP_TITLE = "FPGA 电子琴 · 队伍 MIDI 监视器"
POLL_INTERVAL_MS = 50
SIMULATION_INTERVAL_MS = 520
MAX_LOG_ROWS = 500
MAX_EVENTS_PER_POLL = 100
RECONNECT_DELAY_MS = 1000

COLORS = {
    "background": "#07111F",
    "panel": "#101D2F",
    "panel_alt": "#15253B",
    "border": "#243955",
    "text": "#F4F8FC",
    "muted": "#91A6C2",
    "cyan": "#35D4FF",
    "blue": "#658DFF",
    "green": "#42D69A",
    "yellow": "#FFCB67",
    "red": "#FF647C",
    "white_key": "#EAF0F7",
    "black_key": "#172337",
}


try:
    import mido  # type: ignore

    MIDI_BACKEND: Any = mido.Backend("mido.backends.rtmidi")
    MIDI_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - depends on local packages
    mido = None
    MIDI_BACKEND = None
    MIDI_IMPORT_ERROR = exc


class MetricCard(tk.Frame):
    """Compact dashboard card with a title, value, and explanation."""

    def __init__(self, parent: tk.Misc, title: str, detail: str, accent: str) -> None:
        super().__init__(
            parent,
            bg=COLORS["panel"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            padx=16,
            pady=12,
        )
        self.value_var = tk.StringVar(value="—")
        tk.Label(
            self,
            text=title,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 9),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            self,
            textvariable=self.value_var,
            bg=COLORS["panel"],
            fg=accent,
            font=("Segoe UI Semibold", 21),
            anchor="w",
        ).pack(fill="x", pady=(5, 2))
        tk.Label(
            self,
            text=detail,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 8),
            anchor="w",
        ).pack(fill="x")

    def set(self, value: object) -> None:
        self.value_var.set(str(value))


class ValueMeter(tk.Canvas):
    """A horizontal meter for 7-bit controls and signed pitch bend."""

    def __init__(
        self,
        parent: tk.Misc,
        label: str,
        minimum: int,
        maximum: int,
        accent: str,
    ) -> None:
        super().__init__(
            parent,
            bg=COLORS["panel"],
            highlightthickness=0,
            height=58,
        )
        self.label = label
        self.minimum = minimum
        self.maximum = maximum
        self.accent = accent
        self.current = 0
        self.bind("<Configure>", lambda _event: self.redraw())

    def set(self, value: int) -> None:
        self.current = max(self.minimum, min(value, self.maximum))
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 200)
        left, right, top, bottom = 12, width - 12, 30, 46
        self.create_text(
            left,
            12,
            text=self.label,
            anchor="w",
            fill=COLORS["text"],
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        self.create_text(
            right,
            12,
            text=str(self.current),
            anchor="e",
            fill=self.accent,
            font=("Segoe UI Semibold", 10),
        )
        self.create_rectangle(left, top, right, bottom, fill=COLORS["panel_alt"], outline="")
        ratio = (self.current - self.minimum) / max(1, self.maximum - self.minimum)
        fill_right = left + (right - left) * ratio
        self.create_rectangle(left, top, fill_right, bottom, fill=self.accent, outline="")
        if self.minimum < 0 < self.maximum:
            center = left + (right - left) * (-self.minimum) / (self.maximum - self.minimum)
            self.create_line(center, top - 3, center, bottom + 3, fill=COLORS["text"])


class PianoStrip(tk.Canvas):
    """Draw MIDI notes C2..C6 and highlight currently held keys."""

    FIRST_NOTE = 36
    LAST_NOTE = 84
    BLACK_CLASSES = {1, 3, 6, 8, 10}

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(
            parent,
            bg=COLORS["panel"],
            highlightthickness=0,
            height=128,
        )
        self.active_notes: set[int] = set()
        self.last_note: int | None = None
        self.bind("<Configure>", lambda _event: self.redraw())

    def set_notes(self, active_notes: set[tuple[int, int]], last_note: int | None) -> None:
        self.active_notes = {note for _channel, note in active_notes}
        self.last_note = last_note
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 500)
        white_notes = [
            note
            for note in range(self.FIRST_NOTE, self.LAST_NOTE + 1)
            if note % 12 not in self.BLACK_CLASSES
        ]
        white_width = width / len(white_notes)
        x_by_note: dict[int, float] = {}

        for index, note in enumerate(white_notes):
            x0 = index * white_width
            x1 = (index + 1) * white_width
            x_by_note[note] = x0
            fill = COLORS["cyan"] if note in self.active_notes else COLORS["white_key"]
            if note == self.last_note and note not in self.active_notes:
                fill = COLORS["yellow"]
            self.create_rectangle(x0, 2, x1, 122, fill=fill, outline=COLORS["border"])
            if note % 12 == 0:
                self.create_text(
                    x0 + white_width / 2,
                    108,
                    text=f"C{note // 12 - 1}",
                    fill="#51647A",
                    font=("Segoe UI", 7),
                )

        for note in range(self.FIRST_NOTE, self.LAST_NOTE + 1):
            if note % 12 not in self.BLACK_CLASSES:
                continue
            previous_white = note - 1
            while previous_white % 12 in self.BLACK_CLASSES:
                previous_white -= 1
            if previous_white not in x_by_note:
                continue
            center = x_by_note[previous_white] + white_width
            black_width = white_width * 0.62
            fill = COLORS["cyan"] if note in self.active_notes else COLORS["black_key"]
            if note == self.last_note and note not in self.active_notes:
                fill = COLORS["yellow"]
            self.create_rectangle(
                center - black_width / 2,
                2,
                center + black_width / 2,
                76,
                fill=fill,
                outline=COLORS["background"],
            )


class MidiMonitorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1420x860")
        self.root.minsize(1120, 720)
        self.root.configure(bg=COLORS["background"])
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.event_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.input_worker: MidiInputWorker | None = None
        self.requested_device_name: str | None = None
        self.reconnect_job: str | None = None
        self.poll_job: str | None = None
        self.last_receiver_heartbeat = 0.0
        self.closing = False
        self.csv_logger: CsvMidiLogger | None = None
        self.stats = MidiStatistics()
        self.last_note: int | None = None
        self.recent_note_velocities: deque[int] = deque(maxlen=8)
        self.velocity_warning_active = False
        self.simulation_job: str | None = None
        self.simulation_cycle = itertools.cycle(simulation_messages())

        self.device_var = tk.StringVar()
        self.connection_var = tk.StringVar(value="未连接")
        self.connection_detail_var = tk.StringVar(value="请选择USB MIDI设备，或先运行模拟模式")
        self.csv_var = tk.StringVar(value="CSV未记录")
        self.counter_var = tk.StringVar(value="消息 0 · Note On 0 · Note Off 0")
        self.filter_vars = {
            "notes": tk.BooleanVar(value=True),
            "controls": tk.BooleanVar(value=True),
            "pitch": tk.BooleanVar(value=True),
            "pressure": tk.BooleanVar(value=True),
            "system": tk.BooleanVar(value=False),
        }

        self._configure_style()
        self._build_ui()
        self.refresh_devices(show_dialog=False)
        self.poll_job = self.root.after(POLL_INTERVAL_MS, self._poll_queue)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background=COLORS["panel"],
            fieldbackground=COLORS["panel"],
            foreground=COLORS["text"],
            rowheight=29,
            borderwidth=0,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Treeview.Heading",
            background=COLORS["panel_alt"],
            foreground=COLORS["text"],
            relief="flat",
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        style.map("Treeview", background=[("selected", "#254C6D")])
        style.configure(
            "TCombobox",
            fieldbackground=COLORS["panel_alt"],
            background=COLORS["panel_alt"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["text"],
            bordercolor=COLORS["border"],
        )

    def _button(
        self,
        parent: tk.Misc,
        text: str,
        command: Any,
        accent: str = COLORS["panel_alt"],
        foreground: str = COLORS["text"],
    ) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=accent,
            fg=foreground,
            activebackground=COLORS["blue"],
            activeforeground=COLORS["text"],
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            font=("Microsoft YaHei UI", 9),
        )

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, bg=COLORS["background"], padx=22, pady=18)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=COLORS["background"])
        header.pack(fill="x")
        title_column = tk.Frame(header, bg=COLORS["background"])
        title_column.pack(side="left", fill="x", expand=True)
        tk.Label(
            title_column,
            text="队伍 MIDI 监视器",
            bg=COLORS["background"],
            fg=COLORS["text"],
            font=("Microsoft YaHei UI", 22, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            title_column,
            text="X4 III · Note / Velocity / Pitch / Mod / Sustain · T036 实物证据采集",
            bg=COLORS["background"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 10),
            anchor="w",
        ).pack(fill="x", pady=(3, 0))

        connection_panel = tk.Frame(
            header,
            bg=COLORS["panel"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            padx=15,
            pady=9,
        )
        connection_panel.pack(side="right")
        tk.Label(
            connection_panel,
            textvariable=self.connection_var,
            bg=COLORS["panel"],
            fg=COLORS["green"],
            font=("Microsoft YaHei UI", 10, "bold"),
        ).pack(anchor="e")
        tk.Label(
            connection_panel,
            textvariable=self.connection_detail_var,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 8),
        ).pack(anchor="e", pady=(2, 0))

        toolbar = tk.Frame(
            outer,
            bg=COLORS["panel"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            padx=14,
            pady=12,
        )
        toolbar.pack(fill="x", pady=(16, 14))
        tk.Label(
            toolbar,
            text="MIDI输入设备",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left", padx=(0, 8))
        self.device_combo = ttk.Combobox(
            toolbar,
            textvariable=self.device_var,
            state="readonly",
            width=48,
        )
        self.device_combo.pack(side="left", fill="x", expand=True)
        self._button(toolbar, "刷新", self.refresh_devices).pack(side="left", padx=(8, 0))
        self._button(toolbar, "连接", self.connect_device, COLORS["blue"]).pack(side="left", padx=(8, 0))
        self._button(toolbar, "断开", self.disconnect_device).pack(side="left", padx=(8, 0))
        self._button(toolbar, "模拟模式", self.start_simulation, COLORS["cyan"], "#062033").pack(
            side="left", padx=(8, 0)
        )
        self._button(toolbar, "开始CSV", self.start_csv, COLORS["green"], "#06251A").pack(
            side="left", padx=(8, 0)
        )
        self._button(toolbar, "停止CSV", self.stop_csv).pack(side="left", padx=(8, 0))

        cards = tk.Frame(outer, bg=COLORS["background"])
        cards.pack(fill="x")
        for column in range(6):
            cards.grid_columnconfigure(column, weight=1, uniform="cards")
        self.note_card = MetricCard(cards, "最后音符", "音名 / MIDI编号", COLORS["cyan"])
        self.velocity_card = MetricCard(cards, "力度", "Velocity 0–127", COLORS["yellow"])
        self.active_card = MetricCard(cards, "按住琴键", "当前物理按键数", COLORS["green"])
        self.channel_card = MetricCard(cards, "MIDI通道", "显示为1–16", COLORS["blue"])
        self.range_card = MetricCard(cards, "力度范围", "本次最小–最大", COLORS["yellow"])
        self.message_card = MetricCard(cards, "消息总数", "本次会话累计", COLORS["cyan"])
        for column, card in enumerate(
            (
                self.note_card,
                self.velocity_card,
                self.active_card,
                self.channel_card,
                self.range_card,
                self.message_card,
            )
        ):
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 5, 0))

        body = tk.PanedWindow(
            outer,
            orient="horizontal",
            bg=COLORS["background"],
            sashwidth=8,
            sashrelief="flat",
            bd=0,
        )
        body.pack(fill="both", expand=True, pady=(14, 0))

        left = tk.Frame(
            body,
            bg=COLORS["panel"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            padx=14,
            pady=12,
        )
        right = tk.Frame(
            body,
            bg=COLORS["panel"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            padx=12,
            pady=12,
        )
        body.add(left, minsize=350, width=410)
        body.add(right, minsize=650)

        tk.Label(
            left,
            text="当前演奏状态",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Microsoft YaHei UI", 12, "bold"),
        ).pack(anchor="w")
        self.piano = PianoStrip(left)
        self.piano.pack(fill="x", pady=(12, 10))
        self.velocity_meter = ValueMeter(left, "Velocity", 0, 127, COLORS["yellow"])
        self.velocity_meter.pack(fill="x", pady=2)
        self.mod_meter = ValueMeter(left, "Modulation · CC1", 0, 127, COLORS["cyan"])
        self.mod_meter.pack(fill="x", pady=2)
        self.sustain_meter = ValueMeter(left, "Sustain · CC64", 0, 127, COLORS["green"])
        self.sustain_meter.pack(fill="x", pady=2)
        self.pitch_meter = ValueMeter(left, "Pitch Bend", -8192, 8191, COLORS["blue"])
        self.pitch_meter.pack(fill="x", pady=2)

        hint = tk.Frame(left, bg=COLORS["panel_alt"], padx=12, pady=10)
        hint.pack(fill="x", pady=(14, 0))
        tk.Label(
            hint,
            text="验收提示",
            bg=COLORS["panel_alt"],
            fg=COLORS["yellow"],
            font=("Microsoft YaHei UI", 9, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            hint,
            text="轻按、正常按、重按同一琴键，确认力度数值发生变化；再测试Pitch、Mod和延音踏板。",
            bg=COLORS["panel_alt"],
            fg=COLORS["muted"],
            wraplength=360,
            justify="left",
            font=("Microsoft YaHei UI", 9),
            anchor="w",
        ).pack(fill="x", pady=(5, 0))

        log_header = tk.Frame(right, bg=COLORS["panel"])
        log_header.pack(fill="x")
        tk.Label(
            log_header,
            text="实时消息",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Microsoft YaHei UI", 12, "bold"),
        ).pack(side="left")
        self._button(log_header, "清空", self.clear_log).pack(side="right")

        filters = tk.Frame(right, bg=COLORS["panel"])
        filters.pack(fill="x", pady=(8, 9))
        for key, label in (
            ("notes", "音符"),
            ("controls", "控制器/踏板"),
            ("pitch", "弯音"),
            ("pressure", "触后压力"),
            ("system", "系统消息"),
        ):
            tk.Checkbutton(
                filters,
                text=label,
                variable=self.filter_vars[key],
                bg=COLORS["panel"],
                fg=COLORS["muted"],
                activebackground=COLORS["panel"],
                activeforeground=COLORS["text"],
                selectcolor=COLORS["panel_alt"],
                font=("Microsoft YaHei UI", 8),
                bd=0,
            ).pack(side="left", padx=(0, 10))

        columns = ("time", "type", "channel", "data1", "data2", "raw", "description")
        self.tree = ttk.Treeview(right, columns=columns, show="headings", selectmode="browse")
        headings = {
            "time": "时间",
            "type": "类型",
            "channel": "通道",
            "data1": "音符/控制器",
            "data2": "力度/数值",
            "raw": "原始字节",
            "description": "说明",
        }
        widths = {
            "time": 100,
            "type": 105,
            "channel": 55,
            "data1": 105,
            "data2": 85,
            "raw": 125,
            "description": 270,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], minwidth=50, stretch=column == "description")
        scrollbar = ttk.Scrollbar(right, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        footer = tk.Frame(outer, bg=COLORS["background"])
        footer.pack(fill="x", pady=(10, 0))
        tk.Label(
            footer,
            textvariable=self.counter_var,
            bg=COLORS["background"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left")
        tk.Label(
            footer,
            textvariable=self.csv_var,
            bg=COLORS["background"],
            fg=COLORS["green"],
            font=("Microsoft YaHei UI", 9),
        ).pack(side="right")

    def refresh_devices(self, show_dialog: bool = True) -> None:
        if MIDI_BACKEND is None:
            self.device_combo["values"] = ()
            self.device_var.set("")
            self.connection_var.set("缺少USB MIDI依赖")
            self.connection_detail_var.set("仍可使用模拟模式；安装方法见使用教程")
            if show_dialog:
                messagebox.showinfo(
                    "需要安装依赖",
                    "真实USB MIDI需要 mido 和 python-rtmidi。\n\n"
                    "请双击本目录的“安装MIDI监视器依赖.cmd”。",
                )
            return
        try:
            names = tuple(MIDI_BACKEND.get_input_names())
        except Exception as exc:
            self.connection_var.set("设备枚举失败")
            self.connection_detail_var.set(str(exc))
            if show_dialog:
                messagebox.showerror("无法列出MIDI设备", str(exc))
            return
        self.device_combo["values"] = names
        if names:
            if self.device_var.get() not in names:
                self.device_var.set(names[0])
            self.connection_var.set("发现MIDI设备")
            self.connection_detail_var.set(f"共 {len(names)} 个输入端口，选择后点击连接")
        else:
            self.device_var.set("")
            self.connection_var.set("未发现MIDI设备")
            self.connection_detail_var.set("检查USB线、键盘电源和Windows设备管理器")

    def connect_device(self) -> None:
        if MIDI_BACKEND is None:
            self.refresh_devices(show_dialog=True)
            return
        name = self.device_var.get().strip()
        if not name:
            messagebox.showwarning("没有设备", "请先连接X4 III并点击刷新。")
            return
        self.stop_simulation()
        self.disconnect_device(update_status=False)
        self.requested_device_name = name
        self._start_input_worker(name)

    def _start_input_worker(self, name: str) -> None:
        if self.closing or MIDI_BACKEND is None:
            return
        if self.reconnect_job is not None:
            try:
                self.root.after_cancel(self.reconnect_job)
            except tk.TclError:
                pass
            self.reconnect_job = None
        worker = MidiInputWorker(MIDI_BACKEND, name, self.event_queue)
        self.input_worker = worker
        self.last_receiver_heartbeat = time.monotonic()
        self.connection_var.set("正在连接")
        self.connection_detail_var.set(name)
        worker.start()

    def disconnect_device(self, update_status: bool = True) -> None:
        self.requested_device_name = None
        if self.reconnect_job is not None:
            try:
                self.root.after_cancel(self.reconnect_job)
            except tk.TclError:
                pass
            self.reconnect_job = None
        worker = self.input_worker
        self.input_worker = None
        if worker is not None:
            worker.stop()
        if update_status:
            self.connection_var.set("已断开")
            self.connection_detail_var.set("可以选择其他设备或运行模拟模式")

    def _schedule_reconnect(self, reason: str) -> None:
        if self.closing or self.requested_device_name is None or self.reconnect_job is not None:
            return
        self.connection_var.set("接收中断，准备重连")
        self.connection_detail_var.set(reason)
        self.reconnect_job = self.root.after(RECONNECT_DELAY_MS, self._reconnect_device)

    def _reconnect_device(self) -> None:
        self.reconnect_job = None
        name = self.requested_device_name
        if self.closing or name is None:
            return
        self._start_input_worker(name)

    def start_simulation(self) -> None:
        self.disconnect_device(update_status=False)
        self.stop_simulation()
        self.connection_var.set("模拟模式")
        self.connection_detail_var.set("不连接硬件，用示例消息检查界面和CSV")
        self._simulation_step()

    def _simulation_step(self) -> None:
        message = next(self.simulation_cycle)
        self.event_queue.put(("event", describe_midi_message(message)))
        self.simulation_job = self.root.after(SIMULATION_INTERVAL_MS, self._simulation_step)

    def stop_simulation(self) -> None:
        if self.simulation_job is not None:
            self.root.after_cancel(self.simulation_job)
            self.simulation_job = None

    def start_csv(self) -> None:
        if self.csv_logger is not None:
            messagebox.showinfo("CSV正在记录", str(self.csv_logger.path))
            return
        default_name = f"midi_capture_{datetime.now():%Y%m%d_%H%M%S}.csv"
        path = filedialog.asksaveasfilename(
            title="选择MIDI日志保存位置",
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=(("CSV文件", "*.csv"), ("所有文件", "*.*")),
        )
        if not path:
            return
        try:
            self.csv_logger = CsvMidiLogger(path)
        except OSError as exc:
            messagebox.showerror("无法创建CSV", str(exc))
            return
        self.csv_var.set(f"CSV记录中：{Path(path).name}")

    def stop_csv(self) -> None:
        if self.csv_logger is not None:
            path = self.csv_logger.path
            self.csv_logger.close()
            self.csv_logger = None
            self.csv_var.set(f"CSV已保存：{path.name}")

    def _poll_queue(self) -> None:
        if self.closing:
            return
        processed = 0
        try:
            while processed < MAX_EVENTS_PER_POLL:
                kind, payload = self.event_queue.get_nowait()
                processed += 1
                if kind == "event":
                    self._handle_event(payload)  # type: ignore[arg-type]
                elif kind == "error":
                    self.connection_var.set("接收数据错误")
                    self.connection_detail_var.set(str(payload))
                elif kind == "receiver_connected":
                    if payload is self.input_worker:
                        self.connection_var.set("已连接")
                        self.connection_detail_var.set(self.requested_device_name or "MIDI设备")
                elif kind == "receiver_heartbeat":
                    if payload is self.input_worker:
                        self.last_receiver_heartbeat = time.monotonic()
                elif kind == "receiver_message":
                    worker, message = payload  # type: ignore[misc]
                    if worker is self.input_worker:
                        self.last_receiver_heartbeat = time.monotonic()
                        try:
                            self._handle_event(describe_midi_message(message))
                        except Exception as exc:
                            self.connection_var.set("接收数据错误")
                            self.connection_detail_var.set(str(exc))
                elif kind == "receiver_error":
                    worker, error_text = payload  # type: ignore[misc]
                    if worker is self.input_worker:
                        self.connection_var.set("MIDI端口错误")
                        self.connection_detail_var.set(str(error_text))
                elif kind == "receiver_stopped":
                    if payload is self.input_worker:
                        self.input_worker = None
                        self._schedule_reconnect("端口已停止，正在自动重新连接")
        except queue.Empty:
            pass
        delay = 1 if not self.event_queue.empty() else POLL_INTERVAL_MS
        self.poll_job = self.root.after(delay, self._poll_queue)

    def _handle_event(self, event: MidiEvent) -> None:
        self.stats.update(event)
        if event.note is not None:
            self.last_note = event.note
        if event.velocity is not None and event.event_type == "note_on":
            self.velocity_meter.set(event.velocity)
            self.recent_note_velocities.append(event.velocity)
            if (
                len(self.recent_note_velocities) == self.recent_note_velocities.maxlen
                and len(set(self.recent_note_velocities)) == 1
            ):
                velocity = self.recent_note_velocities[0]
                self.velocity_warning_active = True
                self.connection_detail_var.set(
                    f"连续8次Note On力度都是{velocity}；软件读取的是原始MIDI值，"
                    "请检查X4 III的VEL是否设为Fixed"
                )
            elif self.velocity_warning_active and len(set(self.recent_note_velocities)) > 1:
                self.velocity_warning_active = False
                self.connection_detail_var.set(self.requested_device_name or "力度已经发生变化")
        if event.event_type == "control_change":
            if event.controller == 1 and event.value is not None:
                self.mod_meter.set(event.value)
            elif event.controller == 64 and event.value is not None:
                self.sustain_meter.set(event.value)
        elif event.event_type == "pitchwheel" and event.pitch is not None:
            self.pitch_meter.set(event.pitch)

        if event.note is not None:
            self.note_card.set(event.note_name)
        if event.velocity is not None:
            self.velocity_card.set(event.velocity)
        self.active_card.set(self.stats.active_note_count)
        self.channel_card.set(event.channel if event.channel is not None else "系统")
        self.range_card.set(self.stats.velocity_range_text)
        self.message_card.set(self.stats.message_count)
        self.counter_var.set(
            f"消息 {self.stats.message_count} · Note On {self.stats.note_on_count} · "
            f"Note Off {self.stats.note_off_count} · 当前按住 {self.stats.active_note_count}"
        )
        self.piano.set_notes(self.stats.active_notes, self.last_note)

        if self.csv_logger is not None:
            try:
                self.csv_logger.write(event)
            except OSError as exc:
                self.stop_csv()
                messagebox.showerror("CSV写入失败", str(exc))

        if self._event_is_visible(event):
            self._insert_tree_row(event)

    def _event_is_visible(self, event: MidiEvent) -> bool:
        if event.event_type in ("note_on", "note_off"):
            return self.filter_vars["notes"].get()
        if event.event_type == "control_change":
            return self.filter_vars["controls"].get()
        if event.event_type == "pitchwheel":
            return self.filter_vars["pitch"].get()
        if event.event_type in ("polytouch", "aftertouch"):
            return self.filter_vars["pressure"].get()
        return self.filter_vars["system"].get()

    def _insert_tree_row(self, event: MidiEvent) -> None:
        data1 = event.note_name
        if event.controller is not None:
            data1 = event.controller_name
        data2: object = ""
        if event.velocity is not None:
            data2 = event.velocity
        elif event.value is not None:
            data2 = event.value
        elif event.pitch is not None:
            data2 = event.pitch
        values = (
            event.timestamp[11:],
            event.event_type,
            event.channel or "—",
            data1,
            data2,
            event.raw_hex,
            event.description,
        )
        self.tree.insert("", "end", values=values)
        children = self.tree.get_children()
        while len(children) > MAX_LOG_ROWS:
            self.tree.delete(children[0])
            children = children[1:]
        self.tree.yview_moveto(1.0)

    def clear_log(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.stats = MidiStatistics()
        self.last_note = None
        self.recent_note_velocities.clear()
        self.velocity_warning_active = False
        self.note_card.set("—")
        self.velocity_card.set("—")
        self.active_card.set(0)
        self.channel_card.set("—")
        self.range_card.set("—")
        self.message_card.set(0)
        self.velocity_meter.set(0)
        self.mod_meter.set(0)
        self.sustain_meter.set(0)
        self.pitch_meter.set(0)
        self.piano.set_notes(set(), None)
        self.counter_var.set("消息 0 · Note On 0 · Note Off 0")

    def close(self) -> None:
        if self.closing:
            return
        self.closing = True
        if self.poll_job is not None:
            try:
                self.root.after_cancel(self.poll_job)
            except tk.TclError:
                pass
            self.poll_job = None
        self.stop_simulation()
        self.disconnect_device(update_status=False)
        self.stop_csv()
        self.root.destroy()


def main() -> int:
    root = tk.Tk()
    MidiMonitorApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
