# M3 可视化画面模块

本目录只负责“画什么”，不负责 HDMI 时钟、跨时钟域、TMDS、正式顶层或引脚约束。

## 文件作用

- `visual_live_state.sv`：接收 M2 已跨到视频域的演奏事件，维护琴键高亮和上飘音符。
- `visual_score_tracker.sv`：接收由 M1 曲谱时间量化得到的帧号，维护下落音符和 Hit/Miss。
- `visual_scene_renderer.sv`：根据场景状态和像素坐标生成 RGB。
- `m3_visualizer.sv`：供 M2 正式显示链路接入的封装。

## 与 M2 对接

```text
visual_event_bridge.video_valid  -> m3_visualizer.event_valid
visual_event_bridge.video_data   -> m3_visualizer.event_data
m3_visualizer.event_ready        -> visual_event_bridge.video_ready
visual_event_bridge.video_desync -> m3_visualizer.video_desync
video_scan_timing.pixel_x/y      -> m3_visualizer.pixel_x/y
video_scan_timing.data_enable    -> m3_visualizer.data_enable
video_scan_timing.frame_start    -> m3_visualizer.frame_start
m3_visualizer.rgb_r/g/b          -> M2 HDMI/DVI 发送端 RGB
```

失步后模块仍保持 `event_ready=1`，避免显示反压音频；下一帧清空不可信的键态和动画，并显示红色告警条。共享复位后才能恢复。

## 与 M1 对接

M1 模型以秒表示时间，加载前按 M2 最终模式的真实刷新率量化：

```text
score_hit_frame       = round(hit_time_seconds * refresh_hz)
score_duration_frames = round(duration_seconds * refresh_hz)
```

同时传入 `note_id`、`note_number`、`duration_valid` 和 10 位 `velocity`。例如 60 Hz 下，5 秒对应第 300 帧；默认提前 2 秒即 `PREVIEW_FRAMES=120`，第 180/240/300 帧分别位于顶部/中点/判定线。

当前 M2 原型约 59.5238 Hz，尚不是冻结规格，接入时必须按最终真实刷新率重新量化。

## 模式与验证

- `display_mode=0`：实时琴键和上飘音符。
- `display_mode=1`：曲谱下落、Hit/Miss 颜色和琴键反馈。
- `mode_toggle_pulse` 在下一次 `frame_start` 整帧切换模式。

仿真命令：

```powershell
.\code\scripts\run_m3_visualizer_sim.ps1
```

预期最后输出 `M3 visualization regressions: ALL PASS`。当前只做模块仿真，不代表已经综合、布局布线或实屏出图。
