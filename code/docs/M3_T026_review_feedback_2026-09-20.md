# M2 给 M3 的 T026 复核返工反馈（2026-09-20）

接收人：M3（实体硬件、交互与上板验证负责人）

复核人：M2

复核对象：提交 `e501511`（T026 UART 状态监视上位机）

复核基线：`develop` 提交 `97739e2`

## 结论

T026 的解析器、模拟模式和 CSV 基础功能可用，但当前只能判定为**部分通过（L1/L2 软件测试）**，
不能标记为完成。原 `code/docs/test/T026_上位机复核记录.md` 由 M1 写成“复核通过”，不符合
D025“复核统一归 M2”的现行规则，而且真实串口和真实 FPGA 状态行尚未验证。

本次独立实跑结果：

```text
.\code\scripts\run_t026_tests.ps1
→ FAIL：Python executable not found

.\code\scripts\run_t026_tests.ps1 -PythonExe D:\ProgramData\anaconda3\python.exe
→ 14 tests PASS
→ 3 条模拟状态冒烟 PASS
→ 退出码 0

python -X utf8 uart_status_monitor.py --simulate --count 4 --interval 0 --log <临时CSV>
→ 4 条有效记录，CSV 表头和数据正确，退出码 0
```

## P1：本轮需要修复

### 1. README 规定的默认测试命令在项目当前环境失败

`run_t026_tests.ps1` 和 `run_t026_gui.ps1` 只自动搜索：

- `%USERPROFILE%\miniconda3\python.exe`
- `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`

本项目当前实际 Python 是 `D:\ProgramData\anaconda3\python.exe`，另有 Python 3.13，故 README 中
不带参数的标准命令直接失败。验收脚本不能依赖某位队员的安装目录。

整改要求：

- 优先使用显式 `-PythonExe`；未提供时应通过 `Get-Command python` 或 `py` 启动器发现解释器。
- 保留对常见固定路径的兼容，但不能把它们作为唯一选择。
- `run_t026_tests.ps1` 与 `run_t026_gui.ps1` 使用同一套发现逻辑。
- 增加自动测试或最小冒烟，证明默认命令在项目标准环境中可运行。

### 2. 真实 COM 口路径没有完成验收

本机 Anaconda Python 3.13.5 和独立 Python 3.13.7 均未安装 `pyserial`：

```text
python -X utf8 uart_status_monitor.py --list-ports
→ ERROR: live serial mode needs pyserial
→ 退出码 2
```

这不是解析器错误，但说明 T026 的“列出并连接指定 COM 口”验收尚未执行。

整改要求：

- 增加明确、可重复的依赖声明，例如 `requirements.txt` 或项目环境安装步骤。
- 安装依赖后实跑 `--list-ports`，保存实际枚举结果。
- 至少对一个真实 COM 口验证打开、读取、停止和异常断开恢复。
- 不得把 fake serial 单元测试写成真实串口通过。

### 3. 自动测试没有覆盖任务看板中的全部验收条件

当前 14 个测试覆盖了解析、错误行继续处理、模拟数据、CSV 单行写入和一个 fake serial
停止回调；没有覆盖：

- `list_serial_ports()` 的有端口、无端口和缺依赖路径。
- CLI 真实模式必填参数与非法参数退出码。
- 串口打开失败、读取中断和非 ASCII 数据。
- GUI 的串口枚举、连接参数校验和连接失败恢复。
- 连续 CSV 追加及程序重启后再次追加。

请补足上述自动测试，至少保证异常路径不会崩溃且退出码可用于批处理判断。

## P2：文档和一致性修正

### 4. README 含个人电脑绝对路径

`code/software/README.md` 给出的直接运行示例使用
`C:\Users\songdongkuan\miniconda3\python.exe`。请改为通用的 `python -X utf8 ...`，或说明通过
`-PythonExe` 传入本机绝对路径，不要把个人用户名写入项目标准命令。

### 5. GUI 参数校验弱于 CLI

CLI 已限制数据位、校验位和停止位的合法集合；GUI 目前只检查它们能否转成数字，没有限制：

- 数据位必须为 5/6/7/8。
- 校验位必须为 N/E/O/M/S。
- 停止位必须为 1/1.5/2。

请复用核心参数校验函数，避免 CLI 和 GUI 对同一输入给出不同结果。

### 6. T025 协议尚未实现，不能宣称真实协议已通过

接口规范已列出七个状态字段，但 T025 的 FPGA 发送器、串口参数、文本前缀和实际状态计数器仍未
实现。T026 当前严格要求 `STAT` 前缀和七字段完整出现，只能作为候选协议实现。

M3 不要自行改动状态字段或冻结串口协议。等 M2 完成 T025 后，双方按同一份真实输出更新：

- 波特率、数据位、校验位、停止位。
- 文本前缀和字段格式。
- 真实开发板状态行解析。
- 真实 CSV 日志证据。

## 返工验收条件

M3 推送修复前应完成：

1. 默认执行 `.\code\scripts\run_t026_tests.ps1` 成功，不需要个人路径参数。
2. 自动测试覆盖上述脚本、CLI、串口异常和 GUI 参数校验缺口。
3. README、教程和启动脚本不含个人用户名或机器专用 Python 路径。
4. `check_repo.ps1` 全部 PASS。
5. 仅暂存本次明确修改的文件，禁止使用 `git add -A`。
6. 直接推送 `develop`，完成后把提交哈希、测试命令、输出摘要和验证等级反馈给 M2。

真实 FPGA 联调依赖 T025，可在软件返工通过后继续保持 T026“进行中”，直到取得真实状态行和
CSV 日志证据。M2 将按 D025 对 M3 的修复推送进行复核。
