# M3：138K / 40 MHz PCM→PT8211 联合验收

本轮只新增本目录和 `code/scripts/run_m3_clock40_pcm_serial_acceptance.py`。不改 L/I 原候选、正式 RTL、算法、顶层、公共包、CST/SDC、时钟、STAT、任务看板或当前状态；时序优化仍停止。M2 统一复核和登记，无新增任务编号。

## 冻结输入与运行

默认使用 `code/rtl/138K_try/hold_trials_20261005/M3_138K_Hold修复证据_20261005.zip`，整个 ZIP SHA-256 必须为：

```text
c4eeefac8c28e3ebc01475177601a65abfc0da6f314b1c80f94b223ee9fa5b50
```

仅从该封存 ZIP 提取 L_locations_guard065 的 56 个输入到新运行目录；I_hold_locations 是可显式选择的回退，不自动静默切换。提取件保留原字节，另生成仿真副本，仅重定向 ROM/include 路径。ModelSim 直接编译原 allocator/ADSR/发送器，不替换算术或寄存器结构。每份原源码、ROM、仿真副本和测试源的 SHA 见运行收据及 `source_manifest.json`。

只读复核时，当前工作区 `lfo_sine_q15.mem`、`oct_ratio_q16.mem`、`sub_ratio_q16.mem` 与 ZIP 的原字节 SHA 不同，但逐字核对只差 LF/CRLF；其余 53 个输入原字节一致。此差异不是本轮修改，运行仍固定使用 ZIP 原件，不用工作区 ROM 替代或掩盖原 SHA 差异。

在仓库根目录执行（Python 3.10+，本轮实际 Python 3.12；ModelSim SE-64 2020.4）：

```powershell
python -B -X utf8 code/scripts/run_m3_clock40_pcm_serial_acceptance.py --repo-gate
```

异机指定封存包和工具位置：

```powershell
python -B -X utf8 code/scripts/run_m3_clock40_pcm_serial_acceptance.py --archive X:/delivery/M3_138K_Hold修复证据_20261005.zip --modelsim-bin X:/modelsim/win64 --repo-gate
```

回退输入使用 `--candidate I_hold_locations`。本轮实际正负例使用 L，未运行 I 回退。

运行器所有新产物在本目录忽略的 `runtime/run_*` 内，旧运行不会覆盖。含原日志、完整捕获、只读提取件、变异副本、工具命令/退出码及 SHA 收据。没有 ZIP 精简任务或新的 Gowin 构建。

## 检查方法

正常 harness 按封存顶层的音频接线，使用 25 ns 周期的真实 40 MHz 域刺激，连接封存 UART 31250 8N1、MIDI parser、32 深度公共 FIFO、四声部音频核心及实际 i2s_tx。没有把该 harness 冒称整机顶层/PLL 的新验证。

`serial_capture.sv` 在真实 BCLK 上升沿采 DIN，以实际 WS 翻转划分半帧，启动只明确丢弃不完整的复位半帧。完整半帧必须 32 个上升沿，WS 低为右、高为左，前 16 位填充为零，最后 16 位 MSB→LSB；LSB 是 WS 翻转前最后一个上升沿。它只捕获引脚和模块边界握手，不访问移位寄存器、sample_left/right、内部槽计数或 DUT 舍入函数。

Python 独立从 PCM valid/ready 的 PCM24 和请求 ID 建立 pending/held 队列，每次 frame_tick 核对真实 play_left/right 采用记录及帧/提交/欠载计数，然后按物理 WS 低半帧开始时间把完整左右串行样本关联到该次采用。检查 ID、逐帧顺序、两声道匹配及非空覆盖；相同数值允许正常重复，不把数值相同误当重复事务。

黄金转换为 `clamp((signed_pcm24 + 128) // 256, -32768, 32767)`。Python floor division 对应有符号算术右移；半 LSB 向正无穷取整，不改成对称舍入。期望值只来自真实 PCM 握手和独立缓冲模型，不能从 DUT 移位数据反推。

正常场景通过 24 个实际 UART 字节触发四个不同音符，再逐个 Note Off，保持批准的 4800 样本 Release，不缩短算法时间。独立记录各槽 Release mask 为 1/3/7/15、占用为 15，最后声部全部释放且 PCM 归零。诊断场景另用明确标注的 PCM 夹具驱动原 pcm_frame_buffer+i2s_tx，覆盖左右不同值、正负、±半 LSB、正饱和及负满量程边界；夹具不能算成正常音乐样本。

## 实际验收结果

- 正常：5848 个完整立体声帧，11696 次声道比较，5849 次真实 PCM 握手；松键前 299 帧四声部、最后松键后 4967 帧尾音/归零，欠载 0。
- 诊断：40 个完整立体声帧、80 次声道比较；连续第 14/15/16 采用帧欠载，保持上一组左右样本，计数从 0 恰增到 3；第 17 帧采用新数据。覆盖 15 个指定边界值。
- BCLK 长窗口平均周期正常 325.520789 ns、诊断 325.520833 ns，符合 3.072 MHz。
- 两个错误实现均实际编译成功、仿真运行完成，再由独立检查器拒收：LOAD_SLOT 提前一位（LSBJ 填充/位对齐错误）；play_left/right 强制采用 held 旧帧（第 2 帧错误采用）。变异仅生成在本次 runtime 内。
- 18 项整数边界/非法范围检查及 15 项捕获损坏反例通过。空捕获、缺完成标记、零串行比较、缺握手/采用/计数、错误 ID/样本、31 位槽、未知位、缺四声部/Release/欠载证据等均拒收。超时或工具失败一律非 PASS。

仓库门禁的旧脚本固定写 `code/output`，本轮禁止这种正式目录写入。因此 `--repo-gate` 使用新测试目录内的仓库快照，先恢复并验证所有跟踪文件和本轮新文件与工作区原字节 SHA 一致，再执行**未修改的 check_repo.ps1**。运行收据明确标为 `content-exact isolated snapshot`，不冒称在原工作区直接运行。临时长路径配置只用于克隆副本，不改原 Git 配置。门禁结果以最终 `receipt.json` 和原 `check_repo` 日志为准，早期环境/路径失败原日志保留，不计通过。

九组门禁全部 PASS、退出 0；最终运行目录以 `evidence/receipt.json` 为准。正式工作区没有该门禁的 `code/output` 写入。

## 原证据复查与边界

交付证据在 `evidence/`：源清单、运行收据、正负例编译/仿真原日志及原捕获。原工具输出包含 CRLF 和尾空格，直接提交会受 Git LF 规范影响；因此用 `.b64` 无损编码，`raw_manifest.json` 记录原字节长度/SHA。Base64 解码后的原数据与运行收据哈希完全一致，不裁剪日志、不把规范化后的文本冒称原字节。正常原捕获约 1.38 MB，是逐样本复核必需证据，不是波形数据库或码流。可离线直接重算编码捕获：

```powershell
python -B -X utf8 code/scripts/run_m3_clock40_pcm_serial_acceptance.py --check-capture code/tb/audio_out/m3_clock40_pcm_serial_acceptance/evidence/normal_capture.b64 --scenario normal
python -B -X utf8 code/scripts/run_m3_clock40_pcm_serial_acceptance.py --check-capture code/tb/audio_out/m3_clock40_pcm_serial_acceptance/evidence/diagnostic_capture.b64 --scenario diagnostic
```

查看未裁剪的原门禁日志（其他原日志同理）：

```powershell
python -B -X utf8 code/tb/audio_out/m3_clock40_pcm_serial_acceptance/publish_evidence.py --decode code/tb/audio_out/m3_clock40_pcm_serial_acceptance/evidence/check_repo.b64
```

重新交付某次已全通过运行，用 `publish_evidence.py --run <本目录下 runtime/run_* 的绝对路径>`；它先检查通过收据、原字节 SHA 和 Base64 往返，证据目录必须尚不存在，不能覆盖已有交付。

离线重算不是新的 RTL 仿真；新一轮 RTL 运行需封存 ZIP 和 ModelSim。错误实现捕获用同一入口必须返回非零。

本轮等级 L2 自检仿真、L3 仅 PCM24→PCM16 独立数学/串行比较。没有新增 L4/L5、布线后仿真、自动启动或 PLL 恢复、电气/模拟音频、PT8211 模拟幅度/失真、实屏、板卡、烧录或长期整机验证。不改共享文档；提交后由 M2 复核登记，交接状态待用户转发、尚未送达。
