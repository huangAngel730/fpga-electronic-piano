# T026 UART 状态监视上位机雏形

`uart_status_monitor.py` 是电子琴项目 T026 的 Python 上位机雏形。它负责接收、严格解析、显示并可选保存 FPGA 通过 UART 发出的状态文本。T025 尚未实现，当前 `STAT` 七字段格式只是待双方联调的候选格式，不代表真实协议已冻结。

详细中文教程和示例见：[串口使用教程和示例](串口使用教程和示例.md)。

在 Windows 资源管理器中双击 [`打开串口调试助手.cmd`](打开串口调试助手.cmd)，可以一键打开图形界面。

当前 T025（FPGA 端 UART 状态输出）尚未完成，因此本工具先提供模拟模式。真实串口模式不会猜测串口号或串口格式，必须由使用者明确传入全部参数。

## 图形界面

`uart_status_gui.py` 是基于 Python 自带 Tkinter 的桌面界面，不需要安装 PyQt 或网页框架。它提供：

- 七个固定状态字段的实时卡片。
- 复音数与事件 FIFO 水位趋势图。
- 串口刷新、选择、连接、停止和模拟模式。
- 有效数据、格式错误和运行错误日志。
- 溢出、欠载和削波计数提示。
- 选择 CSV 文件并持续追加记录。

在仓库根目录运行：

```powershell
.\code\scripts\run_t026_gui.ps1
```

也可以直接运行：

```powershell
python -X utf8 .\code\software\uart_status_gui.py
```

打开后可以直接点击“模拟模式”观察界面。连接开发板前，必须根据 T025 最终协议填写波特率、数据位、校验位和停止位；界面不会填入未经确认的默认硬件参数。

## 状态行格式

每行以 `STAT` 开头，后面包含七个固定的 `key=value` 字段：

```text
STAT active_voice_count=4 clip_count=0 event_fifo_level=2 event_fifo_high_watermark=4 event_fifo_overflow=0 audio_underrun=0 max_processing_cycles=910
```

字段可以改变排列顺序，但不能缺失、重复或增加未知字段。数值允许使用十进制或 `0x` 开头的十六进制，范围为 32 位无符号整数。

七个字段的含义：

- `active_voice_count`：当前正在发声的复音数量。
- `clip_count`：音频削波累计次数。
- `event_fifo_level`：事件 FIFO 当前占用量。
- `event_fifo_high_watermark`：事件 FIFO 历史最高占用量。
- `event_fifo_overflow`：事件 FIFO 溢出累计次数或标志值。
- `audio_underrun`：音频欠载累计次数或标志值。
- `max_processing_cycles`：一次音频处理使用过的最大时钟周期数。

## 模拟模式

不连接开发板也可以先验证解析、显示与 CSV 记录：

```powershell
python -X utf8 uart_status_monitor.py --simulate
python -X utf8 uart_status_monitor.py --simulate --count 4 --interval 0 --log status.csv
```

模拟模式在未指定 `--count` 时输出八条有效记录后结束。

## 真实串口模式

真实串口读取依赖 `pyserial`。在仓库根目录使用同一个 Python 安装并运行：

```powershell
python -m pip install -r .\code\software\requirements.txt
python -X utf8 .\code\software\uart_status_monitor.py --list-ports
python -X utf8 .\code\software\uart_status_monitor.py --port COM5 --baud 115200 --bytesize 8 --parity N --stopbits 1 --log status.csv
```

上面的 `COM5`、`115200` 和 `8N1` 只用于展示命令写法，不是本项目已经确认的硬件参数。现有资料尚未冻结 T025 的串口格式，因此真实模式要求显式填写串口、波特率、数据位、校验位和停止位，必须等 T025 明确协议后使用实际参数。

按 `Ctrl+C` 可以停止持续监视。格式错误的行会输出 `PARSE_ERROR`，监视器会继续读取后续数据。

## 自动检查

在仓库根目录运行：

```powershell
.\code\scripts\run_t026_tests.ps1
```

也可以显式指定 Python：

```powershell
.\code\scripts\run_t026_tests.ps1 -PythonExe "<本机 Python 可执行文件的完整路径>"
```

两个 PowerShell 脚本共用解释器发现逻辑：先使用显式 `-PythonExe`，否则依次尝试命令 `python`、`py` 和常见安装位置。脚本依次执行语法编译、单元测试和三条模拟状态的冒烟测试。为避免修改或清理工程文件，测试脚本把 T026 文件复制到新的系统临时目录中运行，且不会删除该临时目录。

当前自动测试只验证软件逻辑（L1/L2）。真实 COM 口打开、断开恢复、FPGA 状态行和 CSV 日志仍需在有设备且 T025 完成后单独验收；不要把模拟或假串口测试当作上板通过。
