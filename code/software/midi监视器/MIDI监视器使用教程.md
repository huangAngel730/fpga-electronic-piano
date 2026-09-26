# 队伍 MIDI 监视器使用教程

## 1. 这个工具用来做什么

这个程序是电子琴项目 T036 的电脑端 MIDI 证据采集工具。它直接读取 Windows 识别到的
USB MIDI 输入设备，适合核对 MIDIPLUS X4 III 实际发出的消息。

它能显示：

- Note On 和 Note Off；
- 音符编号以及 C4、A4 这类音名；
- MIDI 通道；
- Velocity 力度；
- Pitch Bend 弯音；
- Modulation（CC1）；
- Sustain 延音踏板（CC64）；
- Poly Pressure 和 Channel Pressure；
- 每条消息的原始十六进制字节；
- 当前按住的琴键、本次力度最小值和最大值；
- 可供复核的 CSV 日志。

它只负责观察 MIDI，不生成正式音频，也不能代替 FPGA 上板验收。

## 2. 文件位置

```text
code/software/midi监视器/midi_monitor.py
code/software/midi监视器/midi_monitor_gui.py
code/software/midi监视器/requirements-midi.txt
code/software/midi监视器/resolve_midi_python.cmd
code/software/midi监视器/install_midi_monitor_dependencies.cmd
code/software/midi监视器/安装MIDI监视器依赖.cmd
code/software/midi监视器/open_midi_monitor.cmd
code/software/midi监视器/打开MIDI监视器.cmd
code/software/tests/test_midi_monitor.py
```

前七个程序文件在 `midi监视器` 文件夹中；自动测试仍保留在仓库统一的
`code/software/tests` 目录。

## 3. 第一次使用：安装依赖

电脑需要 Python 3。最简单的方法是在资源管理器中双击：

```text
安装MIDI监视器依赖.cmd
```

安装器会优先寻找当前用户的 Miniconda/Anaconda，再寻找普通 Python 3，不会误用 Python 2。
本电脑目前会自动选中：

```text
C:\Users\songdongkuan\miniconda3\python.exe
```

如果安装失败，窗口会保留 `pip` 给出的具体错误，不再只显示笼统的“安装失败”。

安装的是：

- `mido`：把原始 MIDI 消息整理成 Note、CC、Pitch 等类型；
- `python-rtmidi`：读取 Windows 的真实 USB MIDI 端口。

Tkinter 随大多数 Windows Python 安装提供，不需要安装 PyQt。

如果依赖没有安装，程序仍然可以打开并使用“模拟模式”，但不能读取真实键盘。

## 4. 一键打开

在资源管理器中进入：

```text
E:\FPGA\GAOYUNFPGA\team\fpga-electronic-piano\code\software\midi监视器
```

双击：

```text
打开MIDI监视器.cmd
```

也可以在 PowerShell 中运行：

```powershell
& 'C:\Users\songdongkuan\miniconda3\python.exe' -X utf8 .\midi_monitor_gui.py
```

## 5. 没有键盘时先试界面

点击“模拟模式”。程序会循环显示：

- C4 轻按；
- E4 正常按；
- G4 重按；
- Mod（CC1）；
- Pitch Bend；
- 延音踏板按下和松开。

模拟模式只能证明软件界面和 CSV 工作，不能证明 X4 III 或 FPGA 已经通过。

## 6. 连接 X4 III

1. 给 X4 III 正常供电。
2. 用支持数据传输的 USB 线连接键盘与电脑。
3. 等待 Windows 完成设备识别。
4. 打开 MIDI 监视器。
5. 点击“刷新”。
6. 在“MIDI输入设备”中选择名称包含 X4 III、MIDIPLUS 或 USB MIDI 的设备。
7. 点击“连接”。
8. 状态栏显示“已连接”后再弹奏。

如果列表为空：

- 检查 USB 线是否只有充电功能；
- 换电脑上的另一个 USB 口；
- 检查键盘是否开机；
- 在 Windows 设备管理器中确认是否出现 MIDI/音频设备；
- 关闭可能独占 MIDI 端口的编曲软件后重新刷新。

## 7. 实际例子：抓取中央 C

按下中央 C 时，表格可能显示：

```text
类型       通道  音符  力度  原始字节
note_on      1   C4    100   90 3C 64
```

含义：

- `90`：MIDI 通道 1 的 Note On；
- `3C`：十六进制 60，即中央 C；
- `64`：十六进制 100，即力度 100。

松开时可能显示：

```text
note_off     1   C4     40   80 3C 28
```

有些键盘使用 `90 3C 00` 表示松开。程序会自动把“Note On 且力度为 0”显示成
`note_off`，两种写法都算正常。

## 8. 力度测试

对同一个琴键做三次测试：

1. 很轻地按；
2. 正常力度按；
3. 较重地按。

例如看到：

```text
轻按：24
正常：72
重按：114
```

不要求与你得到的数字完全相同。验收重点是：力度不是永远固定，而且总体上重按数值高于轻按。

注意：这个结果只证明 X4 III 发出了力度消息。声音大小是否随力度变化，要等 FPGA 正式音源使用
Velocity 后再验收。

## 9. Pitch、Mod 和延音踏板测试

### Pitch Bend

滑动 Pitch 触控条，观察蓝色 Pitch Bend 条。中心值应回到 0，两个方向分别出现正值和负值。

### Modulation

滑动 Mod 触控条，观察 `Modulation · CC1`。常见范围是 0 至 127，但以真实抓取结果为准。

### Sustain

踩下延音踏板时查看是否出现 `Sustain Pedal (CC64)`。程序按照通用 MIDI 规则显示：

- 数值小于 64：OFF；
- 数值大于或等于 64：ON。

是否支持连续半踏不能只看一次消息下结论，必须观察踏板行程中是否出现多个不同数值。

## 10. 保存正式 CSV

1. 点击“开始CSV”。
2. 选择保存目录和文件名。
3. 完成一组测试。
4. 点击“停止CSV”。

推荐命名：

```text
T036_X4III_note_velocity_2026-09-25.csv
T036_X4III_pitch_mod_sustain_2026-09-25.csv
```

CSV 使用 UTF-8 with BOM，Windows Excel 可以直接打开中文说明。CSV 始终记录全部消息；界面的过滤按钮
只控制表格显示，不会把被隐藏的消息从证据文件中删除。

正式记录同时写明：

- 日期；
- 键盘当前 MIDI 通道；
- 八度和移调设置；
- 使用的 USB 线；
- 程序对应的 Git 提交号；
- 哪些项目通过，哪些尚未验证。

## 11. 安装器自检

如果只想确认安装器找到了哪个 Python，而不下载软件包，可以在本目录运行：

```powershell
.\install_midi_monitor_dependencies.cmd --check
```

看到 `C:\Users\songdongkuan\miniconda3\python.exe` 和 Python 3 版本号，说明查找正常。

## 12. 自动测试

不需要真实键盘。先进入 `midi监视器` 目录，再运行：

```powershell
& 'C:\Users\songdongkuan\miniconda3\python.exe' -X utf8 -m unittest discover -s ..\tests -p test_midi_monitor.py -v
```

测试覆盖音符名称、通道、力度为 0 的 Note Off、CC1、CC64、Pitch Bend、当前按键统计、
力度范围、模拟消息和 CSV 追加。

## 13. 当前验证边界

- USB MIDI 只能验证“X4 III 到电脑”的消息，不能单独证明 DIN、光耦、R17 和 FPGA 链路正常。
- 正式 FPGA 输入仍需用逻辑分析仪在隔离/电平转换后的 R17 数字线上抓取，或使用通过复核的 FPGA 状态/回传功能。
- 当前单声部占位码流不能用于验收四复音、力度控制音量、延音声音效果或 Pitch/Mod 声音效果。
- 不要把 MIDI 五针 DIN 电流环直接接到 FPGA 或普通 USB-UART。
