# V3最终操作与完整性审计

2026-10-02，主对话2追加构建交付。冻结门禁已读，真实仿真、Gowin综合及原约束范围PnR/STA通过；**低音目标未达标、听感NOT_ACCEPTED；研究.fs已生成，未烧录、未上板。**

## 最终只读核查

- DESIGN_READY.json SHA与快照记录一致；冻结source 22文件全部SHA一致。
- candidate_20261002_141443_r2的72个staged_files全部SHA一致；复制来源46个正式原文件SHA一致。
- audit_old_versions.py verify实际返回PASS，0 differences：旧外部pop_repair、仓库code/rtl/pop_repair各95个非缓存文件，合计190份，未变。
- 旧V2研究.fs SHA仍为B12120E53FCEE5A2A48229245F4EA608CE3B7B5B96E0D5935B75FC7446CD1E8D；没有执行回退或替换当前正式版本。
- Git HEAD 427f3d33d6559e83b31e7e5347993db7dc4fa124；git status --short为空，git diff --check无报错。
- 前阶段verification下Python AST静态检查通过；追加export_pnr_delivery.py已实际运行PASS。V3现在有2份.fs（PnR原产物与逐字节一致的交付副本）。

实际SHA清单：verification/old_versions_final_audit.json、verification/baseline_reference_manifest.json、build/candidate_20261002_141443_r2/frozen_input_manifest.json。路径适配只在自有副本修改ROM默认路径/工程路径，算法source未改。

## 实际验证等级

L2/L3：独立振荡器158382检查、真实核心246624检查及61646帧黄金、能力296654检查、全顶层MIDI/PT8211真实及加速回归，均PASS；负例被拒绝。八组48份WAV与逐字节资产再生成PASS。
L4：GowinSynthesis实际exit 0，加密.vg与syn报告已保留。资源27955 Logic、7074寄存器、12 BSRAM、0锁存器；DSP仅报告12 MULTALU27X18+8 MULT27X36原语，不换算物理块数。
追加阶段使用已安装IDE自带Tcl控制台完成真实PnR/STA及码流生成；未安装工具或修改驱动。IDE自动重新综合，最终PnR资源28366 Logic、7074寄存器、12 BSRAM、28/118 DSP、0锁存器。原r2综合记录没有覆盖。50 MHz Setup/Hold违例0/0，最小余量0.060/0.001 ns；Fmax 50.150 MHz。Recovery/Removal最小报告余量7.147/1.011 ns、脉宽6.914 ns。PR1014仍在，未约束路径数量未报告，I2S外部时序没有物理验收。完整记录见PNR_DELIVERY.md与output/bitstream_v3_research_20261002/manifest.json。
未烧录或上板。低音频带结果与听感门禁不通过，不能以PnR/STA通过宣布拍频消除。

## 上下文误续接：已可恢复归档

14:03:42误运行旧run_midi_controls_sim.ps1，14:04:06结束；仅产生唯一新目录的12份日志，没有修改正式源码、脚本、文档或Git。日志已从
E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/output/midi_controls_20261002_140342_b4aa07da
移至
E:/FPGA/GAOYUNFPGA/pop_repair/v3/verification/accidental_run_archive/midi_controls_20261002_140342_b4aa07da。

12份日志均保留，可移回恢复；六前缀mapping、queue_fast、queue_50m、uart_50m、note_uart_regression、cc64_regression各_compile.log/_run.log。这次误跑不作为V3证据。脚本自己的唯一Temp目录按已有finally清理，未改变清理方式或触碰用户结果。

## 写入范围与交接

主对话2只写V3的verification/build/output/README；主对话3拥有source/design。两份准备失败快照及最终r2均保留，无破坏性清理。未更新正式任务/验证编号文档，无Git提交/推送，无FPGA下载或Flash操作。未向其他聊天发送消息；本文件及最终答复供主控读取。
本阶段交付真实研究码流与原约束范围时序报告；低音改善、板上稳定性、PT8211电气时序和M3听感仍未完成。不扩大研究、不改source/design，不自行烧录。
