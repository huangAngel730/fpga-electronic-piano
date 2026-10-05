# 主对话3：138K B/C 离线比较续接记录

日期：2026-10-05。最新状态（12:15续查）：**冻结输入已恢复46/47；仅DVI_TX_Top.v尚未匹配。CLI入口已解决，尚未执行综合/PnR/STA。**

此状态不是 PnR FAIL，不是判断 138K 无益。尚未执行仿真、综合、PnR、STA或烧录。已在隔离工具副本运行Gowin CLI的Tcl冒烟（exit0），不等于验证综合/PnR许可或138K支持。原仓库及前一审计目录未修改，未提交/推送，未调用Programmer、未安装软件或修改现有工具、系统、驱动、ACL。

## 最新自主追查结果

- 从本机同版Gowin安装包中找到并解出gw_sh.exe；先复制现有IDE到138K_try/tools/gowin_1_9_11_03，未运行安装器。Tcl8.6.4冒烟日志见cli_smoke.log。入口SHA与安装包SHA见dvi_search_proof.json；标称工具版本仍需真实构建输出确认。
- 只读导出e5eb025的Git音频快照，按现有生成脚本和历史证据重建8项缺件；只有与预期actual SHA完全相同才保存，详见recovery/recovery_proof.json。simple_voice和sustain_controller的差异确认为ADSR组合阶段audio_snapshot头文件绝对路径。
- assemble_proven_inputs.py重新读取/验哈希后汇齐46项工程输入、7个ROM及2个Git头文件；exit0，见assemble_proven_inputs.log和proven_bundle_manifest.json。这里保留历史绝对路径以证明字节身份，不是已搬迁可编译工程，更不是原始V0171最终manifest。
- 首次对E:/FPGA、D:/program/gaoyunFPGA、桌面和下载目录的10661个Verilog/IPC候选检查10381个文件（另280个大于1MiB跳过），raw/LF哈希均无DVI原件匹配。汇齐副本后的复查为10662候选/10382检查，仍0匹配。15项目录拒绝访问如实保留，未改ACL。补查其他竞赛/学习/下载/备份目录、相关Git历史和已知工程ZIP，仍未找到冻结IP；不能外推全磁盘绝对不存在。
- 剩余DVI实际SHA：162f68cab4262f8a3acae17f2fc66b6d9ef403815fd5ebeeecf30b59d88e203c；M2 GUI原始CRLF文件SHA：b378c6a41d06a14215dc9ec54ed20bfc91309a0bb1543c589246717da3aee2ab。官方SiPEED旧示例是另一哈希，不作替代；不解密、不绕过许可证。
- 最终原始manifest、实际完整选项/命令和原始报告仍未到件；V0165清单+V0171单parser变更只能建立重建依据，不能冒充原清单原件。138K引脚/IP/固定布局适配也尚未开始。

本轮没有运行不完整设计；输入齐套后先核对编译闭包及选项，再在副本运行60K控制组，之后B/C，保持50/25/125MHz及Hold0.550ns。最新最小补件消息见M2_补件收敛到DVI_20261005.md（待用户转发，尚未送达）。下文保留初始静态checkpoint的历史状态；涉及38/47或CLI缺失的描述已被本节更新，不是最新结论。

## 当前任务与边界

- 继续的是 138K B/C 对 V0171 音频+HDMI候选的同条件离线物理比较；不是旧 MIDI 实物补测、parser优化、T028接入或32声部开发。
- 原仓库 E:\FPGA\GAOYUNFPGA\team\fpga-electronic-piano 全部只读；禁止 Git写入及会在原 output/cache落文件的脚本。
- 旧审计目录 comparison_20261005_dab75308 原样保留；本目录新增续接文档、快照、恢复脚本、核对结果和哈希证明源副本；工具副本位于同一138K_try根下。全部在138K_try。
- 先60K控制组，再138K B/C；50/25/125MHz、系统Hold uncertainty0.550ns；不删/放宽约束，不用audio-only或拒收的提前寄存候选。
- 未授权直接给 M2 发消息；补包请求标记“待用户转发，尚未送达”。

## 输入审计复核

读取既有 input_audit.json 和 normalized_audit.json，按不同集合复算：47工程条目，36原input哈希有匹配，33 actual直接匹配，5项在明确历史ROM路径/LF变换后匹配，合计38项 actual有证据。normalized文件仅包含14项待补比对记录，不能误当成全部47项。

9项未证明一致：audio_visual_coexistence_top.sv、simple_voice.sv、dds_oscillator.sv、sustain_controller.sv、polyphonic_envelope_bank.sv、TMDS_PLL_800_600_60.v、DVI_TX_Top.v、audio_visual.cst、audio_visual_hold055.sdc。7个ROM在原审计中已有匹配记录；本轮不重复整库扫描。15个扫描权限错误保留，未改ACL。

V0171源关系由原审查确认：仅换de68038 parser，46条非parser输入及CST/SDC/ROM/PnR选项不变。最终manifest预期SHA为1e29e550b129176e06fe609631229ae7c03a22ed3ad9ac4652f0705c7a234a36；当前取得V0165清单的SHA为08d48c7b744d75f1b6a52cc5f4b4eb6a0c99d1e31e9cec4e3c75209e59e0ad85。只靠前版清单不能建立完整最终编译闭包。

原M2精确隔离组合的历史Setup+.017/Hold.000/Recovery1.113/Removal.869、Logic19534/FF8674/DSP46/BSRAM20已在JSON与原报告正文交叉核对。没有把它们登记为本机复现，也不外推L6或后续功能余量。

## 原理图第5至7页人工续审

使用前审计保留的PDF、PNG和文本，只读查看完整三页；已有材料足够，不执行外部MinerU上传或安装。

- 第5页 MSPI FLASH / JTAG Connector / Button / LED / Crystal oscillator：Y1100标50MHz，经R973 0欧姆连接 BANK4_V22_EMCLK_50MHz。该页的按钮网络是 BANK10_N12_RECONFIG 与 BANK7_F4_CPU_RESET，不能误当成参考CST中的AA13用户复位；本任务不调用任何配置/下载功能。
- 第6页 BTB Connector：核心板向连接器引出Bank信号及电源，例如 BANK5_AA13/AB13/Y12 和 BANK4_V22。连接器有5V0电源针脚；这不意味着对应FPGA GPIO允许5V，不能据此直接给出接线建议。此核心板页没有建立电子琴音频/HDMI底板端到端连接关系。
- 第7页 BANK4/5/10/Q0/ADC：V22在Bank4；AA13、AB13、Y12在Bank5。Bank4包含PLL专用复用脚，Bank10含JTAG配置脚，Q0为SerDes区域，不能把所有球位视作任意GPIO，也不能照抄60K固定INS_LOC。
- 参考CST（另一个文件，不是本次实际设计CST）sys_clk=V22、sys_rst_n=AA13、Key_in[0]=AB13、Key_in[1]=Y12，均写LVCMOS33/3.3V。页6/7支持球位所属Bank，不单独证明底板实际供电/按键电路；板级供电仍需已有供电页和目标底板资料交叉确认。
- 参考CST里R17用作LEDs[2]，因此60K现有MIDI R17用途不能直接继承到138K而声称板级可用。HDMI端口/差分配对、音频和实际目标底板必须从完整板级资料核对。未生成任何新CST或IP。

来源：../comparison_20261005_dab75308/board_138k_schematic.pdf 和 board_138k_reference.cst。以上是本轮人工续审范围，不代表所有接口已完成电气验收或B/C器件布局兼容。

## 工具核对

- 现有目录 D:\program\gaoyunFPGA\Gowin\Gowin_V1.9.11.03_Education_x64\IDE 下文件扫描未找到gw_sh.exe；gw_ide.exe、GowinSynthesis.exe及DLL存在。目录名标称版本不是已执行的版本回传；PE FileVersion/ProductVersion读取为空，真实工具版本尚待工具输出确认。
- 已交付Gowin官方手册SUG100-4.4.2E的PDF第96页（印刷页85）说明CLI是IDE/bin/gw_sh.exe [script file]；PDF第98页说明CLI相对路径基于启动目录；第107页说明run pnr/run all与saveto -all_options。没有将gao_sh/gvio_sh误认为PnR入口，不猜内部DLL命令、不绕过许可证。
- ModelSim已确认可执行文件路径 E:\FPGA\Bpan\modelsim\modelsim1\win64\vsim.exe，examples仅示例目录。未启动，版本与许可可用性未验证。
- 当前提供的计算机控制工具禁用原生应用控制；未启动GUI自动化。缺CLI不能证明已有GUI无法PnR。可由M2提供合法同版CLI/导出工程；需安装或改现有软件则另行向用户申请。
- device_info_original.csv记录B gw5ast138b-011、C gw5ast138c-007，PN GW5AST-LV138PG484AC1/I0、PBGA484A、C1/I0。这里只证明库条目存在，不代表实际板版本、许可或PNR可运行。

## 文件与可复现静态核对

audit_snapshot保存旧审计6个原件副本和原M2报告正文副本；没有复制项目工程来冒充完整冻结包。

运行本目录的静态核对入口（不会执行任何EDA、Git或仓库脚本）：

```powershell
pwsh -NoProfile -File E:\FPGA\GAOYUNFPGA\138K_try\m3_continuation_20261005\record_checkpoint.ps1
```

脚本在本目录checkpoint.json记录输入与快照SHA、缺件、历史指标、实际级别和时间。退出0只表示静态核对成功，不能理解为物理构建通过；若输入数量/哈希/集合或冻结约定变化，直接非零退出。本轮实际执行20项断言全PASS、进程exit0；原始运行日志static_checkpoint.log保留。文档收口后的第二次静态核对记录为static_checkpoint_final.log，仍不是EDA执行。具体时间及哈希见checkpoint.json。

初始全包请求M2_冻结工程补包请求.md仅保留历史。下一步以M2_补件收敛到DVI_20261005.md为准；到件后核对编译闭包和选项，先60K再B/C。收到包不等于已通过，未确认不能启动不可比的构建。
