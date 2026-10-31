# R13 码流及完整工程交接包

先看本文件；本包为已通过仿真及当前约束 STA 的版本，未上板实测。

## 入口

- 码流：`bitstream/09_pro_audio_knobs_flicker_R13.fs`。
- 工程：`source/project/pro_audio.gprj`；完整 HDL、真实厂商 IP、ROM、头文件、CST/SDC 均在 source 内。
- 推荐重建入口：`source/rebuild.tcl` + `source/options.tcl`；全新综合/布局布线，不依赖原机器的中间实现文件。
- 原始报告：`reports/pro_audio.tr`、`reports/pro_audio.rpt.txt`；同时附原始日志、综合 VG、HTML 报告及 native receipt。
- 功能回归、首失败及修正后结果：`verification/r02_system`、`verification/night2_timing/r03_trace_hold`。
- 验收与范围：`bitstream/RELEASE_RECORD.json`、`handoff/R03_FINAL_HANDOFF.json`。

## 本轮结果和边界

Gowin 商业版 V1.9.12.04 build2743；GW5AST-LV138FPG676AC1/I0，C 步进；顶层 pro_audio_minimal_top。
50 MHz 参考、40 MHz 音频、25 MHz pixel、125 MHz serial；均未降频或修改原时序不确定度。
Setup +0.741 ns，Hold 报告 0.000 ns；Setup/Hold 违规端点均 0。
Recovery +1.881 ns，Removal +0.064 ns，最小脉宽余量 +6.847 ns；51 条有效 SDC 命令核同。

R02→R03 仅两项生产文件变化：诊断 UART 的 selected 消费支路增加六个透明 LUT1（不增加协议周期）；
CST 追加红色 TMDS dout4 寄存器的真实历史成功位置约束。未改 DVI 加密 IP、音频流水线或 I/O 引脚。
同周期串口对照 4 组共 540 万周期／448 完整报文通过；其余功能 HDL 与已完成 R02 系统回归逐字节相同。
R02 回归含 85,787,018 次像素比较、32 live＋32 score 槽位、旋钮、BLE 视觉曲谱、PCM/I2S 检查。
这不是“整套 R03 系统回归重新执行”的声明；完整适用范围和首失败保留在 receipts。
没有本轮烧录、听音或物理 HDMI 实测，也不代签完整 C9/CDC/板级验收。

## 控件和画面

K1 CC7 调音量；K2 CC91：0–60 上飘、61–127 下飘；K3 CC71：0–60 原音色、61–127 第二音色。
K4 CC74：0–60 波形预留页、61–127 频谱预留页；页面明确显示“待接入”和 TONE 0/1。
K2/K4 最后收到的有效消息决定页面，K3 仅选音色。B1–B6 的 CC25–30 动作已移除。
曲谱只控制下飘提示，真人 MIDI 发声；下飘模式隐藏真人上飘动画。
保持 32＋32 显示槽位、物理琴键宽度几何与滑块重叠亮度修复。
真实双音色波形／频谱算法还未接入，未来 PCM 和像素接口说明见 source/docs/RESERVED_ANALYSIS_PORTS.md。

## 队友电脑重建

1. 完整解压到新的目录。先运行 `python verify_package.py`，应校验通过。
2. 使用本机已安装的指定商业版；不混用教育版。GUI 可打开 source/project/pro_audio.gprj。
3. 推荐从 PowerShell 用下面入口重建（替换工具实际路径）：

```powershell
& .\REBUILD_ON_TEAM_PC.ps1 -GowinExe 'D:\实际安装目录\IDE\bin\gw_sh.exe'
```

脚本只调用 source/rebuild.tcl；输出在 source/REBUILD/pro_audio/impl/pnr/pro_audio.fs。
如果 source/REBUILD 已存在，原入口会停止以保留旧结果，请另解压一份新副本。
许可证、商业版工具和 ModelSim 不随包分发。重新实现后的 FS/报告需重新核对，不能继承本包的时序数字。
本机已对转移后的 source 做静态 preflight：90 注册输入、GUI/Tcl 一致、include/ROM 解析完整；未再次启动 EDA。

verification 中保留的是实际运行的原始证据，命令和回执中的绝对路径为来源机器记录；
它们不自动变成可在任意位置直接运行的测试脚本。重建入口和产品工程则按包内相对路径解析。
reference_BASE_AUDIO_TOOLCHAIN_AND_PINOUT.md 是最初音频基线参考；本版显示/BLE 的实际引脚以 source/project/pro_audio.cst 为准。
本包是 FPGA 码流与工程，不包含新 ESP 固件或手机安装包；此次未修改两者。
旧 R02 的负 Hold 结果保存在原机器，包内仅附失败登记，不混装失败码流。

MANIFEST.json 覆盖包内所有文件（清单自身除外），用于大小和 SHA256 校验。旧源码、码流、冻结正文均未修改。
