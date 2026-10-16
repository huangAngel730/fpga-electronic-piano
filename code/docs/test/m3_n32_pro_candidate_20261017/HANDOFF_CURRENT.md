# 夜间任务2：E4 N32 离线交付（PARTIAL）

本轮完成授权内可执行的新隔离联接与定向证据；完整E4/T061仍PARTIAL，board_release_allowed=false。基线ad2de2169230dc8fd9f4b6f8157d384306c2479a。只新增任务单五处目录，未修改旧分配器/ROM/M1数学/正式top、时钟、约束或共享状态。未提交、未推送；夜间任务1串行发布。

## 已得到的结果

N4→N8→N16→N32同源参数化B/pROM后端＋原运输模块，通过真实ModelSim SE-64 2020.4执行及独立Oracle逐lane/PCM/clipped核对。四档各64接受＝60发布＋3取消＋1复位取消；每档32运输提交、21个833拍间隔与10个834拍间隔、独立PT8211解码左32/右31半帧；请求到提交最大分别69/109/189/349拍，均小于833。每档全部槽有真实非零贡献、满槽FCW互异，公开phase/FCW/ADSR/身份由既有独立参考检查。S播放与串行黄金来自已数学核同的T提交，再经独立pending/held模型，未以DUT播放值自供黄金。

11个实际RTL坏例：偷音、重触发、CC64延迟、Release ACK、HOLD、cancel、reset、结果ID、运输左PCM、不退休各命中唯一首Fatal；clipped行为变异仿真正常结束，独立checker退出1、拒收码K_ID_PCM_CLIPPED_INDEPENDENT_MATH。实际差异K位于原stdout292行/cycle629，sum20224应clip0而返回1；原收据定位的是同cycle组首F290行，原件保持不改。

N32另有4802请求/真实推进、65个done观察、真实D累计OR=ffffffff且occupied清零；尾段只签生命周期L2，不签尾段逐样本数学。短窗口独立数学/期限/运输/串行为限定L3。冻结piano波表不证明纯正弦、32可闻独奏或32独立谱峰；左右相等，不覆盖不等左右交换；正常clip0，不新增实际正负饱和边界专项；完整ADSR/长压力使用旧原件范围，不重跑1300/FULL。

## 原件与失败史

实际消耗5/6组（总runner约70.656秒），剩余1组未用，成功后停止。R1编译退出2：quiet_tail声明顺序；R2真仿真0、checker1：合法末尾同cycle R/END；R3前三档通过，N32真仿真0、checker1：TAIL_END至真实reset前生命周期观察；R4 N32复用捕获核同＋7坏例通过，错误ID先触发E4_DEADLINE_OPEN而非预设E4_ID，正确保留为失败；R5只加立即valid核ID断言后重测该坏例及三个未跑坏例，13条调用中12条退出0，唯一clip checker按预期退出1，整组退出0。所有失败与修复原件完整封存，不将错误拒收冒称目标坏例通过。

正常四档精确TB SHA38265540a81990ca61bb6e4a4217a4c8d52fc99234f0b4575f12a33b11812bb9；R5增量坏例TB SHA65281fdbef1b912ee6194017bc26b93adb349ee0ede47896e3e06bc3ffda9501，仅增加ID监视。没有声称后者重新跑过正常四档。N4的R2真捕获在R3换checker复用；N32的R3真捕获在R4换checker复用；绑定均核原receipt/工具/全部编译HDL、ROM、include和独立模型同字节。

FINAL_RECEIPT.json含每条实际argv/cwd、退出码、耗时、双流SHA、每组ISO时间及源码/ROM/工具前后身份入口；原字段虽名_utc，组时间实际带+08:00，以显式时区为准。单条调用未单独记墙钟起止，标UNKNOWN；动态加载DLL未逐进程追踪，只有已枚举ModelSim EXE/DLL身份，不能称全动态依赖已测。SELF_AUDIT.json记父窗口及两个只读子智能体自审边界，未启用审核员制度。封包含原源码/数学/ROM快照、双流和失败记录，不含work/qdb/wlf编译缓存。

## M1/M2续做与集中交接（待用户转发，尚未送达）

M1：若最终验收需要纯正弦32频独奏/混合，请确认与冻结piano模式隔离的测试模式、phase→sine ROM、增益/混音/clipped数学口径；本轮未换ROM。现有V释放批次公开payload未作完整独立逐字段签收，不扩大为全口径覆盖。

M2：收到同版新Pro source/ROM/IP/top、完整FPG676料号/修订、商业许可及独立候选CST/SDC后，决定E4候选物理执行；当前综合/PnR/Setup/Hold/Recovery/Removal均NOT_RUN，条件2轮额度消耗0，不以旧PG484资源或6.109MHz替代Pro结果。正式接入仍遵基础Pro四声→双音色→E1→E2→E3→E4；获准同一.fs、恢复SHA、电气核验和本次SRAM许可齐备后再做实物32路频谱、音频与异常原件。夜间任务1接手统一Git门禁/发布与原件转交，本窗口不动index/编号/共享状态。

交付文字勘误：归档HANDOFF.md的R5退出计数句以本文件为准；只更正文案，13条实际调用及退出码均见原RUN_RECEIPT，未改原日志、收据或已封ZIP。
