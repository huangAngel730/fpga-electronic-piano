# R07依赖/消费静态自审：两项实施差额与互通边界

基线4fd3366e42fd2356e56eb96eee70b6771afd4bb1。仅L0阅读/文件身份核对，新程序/import/自测/HDL/EDA/设备均0；不审签正在实现的R07最终代码。输入22份SHA见INPUT_IDENTITIES.json，4份M2新候选现场SHA与发布清单相同，见SOURCE_REPLACEMENT_IDENTITY.json。没有重封旧原件，board_release_allowed=false。

## 两项具体差额（总控需决定下一动作）

1. **R6-5尚缺按新公式生成独立FRAME_PLAN的入口。** 已发布event_calendar.py:131/157/380/423只读取/核计划；fixtures.py:60–64手写100000/60000拍级合成帧，:161–169包装为`M3_R06_INDEPENDENT_FRAME_PLAN_V1`，不是新32位NCO/实际reset窗口生成器。已发布M3软件内检索STEP=659706977，另有旧`D/fixture.py:22–38`的独立闭式公式，但其schema=`D_INPUT_PLAN_V1`、固定38000拍/两个epoch/诊断PCM，是旧夹具，不能直接代R07实际计划，也不应复制旧组重跑。R07第46/70行要求R6-5唯一生成计划；其初组+修复已消费，当前四新包许可不自动补发R6-5新组。应由总控交M2绑定该增量的独占后继/输入/预算；A只记录实际FRAME，R6-6只核计划，均不另造期望。
2. **R6-8三根授权目录均未出现，不能把实测受阻写成离线准备已完成。** R06第99行允许无板准备同版采集步骤/格式；已有`M3_138K四复音同版现场实测任务单_2026-10-16.md`及`hardware/m3_138k_electrical_preparation_20261015/B3_CAPTURE_PLAN.txt`可只读复用“固定音→四独奏/合奏→逐放/力度/reset”、原输入/数字/模拟/会话字段与同时间基准延迟思路。前者首页明确其旧PG484下载/引脚已废止；后者包含后置T052及旧板测点，不能搬来当Pro接线/新许可。尚需R6-8负责人在原授权写集形成Pro同版步骤与字段格式并标全实测NOT_RUN；不需先等板卡才写准备，但本只读窗口不代写/扩写集。实物和单次SRAM仍待独立准入。

## R06消费不得重置（依据各包RESULT/失败史，本轮未运行）

| 包 | 已留执行/修复 | 本轮可否恢复 |
| --- | --- | --- |
| R6-1 | RUN_01 15例；RUN_02唯一修复7增量 | 否；真实闭包仍有dds_oscillator列表差额，词法报告不是实际编译失败结论 |
| R6-2 | RUN_01保留复位初态缺陷；RUN_02修复13正/4负 | 否；复用修复版driver/计划，不用旧错误版刺激 |
| R6-3 | RUN_01失败，RUN_02原修复；后获额外许可的RUN_03修CANCEL活动ID（15例） | 否；未用RUN_04/05不等于当前可继续。cancel_reason≠req_id |
| R6-4 | RUN_01一组7场景；3个Python假进程 | 否；不是实际工具准入 |
| R6-5 | RUN_01夹具写入失败，RUN_02唯一修复14例 | 否；合成计划工具准备≠新公式生成器齐套 |
| R6-6 | RUN_01一组20例，成功未修复 | 不重跑成功组；有新缺陷才可按有效许可定向处理 |
| R6-7 | RUN_01 wrapper失败及其ATTEMPT_02_REPAIRED 17例 | 否；物理UNKNOWN不升级 |

R07 A/B/C/D是四个不同新包，各1组≤90秒；仅新缺陷可一次≤60秒对应增量，跨窗口共享，先冻结RUN_SPEC/源码/输入/工具/输出。此窗口消费0，不领其中任何一组。R6-8无已执行板测，当前也没有可用下载额度。

## 新到件与仍缺项

- 新38obs来自`M2_R06_OBSERVER_EXPORTS_V1`，采样沿`POSEDGE_PRE_NBA`，真实`obs_core_clk`和`obs_polyphonic_valid`须连入。9内部+16既有路由和TX扩展已有静态候选；不能再笼统报“无公开口/无旁带”。源码身份相同不等于已编译或行为等价。
- SOURCE_REPLACEMENTS的schema=`M2_R06_STATIC_SOURCE_REPLACEMENT_PLAN_V1`，冻结基包SHA `931b7d2bbfd7ac056707542931101ff844b125936762748e344536d9be6c1ba2`；69单元排除旧board/core/旧TB三项、添加4个R06候选，计划70。A/B新增TB和复用driver还须显式入各自source list，不能把70当最终TB总数或执行许可；R6-1已报告的旧列表dds差额不因这份计划自动消失。
- M1 A0/A1/B0已发布，仅历史窄profile准备；**不再报M1整包未到**。仍缺ROUTING_PLAN的M1_19：apply_valid/data、occupied/releasing/note_on/note_off/retire、slot sources/channels/notes/generations、advance_mask/frame_req_id、effect input valid/ready/id/left/right/clip_mask。另apply_event_seq、config_payload、cancel_reason、audio_stable策略/出处、独立cycle/epoch/reset/finish仍须实际实现或绑定。共同advance为同沿mask1111，不能按occupied mask裁掉或分四拍。

## A/B/C/D必须对齐的具体合同

| 边界 | 互通要求与精确出处 |
| --- | --- |
| 版本/形状 | M2合同=`M2_R06_PUBLIC_CAPTURE_CONTRACT_V1`；61行schema `$id=M2_R06_NORMALIZED_ROW_CANDIDATE_V1`，NORMALIZED_ROW_SCHEMA:69 additionalProperties=false。新TX mask/metadata_valid/req_id_valid/error/overflow不能硬塞旧61行或丢弃；须显式扩展版本/伴随记录及投影差额。R6-3输出是`M3_R06_CANONICAL_61_ROW_V1` envelope，字段在`.fields`，并非直接61扁平口（normalize_intake.py:557–570）；R6-5 load_jsonl:77–90读扁平字段。C/D需明确取.fields的只读适配，并在索引保留envelope全部身份，不把两种文件称同schema。 |
| 原行/同沿 | A保留每个实际core沿的raw行号/cycle/epoch、真实输入SHA及同沿顺序；R6-3用input_line/same_cycle_order/original_event_order/events_on_edge/missing_reasons。缺项保持X/null及原因，29列只作有损视图，不反填原61。A/B/C/D的关联索引须追到原raw行，不重排/挪cycle凑旧profile。 |
| 采样/epoch | 在obs_core_clk posedge PRE_NBA采同一原子元组，不能`#delay`后把NBA新值冒作该沿。独立RESET_EDGES保留异步断言/锁定事实，epoch由此绑定，不给RTL假常数。首次功能沿是PRE_NBA看见同步reset高的沿，不是前一NBA释放沿；FRAME_PLAN_RULES末行明确release_cycle语义。 |
| FRAME F与A | 记录frame_tick原点F及req_valid&&req_ready实际A；A可F+1或更晚。内处理严格t-F<833并早于下一独立FRAME；TX采纳833/834周期另核。旧D3投影只帧预算诊断，不能A改F。计划schema=`M3_R06_INDEPENDENT_FRAME_PLAN_V1`；由R6-5用`ceil(128*k*2**32/659706977)`、冻结reset/stop生成，含idle/cancel后全部FRAME至finish。 |
| TX | commit不是采纳；保存pending→held及result握手时双clip。clip_mask bit0左/bit1右，旧tx_clip仍1bit OR；req_id_valid=0映射null，数值ID0合法；metadata_valid=0不丢真实TX样本。HOLD继承原ID/PCM/clip，startup无请求ID；错误/overflow不补0伪正常。 |
| B等价框架 | 原/新实例共用同一冻结外部字节/时钟stub起相位/reset/比较窗；只比既有外部输出和可解码UART STAT，诊断口差异单列allowlist。旧实例没有公开状态口就NOT_PUBLIC，不跨层读私有DSP，也不为比较增旧口；未运行TB只能L0。 |
| C数学桥 | 复用`M3_R06_MIDI_STIMULUS_PLAN_V1`、原61行/envelope与真实应用/账本。M1旧`R06_SETTLED_SIMULTANEOUS_LANE_TICKS_V1`不覆盖FRAME/A、同沿组合、startup/HOLD/异步reset/finish，须PENDING_UNSUPPORTED_PROFILE，保留差额，不删行或修改旧M1。M1_B0_R06C1_BOUNDARY_REVIEW对应表已逐项说明。 |
| 结束/来源D | A必须有唯一真实END/MONITOR_END及结束原因/尾水位；EOF不等于finish，有未采纳commit/半串行词不得假正常。D把capture_id绑定source/ROM/driver/observer/参数/工具/argv/双流/退出/消费和raw→plan→projection→PCM/TX→finish链；换源码/日志/投影或缺原件必须拒收。JSON自填approved/authenticated不能生成M2准入或独立真实性。 |

R07当前A/B/C/D最终代码尚未在本报告范围内验收。具体先行缺口是上面两项实施差额，以及扩展TX/61-envelopes的显式桥接口；其余为验收条件，不冒称发现了尚未读取实现的缺陷。需要总控时再只读核最终接口，当前必要报告齐套提前收工。
