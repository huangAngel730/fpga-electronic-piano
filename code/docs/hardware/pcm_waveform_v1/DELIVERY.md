# T058独立波形阶段交付（2026-10-07）

基线develop `2fc64d5`，合同D038/D039。原L56载体输入SHA全部检查，原源码/ROM不改。
只新增本任务四处；无生产/公共接口/顶层/扫描/约束/工程/共享登记变化。

## 实际结果

- Icarus Verilog 14.0 devel（s20260301-474-g5591c2dde-dirty），真实RTL编译exit0/运行exit0。
- 正例4,033,936逐拍公开输出比较，pixel_errors=0、state_errors=0。
- 包含8完整800×525扫描/3,360,000像素/4200行独立Python像素摘要复算；最后一帧enable0。
- 正常原A5849包全部顺序/左右值与原件逐条相等；诊断原A41包全部相等，短流不发布完整窗。
- signed极值/量化边界、四位置尖峰、2047/2048/2049、完整连续多窗、序号gap/repeat/wrap、
  restart优先、复位/热身、背靠背包、pending替换、停止输入、front稳定、消隐边界与2拍通过。
- 两行为变异分别compile0/sim0，完整跑完全部8帧后checker exit1：
  signed_wrong拒收PIXEL_REFERENCE，torn_front拒收STATE_REFERENCE。
- 空/截断/错END数量/非法周期/垃圾capture五项外部checker均exit1拒收。
- 一次独立GowinSynthesis exit0，V1.9.11.03 Education，GW5AST-LV138PG484AC1/I0、C。
  报告实际pixel_clk 40.000ns/25.000MHz；Logic375、Register196、BSRAM3；DSP空栏unknown。
  综合估计Fmax107.167MHz只作为估计，不是布局布线/STA。没有PnR、没有.fs，没有下载。

纯像素域RTL达到L2，独立整数/逐像素参考限定L3；单模块Gowin综合达到L4。
不存在新整机L5/L6/L7结论，不沿用旧L STA或旧实屏结论。

## 运行命令

本机Python为现有bundled runtime（没有安装任何新工具）：
`C:/Users/songdongkuan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`。

```powershell
python -B -X utf8 code/scripts/run_m3_pcm_waveform_acceptance.py --output code/output/m3_pcm_waveform_20261007_attempt3
python -B -X utf8 code/docs/hardware/pcm_waveform_v1/standalone_synth/run_synth.py --output code/output/m3_pcm_waveform_20261007_synth1
```

上述原目录已存在；复跑须换新唯一目录。按本轮有限综合授权，不自动追加综合或PnR。
精确工具命令/源码SHA/原stdout/stderr/capture/report由evidence内原字节封存及receipt保存。
raw_manifest列47份原始证据（含44份专项/综合和3份仓库门禁），每份base64解码后核
raw_bytes/raw_sha256，不把Git换行当原件。
normal/diagnostic输入原始SHA分别为
`23e823c46638f87574616c9ab1de70c594acbd595188783d2e3b54ade0bdcfe4`和
`b212b560594fa4b590981535f9e7df23e4d97fa86ea9a432b68210958d41c06b`。
候选RTL SHA256：`052c4e79095152410bdd42e4d5c3cd47a00b91ad7bdf848a3c0914ab9aec0160`。

`reference_frame3.png`是正例第3号帧的独立参考预览（checker已校验该帧RTL所有行），
不是实屏照片；黑色区外只示意mask0，不代表原动画被删除。

## 失败历史与未验证边界

attempt1：TB参考中unsigned y影响signed移位表达式，同时诊断覆盖计数过宽，未PASS；
attempt2：正例和两个完整行为变异通过，但损坏周期记录被漏检，整轮FAIL；
补严格周期与诊断原41包逐条身份核对，attempt3最终全部通过。三个输出目录原日志均保留。
RTL未因参考/证据checker返修而改变，一次综合对应上述同一RTL SHA。

未执行：真实40→25MHz CDC、音频观测寄存/音频无扰动整机证明、最终RGB/HS/VS/DE接入、
新整机综合/PnR/STA/引脚门禁、HDMI/PT8211/屏幕实物、长期运行、SRAM/Flash。
计数饱和写法已审查，未以40亿输入穷举实测；不可据此声明整机诊断计数溢出试验通过。
M2独立复核/正式接入后统一共享登记；M3不改任务看板/当前状态/编号表。

仓库九项门禁全部PASS、exit0，Python语法194文件；原stdout/stderr/receipt见evidence/gate。
首次直接执行遇系统WindowsApps Python启动别名不可用，未改全局环境，在子进程PATH中
使用已有bundled Python后上述门禁实际通过。提交号在实际Git提交后回传，不预填。
