"""Local MIDI selection, independently checked preview and confirmed export."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import uuid

# Explicit trusted sibling path also supports python -I -S script execution.
# No current-working-directory or arbitrary PYTHONPATH fallback is used.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from desktop_controller import Controller, DesktopError
from preview_model import ROOT


class DesktopApp:
    """All Tk calls occur on its creating/main thread; no automatic export."""

    def __init__(self, root, controller, chooser=None, directory_chooser=None, confirm=None):
        self.root, self.controller = root, controller
        self.chooser = chooser or self._choose_file
        self.directory_chooser = directory_chooser or self._choose_destination
        self.confirm = confirm or self._confirm_export
        self._closing, self._after = False, None
        self.file_var = tk.StringVar(root, value='未选择本地 MIDI 文件')
        self.status_var = tk.StringVar(root, value='选择 .mid → 导入并离线核验 → 查看全部事件 → 确认导出')
        self.summary_var = tk.StringVar(root, value='尚无已核验预览；不能导出。')
        self.score_id_var, self.session_var = tk.StringVar(root, value='1'), tk.StringVar(root, value='1')
        self.source_var = tk.StringVar(root, value='本地文件；请填写来源，不自动核实授权')
        self.license_var = tk.StringVar(root, value='未提供；不声称拥有再分发权')
        root.title('T057 本地 MIDI 离线导入与预览（不连接设备）')
        root.geometry('1200x800')
        frame = ttk.Frame(root, padding=10)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='仅离线音符事件预览；不联网、不串口、不播放，不代表 FPGA ACK 或已发声。',
                  foreground='#9a3310').pack(anchor='w')
        ttk.Label(frame, textvariable=self.file_var, wraplength=1150).pack(anchor='w', pady=5)
        controls = ttk.Frame(frame)
        controls.pack(fill='x')
        self.choose_button = ttk.Button(controls, text='1 选择本地 .mid', command=self.choose)
        self.preview_button = ttk.Button(controls, text='2 导入并核验预览', command=self.preview)
        self.export_button = ttk.Button(controls, text='3 确认并导出', command=self.export)
        self.cancel_button = ttk.Button(controls, text='取消当前操作', command=self.cancel)
        for widget in (self.choose_button, self.preview_button, self.export_button, self.cancel_button):
            widget.pack(side='left', padx=(0, 8))
        identifiers = ttk.Frame(frame)
        identifiers.pack(fill='x', pady=8)
        ttk.Label(identifiers, text='score_id (0..4294967295)').pack(side='left')
        ttk.Entry(identifiers, textvariable=self.score_id_var, width=15).pack(side='left', padx=8)
        ttk.Label(identifiers, text='session (1..65535)').pack(side='left')
        ttk.Entry(identifiers, textvariable=self.session_var, width=10).pack(side='left', padx=8)
        metadata = ttk.Frame(frame)
        metadata.pack(fill='x')
        ttk.Label(metadata, text='来源说明').grid(row=0, column=0, sticky='w')
        ttk.Entry(metadata, textvariable=self.source_var).grid(row=0, column=1, sticky='ew', padx=5)
        ttk.Label(metadata, text='使用权限').grid(row=1, column=0, sticky='w')
        ttk.Entry(metadata, textvariable=self.license_var).grid(row=1, column=1, sticky='ew', padx=5)
        metadata.columnconfigure(1, weight=1)
        ttk.Label(frame, textvariable=self.summary_var, wraplength=1150).pack(anchor='w', pady=8)
        ttk.Label(frame, text='Tempo 时间轴（默认 500000 μs/四分音符；绝对有理时间累计，最近样本、恰半向上）').pack(anchor='w')
        tempo_frame = ttk.Frame(frame)
        tempo_frame.pack(fill='x')
        self.tempo_text = tk.Text(tempo_frame, height=4, wrap='none', state='disabled')
        tempo_scroll = ttk.Scrollbar(tempo_frame, orient='vertical', command=self.tempo_text.yview)
        self.tempo_text.configure(yscrollcommand=tempo_scroll.set)
        self.tempo_text.pack(side='left', fill='x', expand=True)
        tempo_scroll.pack(side='right', fill='y')
        columns = ('index', 'track', 'channel', 'midi_tick', 'sample_tick', 'seconds',
                   'type', 'note', 'velocity', 'exact_samples', 'record_hex')
        table = ttk.Frame(frame)
        table.pack(fill='both', expand=True, pady=8)
        self.tree = ttk.Treeview(table, columns=columns, show='headings', height=16)
        headings = ('序号', '轨道(0起)', '通道(0起)', 'MIDI tick', '样本 tick', '秒',
                    '事件', 'note', 'velocity', '精确样本分数', '原8字节记录')
        widths = (55, 75, 75, 100, 105, 100, 90, 55, 65, 180, 155)
        for name, heading, width in zip(columns, headings, widths):
            self.tree.heading(name, text=heading)
            self.tree.column(name, width=width, minwidth=50, stretch=False)
        vertical = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
        horizontal = ttk.Scrollbar(table, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        ttk.Label(frame, textvariable=self.status_var, wraplength=1150).pack(anchor='w')
        ttk.Label(frame, text='Type0/1、PPQN、1..512 NoteOn/Off；零力度归一。CC/延音、音色、弯音、SysEx、SMPTE 等明确拒收。',
                  wraplength=1150).pack(anchor='w', pady=(5, 0))
        root.protocol('WM_DELETE_WINDOW', self.close)
        self._refresh()
        self._after = root.after(50, self._tick)

    def _choose_file(self):
        return filedialog.askopenfilename(parent=self.root, title='选择已有本地 MIDI 原件',
                                         filetypes=[('MIDI', '*.mid *.midi'), ('所有文件', '*')])

    def _choose_destination(self):
        # A save-name dialog gives a NONEXISTING directory name, not an existing
        # folder selection. No file is created by the dialog itself.
        return filedialog.asksaveasfilename(parent=self.root,
                                           title='输入全新导出文件夹名称（不能选已有目录）',
                                           initialfile='t057_export_' + uuid.uuid4().hex[:8])

    def _confirm_export(self, destination):
        return messagebox.askyesno('确认离线导出',
                                   '将已核验的 JSON／原编码／离线读回保存到：\n' + str(destination)
                                   + '\n\n不发送任何字节到设备。确认导出？', parent=self.root)

    def _error(self, error):
        self.status_var.set(str(error))
        self._refresh()

    def _clear(self):
        self.tree.delete(*self.tree.get_children())
        self.summary_var.set('尚无已核验预览；不能导出。')
        self.tempo_text.configure(state='normal')
        self.tempo_text.delete('1.0', 'end')
        self.tempo_text.configure(state='disabled')

    def choose(self):
        try:
            if self.controller.select_file(self.chooser()):
                self.file_var.set(str(self.controller.source))
                self.status_var.set('已选择；请导入并核验后查看全部事件。')
                self._clear()
        except Exception as exc:
            self._error(exc)
        self._refresh()

    def preview(self):
        try:
            self.controller.preview(score_id=int(self.score_id_var.get()),
                                    session=int(self.session_var.get()),
                                    source_description=self.source_var.get(),
                                    license_note=self.license_var.get())
            self._clear()
            self.status_var.set('后台执行原编码与独立离线读回，最多90秒；可取消。')
        except Exception as exc:
            self._error(exc)
        self._refresh()

    def export(self):
        try:
            destination = self.directory_chooser()
            if not destination:
                self.status_var.set('导出选择已取消；没有创建输出。')
                return
            if not self.confirm(destination):
                self.status_var.set('未确认导出；没有创建输出。')
                return
            self.controller.export(destination, confirmed=True)
            self.status_var.set('重新核验输入与全部产物，导出到独占新目录。')
        except Exception as exc:
            self._error(exc)
        self._refresh()

    def cancel(self):
        self.controller.cancel()
        self.status_var.set('已请求取消；等待私有进程树有界退出，保留已有日志。')

    def _render(self, result):
        self._clear()
        self.summary_var.set(
            f"schema=1，score_id={result['score_id']}，session={result['session']}；"
            f"Type{result['midi_format']}，{result['tracks']}轨，PPQN={result['ppqn']}，sample_hz=48000；"
            f"{result['event_count']}/512事件，剩余{result['remaining']}；"
            f"最后事件={result['last_event_sample']}样本 / {result['last_event_seconds']}秒。\n"
            f"原文件 SHA256={result['input']['sha256']}\n"
            'track保留在来源表，不写入T057；通道/note/velocity保持原值。同刻按MIDI tick/轨/轨内序号稳定排序。'
        )
        lines = ['默认 tempo=500000 μs/quarter（120 BPM）']
        for item in result['tempo_map']:
            lines.append(f"MIDI tick={item['midi_tick']} track={item['track']} event={item['event_index']} "
                         f"tempo={item['us_per_quarter']} μs/quarter")
        self.tempo_text.configure(state='normal')
        self.tempo_text.insert('1.0', '\n'.join(lines))
        self.tempo_text.configure(state='disabled')
        for row in result['rows']:
            self.tree.insert('', 'end', iid=str(row['index']), values=(
                row['index'], row['track'], row['channel'], row['midi_tick'], row['sample_tick'],
                f"{row['sample_tick'] / 48000:.9f}", row['type'], row['note'], row['velocity'],
                f"{row['exact_sample_numerator']}/{row['exact_sample_denominator']}", row['record_hex']))

    def _refresh(self):
        busy = self.controller.state in ('loading', 'exporting') or self._closing
        self.choose_button.configure(state='disabled' if busy else 'normal')
        self.preview_button.configure(state='normal' if not busy and self.controller.source is not None else 'disabled')
        self.export_button.configure(state='normal' if not busy and self.controller.state == 'ready' else 'disabled')
        self.cancel_button.configure(state='normal' if busy and not self._closing else 'disabled')

    def _tick(self):
        if self._closing:
            return
        for item in self.controller.poll():
            if item['type'] == 'completed' and item['operation'] == 'preview':
                self._render(item['result'])
                self.status_var.set('离线逐条核同通过。请查看全部事件，再主动确认导出；未连接 FPGA。')
            elif item['type'] == 'completed':
                self.status_var.set('离线导出通过：' + item['result']['destination'] + '；不是 FPGA ACK 或发声。')
            else:
                self._clear()
                self.status_var.set(item.get('error', 'CANCELLED: 已取消，日志保留'))
        self._refresh()
        self._after = self.root.after(50, self._tick)

    def close(self):
        if self._closing:
            return
        self._closing = True
        if self._after is not None:
            self.root.after_cancel(self._after)
            self._after = None
        self.controller.close()
        self.status_var.set('正在停止本窗口拥有的后台进程；不会按进程名杀其他任务。')
        self._refresh()
        self._close_started = time.monotonic()
        self._finish_close()

    def _finish_close(self):
        if self.controller.wait_closed(timeout=0):
            self.root.destroy()
            return
        if time.monotonic() - self._close_started > 5:
            # Keep the UI visible: do not silently claim all workers stopped.
            self.status_var.set('后台清理超过5秒；日志保留，请检查process_receipt.json。')
        self.root.after(50, self._finish_close)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path,
                        default=ROOT / 'code/output' / ('score_midi_desktop_' + uuid.uuid4().hex))
    parser.add_argument('--input', type=Path, help='optional local selection only; does not auto-import/export')
    args = parser.parse_args(argv)
    controller = None
    try:
        controller = Controller(args.workspace)
        root = tk.Tk()
        app = DesktopApp(root, controller)
        if args.input is not None:
            controller.select_file(args.input)
            app.file_var.set(str(controller.source))
            app._refresh()
        root.mainloop()
        return 0 if controller.wait_closed(5) else 1
    except Exception as exc:
        if controller is not None:
            controller.close()
            controller.wait_closed(5)
        print(f'GUI_START_FAILURE: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
