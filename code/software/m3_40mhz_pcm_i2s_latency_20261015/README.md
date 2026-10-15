# 包 C：40 MHz PCM／PT8211 公开端口数字证据

2026-10-16 收尾；仅 M3 新隔离模块夹具，不是 R05 真链、正式四音整机或实物通过。主控统一发布，本窗口没有 Git 写入。新夜间规则核读后**未新增任何 RTL 编译／仿真**。

## 输入、写集和来源

只写本目录、`code/tb/audio_out/m3_40mhz_pcm_i2s_latency_20261015/`、`code/docs/test/m3_40mhz_pcm_i2s_latency_20261015/`。新目录原不存在；其余窗口的未跟踪文件保持。

- 初始 HEAD `874c097d34140b120d52eaadd9748dd6ae8d5894`；恢复封存核 HEAD `8b64a352464932a28df565038cafc8d623dea5c9`。
- R05 ZIP 原件 SHA256 `dcf15f5d3ded1a0b160f55eab43066c728f80b3c329c44ea9f099c63f178696a`。**只取原封包 i2s_tx / pcm_frame_buffer**，不运行 R05 原 TB。
- 原 i2s_tx SHA256 `6c703e31064e5943df4e310b3baddd8935362a1c028828d8e11f8f3c016267ad`；原 pcm_frame_buffer `f8bc454a2e627809c2f9f9029c1e5128acf2fd543d7fcc2d3d83b50685f40997`。
- 只读原 sample_tick_gen SHA256 `0ae119c759ef208560a877c6393d6b1caa2fe0f4aa7f9cc8335b1982e6d139d6`。tick 参数 5153961，BCLK 翻转参数 659706977，sys_clk 40 MHz。
- 复用旧 `m3_clock40_pcm_serial_acceptance/` 的**协议事实**：外部 BCLK 上升沿采样、WS 低右高左、32 槽／半帧、最后16位有效。没有重跑旧专项或复制旧正常 capture 冒新证据。

## 文件与实际入口

`tb_public_serial.sv` 新诊断生产者连接原 buffer / tick / tx；`check_capture.py` 独立整型量化、公开 pending/held/ID/计数账本与物理引脚解码；`test_capture.py` 20 项新软件正负例；`run.py` 保留原有有界运行器及精确 R04 运行身份，**当前停止执行，不是新的许可入口**；`audit_and_seal.py` 仅只读历史和封包。

历史最终实际命令（已执行，勿重复）：

```powershell
& 'C:/Users/songdongkuan/miniconda3/python.exe' -B -X utf8 code/software/m3_40mhz_pcm_i2s_latency_20261015/run.py --output code/docs/test/m3_40mhz_pcm_i2s_latency_20261015/R04
```

退出0，总13.469秒，9个子进程；每工具90秒／本组300秒上限，全无超时。真实 argv/cwd、stdout/stderr、前后源／工具／依赖 SHA 见 R04/RUN_RECEIPT.json。执行工具为已核 Icarus 14.0 devel，本机 `E:/FPGA/GAOYUNFPGA/138K/tools/icarus_oss_copy/bin/`；只有子进程 PATH/TMP 前置，无安装或系统设置变更。ModelSim／Gowin／设备实际调用0。

## R04 限定结果

- 正常 capture 120024 连续 pre-NBA sys_clk 沿，两个独立 reset 寿命；每寿命72次 frame_tick，71间隔中833拍48次、834拍23次。短窗统计均值约48000.54 Hz，不能把有限窗偏差写成长期精确频率实测。
- 从真实新模块仿真 BCLK/WS/DIN 独立重建140个立体声帧，PCM24→16加128后算术右移8并饱和；正负满幅、舍入端点、左右不等均覆盖。
- 142次公开请求：136次到完整串行观察；4次尾段已 adoption 但串行尚未完整，不冒称全请求端到端闭合；2次故意未提交／过期，产生刻意欠载并保持旧 held。欠载与重复播放不计新发布。
- 32沿旧ID有效但不ready；700沿提交后valid保持但不二次提交。8次clip是**诊断生产者元数据**。原 buffer/tx 无clip输出口，账本可按成功提交只计一次，但这不证明R05算法clip或物理clip侧带已接通。
- 已完整观察136请求的数字 request→完整串行最大1687拍，即42.175 μs。**不是 MIDI 输入／算法总服务界，不是模拟起音≤10ms实测**。真实A公开轨迹缺失，R05逐请求deadline UNKNOWN；DUT自报max不替代它。
- 可编译 `WRONG_STEREO` 新TB错接变体：实际compile0、simulate0，checker退出1／`SERIAL_PCM_LSBJ_OR_STEREO`。不是文本篡改替代行为反例。
- 20项纯软件测试通过：漏／重复沿、X、非法flag、漏END、错PCM/clip/ID、错tick相位、错串行相位、意外欠载、10ms等号／超界／负时间、6舍入边界。所有文本坏例标 `SYNTHETIC_MUTATION`，10ms时间戳是软件边界例，不是真实超时RTL。

## 失败历史与额度，不重置

| 历史组 | 实际子进程 | 编译／VVP | 结果 |
|---|---:|---:|---|
| R01 | 3 | 1／0 | 编译进程3221225477访问违例，首双流／中间产物保留 |
| R02 | 5 | 1／1 | 提升执行权限验证同工具可编译；新TB最初未产生有效异步复位沿，首pre-NBA行有X，checker正确拒收 |
| R03 | 5 | 1／1 | 新TB显式t=1ns拉低复位后无初始X；oracle错误地不允许首次完整帧前的复位静音半帧，`SERIAL_WITHOUT_ADOPTION` |
| R04 | 9 | 2／2 | 只修独立oracle首次半帧口径，正常通过／错声道指定拒收／20软件例通过 |

共22个**runner子进程**：8版本查询、5编译、4VVP、5软件检查／测试。开工工具盘点另直接调用过一次`iverilog -V`，shell退出0；该次只有对话原始合并输出，没有另外冻结双流，不能混入22项收据或冒称双流齐套。因此已知Icarus程序总调用18次，其中5次编译、4次VVP、9次版本查询。四轮原件均在各R目录；不得删首失败、把四轮并成两轮或称R01未启动。R02提升沙盒执行身份不是更换工具；R01崩溃根因未作确定断言。

这四轮在本地原收据文件时间22:21:04–22:24:22，初始四包任务单874c097的C授权未列两组上限；夜间两组不同SHA规则首次Git发布在6d6c726（23:52:02）。时间来源为文件系统／Git记录，不是不可篡改的执行时钟证明。最新规则核读后遵照主控停止指令，仅封存，**无新增RTL运行，也不据新规则再领两组额度**；历史额度是否追溯的最终解释交M2／用户。本窗口不声称已替主控核定剩余额度。

## 自审与封存边界

核原双流SHA、所有stage源码SHA、R04前后SHA、原capture身份与20项原结果；不重跑已有测试。R04四个已验执行源保持原字节。新audit脚本／README仅软件封存和静态说明，不借旧仿真升级。R01–R03旧checker未单独冻结原文件；封存脚本按已知唯一diff逆向构造并验到原SHA，标DERIVED，不冒称同期原件。

封存命令只读既有证据，产生新独占目录，不运行任何RTL：

```powershell
& 'C:/Users/songdongkuan/miniconda3/python.exe' -B -X utf8 code/software/m3_40mhz_pcm_i2s_latency_20261015/audit_and_seal.py --output code/docs/test/m3_40mhz_pcm_i2s_latency_20261015/SEAL_20261016_R02
```

新capture合同见同目录 `CAPTURE_CONTRACT.md`。真实A不满足此字段时不能“换文件即PASS”；须明确来源映射和UNKNOWN字段，不填造request、clip或真实发布。只签新模块 L2／checker L1，整机、生产四音、资源、STA、板测、模拟延迟均未验证，board_release_allowed=false。
