40 MHz 音频端点清单与 STA 定向提案（主对话4部分，2026-10-15）

结论
====
本交付只完成任务单第1/2项可实现的离线准备及自身软件自检，等级L0/L1。
新STA、get_regs/get_pins执行、综合、PnR、ModelSim、下载均0次。
board_release_allowed=false。没有修改旧报告、checker、SDC/CST/LOC、RTL或共享表。
主对话2的独立软件验收器另行负责；总控负责适配与综合交付，本窗口未代签该部分。

重要材料边界
============
物理ZIP SHA256:
17e71ebd5b54743fd0214af5fbfdfd1a4cca4eddbcedab56f7b3df7b3ca521ff
实际15成员，无.vg、无布局后网表、无位流本体；MANIFEST仅记录本地位流身份。
原预期output目录在本机不存在，限定路径枚举未找到同次.vg；部分历史临时目录访问拒绝，
因此不声称全磁盘搜索穷尽。未提权/扩大扫描，不拿旧electronic_piano.vg代替。
原报告Design File指向impl/gwsynthesis/*.vg，仅是历史输入路径，不证明本机持有该原件，
更不能把综合.vg叫布局后网表。现可核的是原PnR timing报告中的实际路由节点及LOC。

目标base_s1[31:0]→base_s2[31:0]源级关系成立，但精确综合对象、物理对象、双分析报告UNKNOWN。
timing.html全部字节中base_s1/base_s2各0匹配；这只是有限报告未显示，不能推出被优化。
不得把新层级前缀拼接旧base_s1_18_s0/base_s2_18_s0当作实际对象。
M2需补同次完整综合网表或已有实现数据库，核实际保留/优化对象，再决定寄存器对。

真实可证端点（精确全名见targets.json，不是新命名）
=================================================
1. pitch_lane3_total_to_oct：total_s2_10_s0/Q → oct_lut.../AD[7]。
   Hold_Slack_Table8路径4，Hold 0.000ns，sys_clk:[R]→sys_clk:[R]。
   起点R83C117[2][A]，终点LOC见同路径详细原文；这是寄存器→ROM地址，不是FF→FF。
2. pitch_lane0_total_to_sub：total_s2_6_s0/Q → sub_lut.../AD[10]。
   同表路径5，Hold 0.000ns，同sys_clk，起点R86C122[0][A]。
3. voice_lane2_phase_to_rom：piano/phase_acc_30_s0/Q → piano/u_table/rom_data.../AD[10]。
   同表路径3，Hold 0.000ns，同sys_clk；R102C83[1][A]→BSRAM_R100[17][B]。
   这是实际声音采样链的相位→波表地址路径，不以事件FIFO/视觉CDC冒充声音数据路径。
4. post_right_ram_address：右声道延迟wr_ptr_7_s1/Q → buffer.../WAD[1]。
   同表路径2，Hold 0.000ns，同sys_clk，起点R48C105[0][A]。
5. event_fifo_to_audio_slot：事件FIFO/rd_ptr_2_s0/Q →音频allocator target_slot_0_s0/CE。
   Setup_Slack_Table10路径1，Setup +1.736ns，同sys_clk。
   这是事件入口→音频控制路径，不冒充voice→mix或PCM/I2S数据路径。

前四对未见同一精确pair的Setup，第五对未见同一pair的Hold。
现有原报告全局Setup+1.736/Hold0及TNS零不能补齐这五对的另一个分析。
voice→mix输出寄存器对、PCM→I2S负载寄存器对：UNKNOWN，需同次网表进一步核对象，
不能用本次未出现的源码名自动生成物理目标。先完成上述关键pitch与真音频路径即可。

原片段与原文定位
==============
observed_r03/originals/：12个白名单成员逐字节复制，保留原换行；不解工具/位流。
observed_r03/observations.json：原ZIP/成员SHA、11条音频相关汇总行、5条重点路径、时钟元数据。
每行raw_location为UTF-8原字节0基[start,end)；fragment_sha256可从原timing.html重新切片核验。
detail_candidates绑定详细路径表，routed_node_locations绑定起终点真实LOC。
observed_r03/fragments/文件名含字节偏移，避免同一个Hold_Analysis8锚下多表互相覆盖。
原报告生成时间Thu Oct15 10:48:37 2026、Gowin V1.9.11.03 Education、
GW5AST-LV138PG484AC1/I0/C；sys_clk Generated25.000ns、40MHz，源PLLA/CLKOUT2。
这些是历史报告中的身份，不是本机当前工具安装核验或新工具执行。

精确源级关系与派生证明
====================
source_derived_verify_r03/（最终本轮）保存两个派生源、portable_original原成员及DERIVATION.json。
来源原自包含ModelSim ZIP:
1101f1af0809530a150143456aab8ff9a1c66373e9ccbc174c6459e8c916b3bf
依自身PREPARATION_RECEIPT.path_adaptations逐项new→old逆置UTF-8路径字节，其他字节不变：
fcw源5997ae2eddb483f95dbb10cdac6cfdac3d61a857046e95e136099e11cf0ecabb
snapshot源c35bc435a98d541e176ea59373bffd0ded9c346c1954118c6fde21c65a4ee601
二者与物理PREPARATION_RECEIPT.input_files精确SHA相同；全部标DERIVED_RECONSTRUCTION_NOT_ORIGINAL。
fcw L81声明32位base_s0..s4；L100同sys_clk always_ff；L105复位清零；
L110-112 valid_pipe[0]使能base_s1；L113 valid_pipe[1]使能base_s2<=base_s1。
snapshot L37四lane生成、L38-43 u_control/clk/accepted&&request_occupied[lane]。
这是同源静态语义，不代表综合网表保留同名FF或该特定位布局后存在/活动。

提案使用与错误即拒合同
====================
STA_PROPOSAL_NOT_EXECUTABLE.tcl.txt仅文本提案，禁止直接source。
targets.json是本窗口观察schema，不假设与主对话2schema相同；总控在coordinator/适配。
对每个真实起点查询精确get_regs对象、对ROM地址/CE查询精确get_pins，不能要求RAM地址是get_regs。
名称中的[]转义为literal glob；M2应先核该版Gowin集合/转义语义，检查返回对象准确名和数量1，
不可用扩大通配符消除缺失。查询时钟、两端clock pin实际归属及25ns周期，不能只看字符串sys_clk。
之后拟对同对对象分别report_timing -setup/-hold，每类至少一条非空真实路径。
最终必须校验精确起终点pin、两端sys_clk:[R]、活动性、有限非负slack、同实现/报告SHA。
absent、inactive、空路径、缺一类、非目标音频路径、不同clock/身份/负slack均拒收。
不能仅凭命令调用exit0、Active字样或任意音频路径签收，也不能把JSON自述当原报告。
命令未执行、collection cardinality API/精确query语义仍待M2在工具文档/获准窗口核实。
不恢复旧LOC、不放宽约束、不重新跑全PnR；若M2改变源/约束/实现则需新同版受影响验证。

运行与验证
==========
Python标准库，无第三方依赖，无联网，无编译器或EDA调用。
在仓库根使用本机Python -I -S -B -X utf8执行本目录脚本：
inspect_original.py --output 本目录下全新直接子目录
source_identity.py --output 本目录下全新直接子目录
build_targets.py（仅首次；拒绝覆盖targets.json）
test_observations.py
verify_local.py --run-id r03（最终留痕；r04仅独立软件后继可用，不是工具重试许可）

verification_r01：提取0、派生0、13项测试12通过1失败（测试预期LOC抄错）；原双流/失败测试源保留。
verification_r02：提取0、派生0、13/13通过，输入/源码SHA前后同。
verification_r03：最终源码及两原ZIP纳入前后SHA，原双流、argv、cwd、退出码见RECEIPT.json。
两次初始交互命令引号/一处初稿成员数检查失败及片段覆盖缺陷见FAILURE_HISTORY.txt。
全部仅软件观察，13自检不替代主对话2验收器的正负报告测试。

交付边界
========
本窗口不提交/推送、不取号、不更新共享状态。总控统一综合发布和M2复核。
当前真正缺件：同次综合网表/实现数据库；base_s1/base_s2物理目标及两类定向报告；
真实voice→mix、PCM/I2S精确端点对及目标STA。由M2决定并获准后执行，非本窗口隐瞒必做项。
新原件不会由本窗口伪造。L0/L1准备完成不等于限定端点L5或138K整机/实物验收。
