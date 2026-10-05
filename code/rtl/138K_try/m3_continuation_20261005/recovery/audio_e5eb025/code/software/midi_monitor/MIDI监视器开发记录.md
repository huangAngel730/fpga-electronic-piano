# 队伍 MIDI 监视器开发记录

## 日期与任务

- 日期：2026-09-25
- 任务：T036 X4 III MIDI 交互实测的电脑端消息采集工具
- 负责人：M3
- 复核人：M2
- 当前验证等级：L1/L2（软件静态检查、单元测试和隐藏窗口冒烟；没有真实键盘联调）

## 本次实现的整体功能

程序从 Windows USB MIDI 输入端口接收消息，把原始字节整理成适合项目验收阅读的内容：

```text
X4 III USB MIDI
    -> python-rtmidi 获取系统端口
    -> mido 形成 MIDI Message
    -> describe_midi_message 统一解释
    -> MidiStatistics 更新统计
    -> Tkinter 卡片、琴键、仪表和消息表格
    -> 可选 CsvMidiLogger 保存证据
```

没有键盘时，`simulation_messages` 产生固定示例并走同一套解释、显示和 CSV 路径。

## 生成的文件

所有程序文件均位于 `E:\FPGA\GAOYUNFPGA\team\fpga-electronic-piano\code\software\midi_monitor`：

| 文件 | 作用 |
|---|---|
| `midi_monitor.py` | 与界面无关的消息解释、统计、模拟消息和 CSV 保存 |
| `midi_input_worker.py` | 后台打开、轮询和关闭 RtMidi 端口，向 GUI 队列发送消息与健康状态 |
| `midi_monitor_gui.py` | Tkinter 图形界面、USB MIDI 设备连接和实时显示 |
| `requirements-midi.txt` | 声明 `mido` 与 `python-rtmidi` 依赖 |
| `resolve_midi_python.cmd` | 查找并验证 Python 3.9 以上解释器，优先使用当前用户的 Miniconda/Anaconda |
| `install_midi_monitor_dependencies.cmd` | 纯 ASCII 的依赖安装入口 |
| `安装MIDI监视器依赖.cmd` | 给使用者双击的一键安装入口 |
| `open_midi_monitor.cmd` | 纯 ASCII 的可移植启动入口 |
| `打开MIDI监视器.cmd` | 给使用者双击的中文入口，转调 ASCII 启动器 |
| `MIDI监视器使用教程.md` | 安装、连接、示例、CSV和故障处理教程 |
| `tests/test_midi_monitor.py` | 不依赖真实键盘的自动测试 |
| `MIDI监视器开发记录.md` | 本文件 |

## 主要模块、类和方法

### `midi_monitor.py`

- `MidiEvent`：一条已经解释的消息。重要字段包括时间、消息类型、通道、音符编号、音名、
  力度、控制器编号、控制值、Pitch值、原始十六进制和中文说明。
- `midi_note_name(note)`：把0至127的MIDI音符编号转换成音名，例如60转换为C4。
- `describe_midi_message(message)`：识别Note On、Note Off、Velocity=0松键、CC、Pitch、
  Poly Pressure、Channel Pressure、Program Change和系统消息。
- `MidiStatistics`：维护消息总数、Note On/Off数量、当前按住的`active_notes`集合、力度
  最小/最大值、Mod、Sustain和Pitch当前值。
- `CsvMidiLogger`：使用UTF-8 with BOM追加CSV；已有文件不覆盖，表头只写一次。
- `simulation_messages()`：产生Note、三档力度、CC1、CC64和Pitch示例。

### `midi_monitor_gui.py`

- `MidiMonitorApp`：程序主控制器，负责设备刷新、连接、断开、模拟模式、CSV、消息队列和退出清理。
- `MetricCard`：显示最后音符、力度、按住琴键、通道、力度范围和消息总数。
- `ValueMeter`：显示Velocity、Mod、Sustain和有正负方向的Pitch Bend。
- `PianoStrip`：显示C2至C6琴键，当前按住琴键高亮，最后音符使用另一颜色提示。
- `event_queue`：后台接收线程不直接修改Tkinter控件，而是把消息送入队列，由GUI主线程分批读取，
  避免跨线程更新界面和消息过多时长期占住主线程。
- `input_worker`：当前MIDI后台接收器；打开、轮询和关闭端口均在同一后台线程执行。
- `csv_logger`：未开始保存时为`None`，开始CSV后每条消息立即写盘。
- `simulation_job`：Tkinter定时任务编号，用于可靠停止模拟消息。

## 输入与输出

### 输入

- Windows识别到的USB MIDI输入设备；
- MIDI 1.0消息，包括Note、CC、Pitch、触后压力及系统消息；
- 用户的设备选择、连接、过滤、模拟和CSV操作。

### 输出

- 屏幕状态卡片、琴键高亮、数值仪表和最多500行实时表格；
- CSV字段：`timestamp`、`event_type`、`channel`、`note`、`note_name`、`velocity`、
  `controller`、`controller_name`、`value`、`pitch`、`raw_hex`、`description`。

本工具没有FPGA端口，不使用50 MHz时钟、复位、R17或CST。它验证的是键盘到电脑的USB MIDI消息；
DIN、光耦、R17和FPGA链路必须另外实测。

## 状态与异常处理

程序没有复杂状态机，主要运行状态为：

1. 未连接；
2. 找到设备但未打开；
3. 已连接真实USB MIDI；
4. 模拟模式；
5. 连接或接收错误；
6. 端口中断后自动重连；
7. 退出时立即停止界面，端口由后台线程关闭，CSV正常收尾。

缺少`mido`或`python-rtmidi`时界面仍可打开模拟模式，并明确显示安装命令。设备为空、端口被占用、
CSV不能写入或消息解释异常时均提示错误，不让程序直接崩溃。

## Testbench等价的软件测试情况

`tests/test_midi_monitor.py`共12项，覆盖：

1. C-1、C4、A4、G9音名边界；
2. 非法音符编号拒绝；
3. Note On的通道、音符、力度与原始字节；
4. Note On且Velocity=0自动解释为Note Off；
5. CC1和CC64名称与延音开关；
6. Pitch Bend有符号数值；
7. 当前按键集合和力度范围；
8. Mod、Sustain、Pitch状态；
9. 模拟消息覆盖T036所需类型；
10. CSV关闭后重开继续追加且不重复表头。
11. Velocity 取值1、24、64、100、127时均原样保留并与原始第三字节一致；
12. 后台接收器能连续轮询消息，`stop()`非阻塞，端口最终关闭。

## 实际运行的检查与结果

- 三个Python文件`py_compile`：PASS，退出码0。
- 新增MIDI测试：12/12 PASS。
- `code/software/tests`全部软件测试：38/38 PASS。
- 隐藏Tkinter窗口实例化完整`MidiMonitorApp`并送入一条C4力度24消息：
  `GUI_SMOKE_PASS 1 C4 24`。
- `git diff --check`：PASS，退出码0。
- `code/scripts/check_repo.ps1`：9/9 PASS，退出码0；包括Python语法、引脚资料检查及T007/T019回归。

## 2026-09-25 安装启动故障修复

- 故障原因：原安装器只运行 `where python`，首先命中旧的
  `D:\program\anaconda2\python.exe`，却不会寻找可用的
  `C:\Users\songdongkuan\miniconda3\python.exe`。
- 修复方法：安装器和 UI 启动器统一调用 `resolve_midi_python.cmd`，候选解释器必须实际运行并且版本不低于 Python 3.9。
- 可诊断性：安装时先显示选中的绝对路径和版本；如果 `pip` 失败，保留真正的错误输出。
- 移动适配：启动器继续使用 `%~dp0` 定位同目录文件，因此整个 `midi_monitor` 文件夹移动后仍可工作。
- 实际结果：安装器选择 `C:\Users\songdongkuan\miniconda3\python.exe`（Python 3.12.4）；
  `mido 1.3.3` 与 `python-rtmidi 1.5.8` 已安装，导入检查通过。
- 界面检查：带真实 RtMidi 后端创建隐藏窗口成功，显示“未发现MIDI设备”，程序正常退出。
- 移动后单元测试：从 `midi_monitor` 目录运行父目录中的测试，10/10 PASS。

## 2026-09-26 真实键盘稳定性修复

- 用户实测问题：Note On力度始终100；关闭窗口短暂卡住；连接一段时间后停止显示消息。
- 力度核查：`describe_midi_message()`始终读取消息自身的`velocity`，不存在固定100的赋值；新增
  1、24、64、100、127五档自动测试，解析值和原始第三字节全部一致。连续8次收到同一力度时，
  界面提示检查X4 III的`VEL=Fixed`设置，但绝不改写原始数据。
- 接收修复：移除RtMidi回调模式，新增`MidiInputWorker`后台线程；端口的打开、非阻塞`poll()`、
  心跳和关闭都由同一线程负责。驱动停止后约1秒自动重连。
- 界面修复：每轮最多处理100条队列消息，剩余消息下一轮立即处理，避免消息洪峰令Tk主线程
  长时间无法响应。
- 关闭修复：关闭按钮只设置停止事件，不再从GUI主线程同步调用驱动`close()`；隐藏窗口实测
  `GUI_CLOSE_SECONDS=0.0261`，退出码0。
- 环境实测：Windows/RtMidi当前枚举到`X4III 0`与`MIDIIN2 (X4III) 1`；没有自动打开或修改
  第二路端口。
- 真实端口冒烟：后台线程成功打开`X4III 0`并保持心跳，2.2秒后状态仍为“已连接”；关闭界面
  耗时0.0270秒，150毫秒后后台线程已退出且端口已关闭。
- 实际检查：3个Python文件`py_compile`通过；MIDI专用测试12/12通过；真实键盘重新弹奏验证待用户执行。

## 尚未验证的问题

- 已识别并枚举X4 III；用户已看到Note消息，但本次修复后的长时间接收、可变Velocity和关闭手感仍需重新实测。
- 尚未保存并复核真实Note、Velocity、Pitch、Mod、SUS CSV证据。
- 未测试Windows设备在其他音乐软件占用时的实际错误文字。
- 未在多种Windows缩放比例与显示器分辨率下人工检查布局。
- USB消息不能代替DIN/光耦/R17/FPGA链路测试。
- 未执行Git提交或推送；编号应按团队规则在推送前最后一步由合入者取得。

## 使用者下一步

1. 安装`requirements-midi.txt`；
2. 双击`打开MIDI监视器.cmd`；
3. 先运行模拟模式；
4. 连接X4 III USB并刷新设备；
5. 分别采集Note/Velocity与Pitch/Mod/SUS两份CSV；
6. 把CSV、接线/设置说明和Git提交号一并交给M2复核。
