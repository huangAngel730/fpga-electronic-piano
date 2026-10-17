# V0396/C5窄核：当前未发现消费冲突

基线 `40d78131e8ed50643dd169816f7bfc7149a8ced9`。只读最新M2限定复核、更新后的总控PLAN及指定包台账，未运行程序/import/测试/HDL/EDA/设备，未改旧报告或实现。此文件只补充先前静态报告，不倒改旧事实；L0。

| 核对项 | 结论与依据 |
| --- | --- |
| R6-4原修复组 | 本次目录快照仅RUN_01，无r07_fix或第二组。RESULT:11记原功能组1/1；GROUP_RECEIPT:6–7为90秒/group1，原组三个worker/并发消费marker属于同一组。:292、976的expected_error/exit7是预期负例，外组exit0，不是修复组或新失败重试。未见其单次≤60秒修复已消费。 |
| R6-6原修复组 | 同样仅RUN_01，无r07_fix或第二组；RUN_01/receipt:21–23为5.205964秒/无超时/exit0，:44为software_groups_consumed=1；RESULT明确without repair/no second run。未见其单次≤60秒修复已消费。 |
| 当前使用条件 | M2新报告:30明确允许在先核共享台账后使用R6-4/6原未消费≤60秒一次定向修复。故总控分派与已读台账**未发现冲突**；不能恢复90秒原组、全量重跑或升级真实工具。该结论不是占用/锁定额度，执行者启动前仍须核本包并原子标记一次消费，先冻RUN_SPEC/输入/源/输出，失败原件保留。 |
| R6-3/R6-5新候选 | 仅L0/NOT_RUN的计划准确。M2报告:9/30确认R6-3原RUN03是2合成成功+4PENDING+9拒收，原CANCEL增额成功停止、未用轮不转HOLD/profile；R6-5原初组+修复用尽。旧L1夹具事实保留，不能写“旧包只有L0”，但新C3/F-A/FRAME_PLAN返修没有可用软件组。 |
| 跨包调用 | R6-6获准自身定向组，不应暗中调用/运行R6-5新生成器或R6-3新摄取候选，同时仍把它们写NOT_RUN。可只读用冻结的定向输入文件测试R6-6自身；若需要执行其它新候选，必须由M2明确绑定范围/预算并如实记等级。 |
| C5源决定 | SOURCE_DECISION_R06C5.json:2–3为`M2_R06C5_SELECTED_SIMULATION_SOURCE_V1`/`SELECTED_STATIC_NOT_COMPILED_NOT_ADMITTED`，已选71单元/9ROM/73字面module。派生DDS仅取原[0:1240]+LF，1241B SHA `303e3a9927e743d4149ceae4bb8754ebb8abdfb14638d407254b8e555dfcd3bd`；唯一共享ROM定义保留m1td文件。不能再报“等M2决定是否整份追加DDS”。 |
| C5保留边界 | 决定JSON末段HDL_executed=false、execution_admission=null，旧stub/PLL header仅仿真；完整TB仍待R7-A，M1真实语义/G0–G3仍PENDING。SOURCE_CLOSURE_R06C5.zip已交176361B，声明SHA `2fc5518a35600f67d025aa2efe55e6b436daa5a04b592053f7326385b42134fb`。本次只核文件身份，不重新解包/验源码功能；A/B静态绑定不能冒称编译/行为等价。未发布C4不混入。 |

本次未发现上述台账/等级/源决定表述的具体阻断。先前RESULT中的“旧69列表DDS待M2决定”仅保留形成时事实，当前由C5决定覆盖；“R6-3/5修复额度用尽、需额外绑定”的边界不变。总控新PLAN对R6-4/6各一组≤60秒、R6-3/5仅新L0、C5静态绑定的分派与M2:30相符。R6-4修复仍只限固定Python夹具，不解决或放行旧P7/真实工具执行安全；所有真实工具/物理/板测继续未准入，board_release_allowed=false。

只读查询范围是这两个指定包的目录/原收据及当前新PLAN，并非跨所有机器的消费保证。执行期间并发变化应以启动者实时台账为准，不把本报告当可重复用的执行许可。输入SHA与快照在同名JSON；未发送成功不写已送达，总控可直接领取。
