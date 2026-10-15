当前状态（2026-10-16）
======================
以下旧BLOCKED_INPUT正文为路径迁移新授权前的历史记录，不代表当前结果。
最新结论及交接以CURRENT_RESULT.txt、HANDOFF_TO_M2.txt和delivery_night_r03为准。
一次实际Gowin调用已完成：退出0，344.813秒，五对精确端点的Setup/Hold均通过候选检查。
原84项输入已封存并核同；仅新副本40处路径可逆迁移，SDC追加10条报告命令。
工具2518项前后核同。未运行第二轮，未操作硬件；正式签收仍归M2。
本窗口不Git写入或上传，由总控统一发布；待用户转发，尚未送达。

历史正文（原文保留）
====================
B：40 MHz 新音频定向 STA 后继 R03（2026-10-15）

结论：BLOCKED_INPUT；已完成新增同版输入恢复与可核启动缺口清单，未新物理运行。
本次用户的一轮物理额度UNCONSUMED，Gowin/PnR/STA启动0，未建消费标记或物理输出。
不是“许可尚未给”：四包总单已允许满足条件后一次1800s以内候选物理试核，
本次停在条件未齐，而不是要求用户逐文件重新授权。

有效输入与写集
==============
开工HEAD与origin/develop：874c097d34140b120d52eaadd9748dd6ae8d5894。
依据M3_四项并行主责授权_2026-10-15.md、B专单最新横幅；旧72561ce成果只读复用。
仅写code/software/m3_m2td_audio_endpoint_audit_20261015/successor_R03/和本docs后继。
原_06、旧checker、源/ROM、SDC/CST/LOC、R05、T052/R04、共享编号/状态未改。
未Git写入、未提交/推送；总控唯一发布。B物理输出只拟用全新任务前缀，尚未创建。

新增可核成果（不是重跑旧32/13组）
================================
1. 精确恢复物理PREPARATION_RECEIPT.input_files的全部84项。
   physical ZIP17e71ebd5b54743fd0214af5fbfdfd1a4cca4eddbcedab56f7b3df7b3ca521ff；
   portable ZIP1101f1af0809530a150143456aab8ff9a1c66373e9ccbc174c6459e8c916b3bf。
   普通成员直接保留，路径适配成员按portable收据逐项new→old逆置UTF-8字节。
   重复记录的相同映射只执行一次，记录每项替换次数；派生身份明确标注。
   84项每一项大小/SHA都与物理冻结清单相同，0缺件/0猜字节。
   input_audit_r01/derived_original_bytes/为原字节或明确派生，不是新综合网表。
   AUDIT.json逐项保留原/portable member、原SHA、逆映射、前后SHA。
2. 已查到E盘gw_sh.exe（33064B）SHA
   4c172d4c0d2a4c7ef5c764d091a315cbcde2127573554bfd7d09ac6f2e5ea535，
   与原RUN_RECEIPT.input_before中的gw_sh.exe完全一致。
   原报告版本V1.9.11.03 Education；仅是launcher字节核同，未运行-v、未观测DLL加载。
   D:/program/.../IDE/bin中其他Gowin程序存在，但gw_sh.exe本体不存在，未换工具。
3. 复用旧5个具体报告pair及32/13已签软件结果；本轮不重跑。
   pending_plan_r01/PENDING_PLAN.json绑定旧targets SHA、84恢复清单SHA和一次启动边界。
   DIRECTED_REPORTS_PROPOSAL_ONLY.sdc.txt为旧实际5pair提案原字节，未插入SDC/执行。
4. 新12项恢复边界测试通过；verify_and_seal.py --run-id r01实际exit0，
   recovery/unit两子命令0/0，输入/源码/Python及恢复84文件前后SHA一致。
   完整argv/cwd、stdout/stderr、退出码和SHA见verification_r01/RECEIPT.json及双流原件。

真正的启动缺口
==============
恢复84/84不等于可在本机原字节启动：恢复源中40处绝对ROM/include引用，跨15个文件，
指向原Angel17机器C:/.../m2_m1td_whole_prepare_20261015_06/，本机均不存在；
这40处只有9个不同绝对路径。38处位于GPRJ列举文件，2处在明确排除且未编译的旧dds_oscillator。
被列举编译也不等于被实际实例化；不能把40处全部叫40条活跃路径或40个功能缺陷。
未以创建原C盘目录、junction、别名、改系统设置、忽略readmem错误来绕过。
pending_plan_r01仅计算原prefix→拟新stage prefix的可逆字节变更方案，15文件、逆置全同；
没有写新适配源、没有改预期SHA、没有实际运行或认定受控范围已获批准。
项目XML本身含原机路径，也需显式新stage构建映射，不得冒原_06原件。

同次.vg/实现数据库：原物理ZIP15成员中没有，旧_06本机不存在。
只读查看E:/FPGA/GAOYUNFPGA/138K及Callback3，只找到10-05旧audio_visual_coexistence_top.vg
等历史对象，不拿它们冒新版m2_fourvoice_timbre_delay_board_top.vg。
原timing报告base_s1/base_s2各0匹配，不能据此认定已优化；物理pair仍UNKNOWN。
五旧pair只具有单类报告，缺完整setup+hold；query集合/转义/存在性未执行核验。

下一责任与可执行条件
==================
M2/总控需决定并提供：
- 同次_06综合网表/实现数据库原件及SHA，或明确重建后目标映射的依据；
- 是否批准只对上述已绑定ROM/include路径做独立可逆迁移（不改数学/时序/模块），
  或提供不改冻结源字节、只在授权新stage内可用且有文档依据的原路径解析机制；
- 完整工具依赖/版本身份、真实get_regs/get_pins对象和命令语义核验。
若这些条件齐全，可在本次授权的全新输出/marker中一轮有界执行；不能复用旧attempt/vg/fs。
首物理失败即停，不提限、不无变更重试、不恢复旧LOC/放宽uncertainty。
本包只L0/L1身份准备，board_release_allowed=false；不是指定端点L5、整机功能或硬件签收。

命令
====
仓库根：Python -I -S -B -X utf8
code/software/m3_m2td_audio_endpoint_audit_20261015/successor_R03/freeze_audit.py
  --output code/docs/test/m3_m2td_audio_endpoint_audit_20261015/successor_R03/<全新直接子目录>
test_freeze_audit.py（同解释器；12项）
prepare_pending_plan.py（首次；拒覆盖pending_plan_r01）
verify_and_seal.py --run-id r01（已执行；再次需新r02，不能覆盖r01；只软件，不是EDA额度）

失败历史与通信
==============
首次test_freeze_audit.py exit1：-I模式去除脚本目录，直接import freeze_audit失败；
原工具回执29854e保存ModuleNotFoundError，未启动任何EDA，未写失败输出。
后继仅用importlib明确装载同目录固定源，再新完整留痕两命令0/0及12项通过。
初次交互命令只有工具合并输出，没有另存原始双流，明确不伪称齐套原双流。
新verification原件双流齐套。必要总控阻断回执send工具被平台拒绝，未送达、未绕过。
