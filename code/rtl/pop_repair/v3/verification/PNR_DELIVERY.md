# V3研究试听码流：真实构建交付，不烧录

2026-10-02，主对话2。低音研究候选，NOT_ACCEPTED；不是正式消拍修复版。仅verification/build/output/README变更，无source/design、正式仓库或V1/V2修改。

## 交付

- FS：E:/FPGA/GAOYUNFPGA/pop_repair/v3/output/bitstream_v3_research_20261002/electronic_piano_v3_RESEARCH_NOT_ACCEPTED_427f3d3_20261002.fs
- SHA256：d561c10eee9de55355ff6a7a65d31893314ef4f2cda2a37c7915a9e42b40a5e4，18,109,476字节。
- manifest：同目录manifest.json，含原产物、全部报告SHA、冻结门禁、约束SHA、工具/器件/资源、实际时序和未验证边界。
- 实际工程与日志：E:/FPGA/GAOYUNFPGA/pop_repair/v3/build/pnr_attempt_2。

已安装Gowin V1.9.11.03 Education，GW5AT-60B-PBGA484A-1，GW5AT-LV60PG484AC1/I0，顶层electronic_piano_top。正式基线427f3d33d6559e83b31e7e5347993db7dc4fa124；实际RTL输入仍是此前仿真通过的candidate_20261002_141443_r2。原50 MHz、采样率、端口、引脚、电平、CST/SDC字节不变。

## 实际操作与命令

computer-use技能用于已安装Gowin IDE操作，最终使用该软件自带Tcl工程控制台；没有从GUI执行Windows shell命令，没有安装/修工具、驱动或更改系统设置。

1. prepare_pnr_attempt.py --name pnr_attempt_1复用原r2综合产物准备工程；IDE run pnr自动补跑综合，默认Verilog-2001导致失败。失败工程/日志保留，不作为成功证据。
2. prepare_pnr_attempt.py --name pnr_attempt_2重新建立独立工程，原r2不动。在IDE Tcl控制台实际执行：

```tcl
source {E:/FPGA/GAOYUNFPGA/pop_repair/v3/build/pnr_attempt_2/run_pnr.tcl}
```

脚本内open_project、set_option -verilog_std sysv2017、set_option -top_module electronic_piano_top、原快照include路径及run pnr；原文件可直接查看。IDE仍自动综合，所以最终PnR输入是本次新生成的impl/gwsynthesis/electronic_piano_v3.vg，不冒称直接复用了原r2网表。实际编译配置见.prj与impl/electronic_piano_v3_process_config.json，实际综合结束见同名.log。
3. PnR实际参数见impl/pnr/cmd.do；-sdc明确指向原audio_timing.sdc副本，STA报告确认20.000 ns/50.000 MHz。cmd.do的-global_freq 100.000是工具默认目标，不是改变板载时钟；以实际SDC及STA Clock Summary为准。
4. 用现有Python执行（交付脚本拒绝覆盖现有目录）：

```powershell
& 'C:/Users/songdongkuan/miniconda3/python.exe' -B -X utf8 'E:/FPGA/GAOYUNFPGA/pop_repair/v3/verification/audit_old_versions.py' verify
& 'C:/Users/songdongkuan/miniconda3/python.exe' -B -X utf8 'E:/FPGA/GAOYUNFPGA/pop_repair/v3/verification/export_pnr_delivery.py'
```

实际PASS：source22/staged72/formal46/design/constraints/old190/git；PnR与原约束范围STA通过。导出脚本首次因Gowin HTML缺少一个td闭合标签触发断言，修正报告解析后PASS；未修改报告或设计。原始结果完整保留。

注意：pnr_attempt_2/impl/gwsynthesis里的result.json、command.json、actual_synthesis.log是准备阶段复制的原r2综合溯源，不是本次GUI综合/PnR判据；以实际新.prj/.log/.vg及PnR报告为准。

## 时序与资源

实际PnR于15:51:57结束，布局布线报告总耗时2分42秒。报告分析24309条路径、22216个端点，Setup/Hold TNS均0、违例端点均0。

| 项目 | 实际报告 |
| --- | --- |
| sys_clk | 20.000 ns，50.000 MHz；实际Fmax 50.150 MHz |
| Setup最小余量 | 0.060 ns；最差路径为slot_generation到MIDI parser FIFO CE |
| Hold最小余量 | 0.001 ns；最差路径为allocator note_active到in_release |
| Recovery / Removal | 前25条最差路径均非负，最小7.147 / 1.011 ns |
| 最小脉宽 | 最小余量6.914 ns |
| PnR资源 | Logic 28366/59904；寄存器7074/60780；BSRAM 12/118；DSP 28/118；锁存器0 |

Setup角Slow 0.855V 0C C1/I0；Hold角Fast 0.945V 85C C1/I0。所有10个端口在实际PnR pinout都有原指定引脚、电平及约束标记；导出脚本核对位置/电平。上述28个DSP是PnR实际物理资源值，不是把12 MULTALU27X18+8 MULT27X36简单相加。

## 必须保留的边界

- Setup/Hold余量很小；PR1014通用sys_clk_d布线延迟/偏斜警告未消除，不改V22或原约束。
- 工具生成报告没有未约束路径总数，不宣称0。原SDC对异步MIDI/按键/外部复位没有input_delay，对UART/PA没有output_delay；这不等于全部外部接口已签核。
- 原I2S输出-delay 5/0 ns仍是经验占位量级，不是PT8211板级延迟实测。BCK/DIN电气时序、THD+N、实物键盘、长时间稳定性未验收。
- 本阶段不重跑全仿真，复用同一冻结快照已有真实PASS记录；没有后PnR仿真或独立ROM INIT码流解码。ROM SHA、路径、重生成一致性和综合RAM提取证据保留，不能冒称板上ROM已验证。
- 低音改善仍NOT_ACCEPTED，当前基线无HDMI，未新增。未烧录SRAM/Flash，未替换旧正式版本，未提交/推送或取号。
- source22、design全部文件、staged72、正式46份及约束SHA核对PASS；旧两个目录各95文件零差异、Git HEAD不变且工作区干净。最终审计与manifest已保留。

本轮完成构建交付，不替代下一步由用户安排的研究候选试听或主控决定的设计优化。
