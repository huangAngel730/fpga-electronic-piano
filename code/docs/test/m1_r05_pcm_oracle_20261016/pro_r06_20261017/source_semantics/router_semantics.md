# R6-1 router/slot：真实语义与最小公开出口

2026-10-17。本件是 M1 独占候选源码与语义说明，当前仅 **L0 静态候选**，没有运行 HDL、EDA、旧测试或新软件组。新软件组由主窗口整包统一消费。`REAL_RESULT=PENDING_REAL_CAPTURE`，`board_release_allowed=false`。尚不能以此候选冒称 Pro 真实源树或硬件通过。

## 来源与替换范围

基源为 `code/docs/test/m3_r05_functional_integration_20261015/night_20261016/RESUME_R02/RUN_01/stage/inputs/sources/m1td_polyphonic_event_router.sv`，模块名 `m1td_polyphonic_event_router`，10,466 字节，SHA-256 `f86dc783534c7e3897197d3a967c94d614642196c8d67bff9493d70d1a5fc808`。已只读核其与冻结 R06 ZIP 的 `inputs/sources/m1td_polyphonic_event_router.sv` 逐字节相同；载体 `code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1TD_R06_XSAFE_7ms_ModelSim输入_20261016.zip` SHA `4be2b4c185691a3e493827a3a95303fa90f49ba6336eb4a8e0183942c8f05483`。

候选仅位于 `code/rtl/audio/m1_pro_observer_r06_20261017/m1td_polyphonic_event_router.sv`，保留原模块名，供明确 source-list **替换原同名编译单元**。不得把原件和候选同时加入编译列表，不改原件、正式顶层、公共包、算法或 ROM。新增端口/逻辑分别包在 `BEGIN/END M1_OBSERVER_R06_PORTS` 和 `BEGIN/END M1_OBSERVER_R06_LOGIC` 标记内；去掉两标记块后应保留原始功能源。端口使用前导逗号，原 `slot_generations` 行保持原样。

## 采样规则及端口

所有新增出口均为 `wire`，组合描述 **当前 `posedge clk` 的 pre-NBA 条件**，不是在观察器中再打一拍。已有 slot 数组仍为原功能寄存器。某 `*_COMMIT` 条件为真时，观察行里的 slot 数组是该沿更新前的值；本沿 NBA 完成后更新的新数组在下一 pre-NBA 行可见。`*_CONSUME` 则是原注册脉冲已高的那一沿，恰为 voice/envelope 读取该脉冲的沿。

| 新增端口 | 位宽 | 含义 |
| --- | ---: | --- |
| `obs_apply_valid` | 1 | `obs_apply_kind != 0`，包括有原事件关联与无关联的实际动作 |
| `obs_apply_data` | 64 | 有原事件关联的动作取原 `held_event`；无关联为 0 哨兵，不能当真实全零 NoteOn |
| `obs_apply_kind` | 4 | 下表版本化操作码；不是 `performance_event_t.event_type` |
| `obs_apply_mask` | 4 | 对应操作的目标/消费槽 mask，不能跨 kind 混解释 |
| `obs_apply_seq` | 32 | 仅在 `obs_apply_seq_valid=1` 时有效的真实入口接受次序 tag |
| `obs_apply_seq_valid` | 1 | 关联可信有效标记；延迟 release、off 消费及自主 retire 均为 0 |
| `obs_retire_mask` | 4 | `rst_n && state==RETIRE && cmd_ready` 时的 `1 << target_slot`，否则 0 |

`obs_retire_mask` 表示该沿实际退休动作，不是 `retire_pending` 待办集合。该沿 slot 仍显示更新前状态，下一行才看到 `occupied=0/releasing=0`。复位清除单列由 `rst_n`/独立复位边沿表达，不伪装为 retirement。

| kind | 名称 | 精确条件/原源行号 | mask | 原事件关联 |
| ---: | --- | --- | --- | --- |
| 0 | NONE | 没有下列动作 | 0 | 无 |
| 1 | ALLOC_COMMIT | `state==ALLOC_APPLY && slot_valid`（143–153） | `1 << allocated_slot` | `held_event` / held seq 有效 |
| 2 | NOTE_ON_CONSUME | `|slot_note_on`（脉冲产生155；bank消费128/132） | `slot_note_on` | `held_event` / held seq 有效 |
| 3 | RELEASE_COMMIT | `state==RELEASE_APPLY && release_target_valid && release_slot==release_lane && release_matches`（164–168） | `1 << release_slot` | **无**；没有被冻结的延迟原因 tag |
| 4 | NOTE_OFF_CONSUME | `|slot_note_off`（脉冲产生166；bank消费128/132） | `slot_note_off` | **无**；不能从当前 held_event 猜原因 |
| 5 | PROGRAM_COMMIT | `state==CTRL_TIMBRE`（156） | 0 | 有效；修改 source/channel 的后续 NoteOn 音色 |
| 6 | CONTROL_ACCEPT | `cmd_ready && state in {CTRL_OFF,CTRL_PEDAL,CTRL_PANIC}`（157及81–87） | CTRL_OFF为`1<<target_slot`，其他0 | 有效；表示 sustain 接受命令，不表示已生成 NoteOff 或已退休 |
| 7 | IGNORE | `state==IGNORE_EVENT`（170） | 0 | 有效；被接受后明确忽略的入口事件 |
| 8 | RETIRE | `state==RETIRE && cmd_ready`（171–173） | `1 << target_slot` | **无**；自主生命周期完成，不是新入口事件 |

上述各条件另有 `rst_n` 门控。原状态机使这些动作在正常状态下互斥；代码按表中顺序选 kind，并未修改原功能优先级。若使用者观察到冲突，应视为合同错误，不推测遗漏动作。

## 接受次序与应用关联

新增独立诊断寄存器 `obs_next_event_seq_r`、`obs_held_event_seq_r` 和 valid 标记，只在原真实 `event_valid && event_ready` 时分配 tag；首次接受为 0，随后 unsigned32 模 `2^32` 递增，低有效异步复位清零。tag 不参与任何功能反馈。一个 epoch 内若达到计数回绕，采集器必须保留回绕事实且不能再声称 tag 唯一；不能依靠这个有限宽 tag 解决无限窗口的唯一性。

入口接受条件来自原 router 65、129–130行，受 IDLE、sample-owner、待释放/退休影响。原 bank 53、56、79行将同一次有效/就绪事件同时送 router 与 control RAM。**接受、分配生效、NoteOn 实际消费是不同沿**；同一 tag 可先出现 kind1、再出现 kind2。不得要求“一次接受只一条应用”，不能令 apply seq 自行按应用次数递增，也不能由 req/frame/PCM 推断原输入关联。

NOTE_ON_CONSUME 沿，即使 router 同时接受下个事件，pre-NBA 的 `held_event`/held seq 仍是原 NoteOn；下一事件的数据与 tag 在本沿 NBA 后才覆盖。PROGRAM/CONTROL/IGNORE同样使用原 held token。

延迟释放的原码只有 sustain `release_mask/release_generations`，没有保留触发来源事件 tag；踏板解除、panic 或早前 NoteOff 的因果链不能可靠归约成当前 `held_event`。因此 kind3/4 的 mask/slot 状态是实际观测，但 `obs_apply_data=0`、`obs_apply_seq=0`、`obs_apply_seq_valid=0`，应标 **NOT_ORIGINAL_EVENT / CAUSE_UNRESOLVED**。kind8 同样无原输入关联。后续若需完整释放因果，必须另设计不反馈功能的原因 tag 保存合同，不能把本候选无效哨兵当有效数据。

## slot 身份和生命周期

原 router 公共口继续原样透传：`slot_occupied/releasing/note_on/note_off[3:0]`；`slot_source_ids/slot_channel_ids[15:0]`；`slot_notes[31:0]`；`slot_generations[127:0]`。槽 i 对应 source/channel 的 `[4*i+:4]`、note的 `[8*i+:8]`、generation的 `[32*i+:32]`，note高位固定0、有效MIDI范围0…127。位宽依据原源13–20、31–38、146–152行。

- occupied 包含 active 与 Release，并非物理键按下。active count 66–67行正是 occupied mask 的人口计数。
- ALLOC_COMMIT 更新 occupied=1、releasing=0、velocity/FCW/timbre/note/source/channel，同时该槽 generation 加1（143–153行）。覆盖新分配、同身份重触发和抢占；只增加被分配槽，不按每帧或所有槽增加。
- 真正 NoteOff 脉冲发生在 release 操作完成处（164–167行）；占槽保持1。sustain可以因踏板而延迟释放，CONTROL_ACCEPT不是等价的off脉冲。
- `release_done` 在 bank 135–136行要求 `rst_n && occupied && releasing && envelope_state==0 && !slot_note_on`。router 121–122行先保存 pending generation，再经77、128、171–173行核 live generation并退休；不能把done当同沿已退休。
- RETIRE仅清 router 的 occupied/releasing/pending，**不清**原 source/channel/note/generation（171–173行）。未占用槽的这些寄存值是保留值，必须以occupied判断身份是否有效；不要用sustain内部退休时清零的副本代替router公共generation。
- `slot_note_on/off` 每个非reset沿默认清零（119行），满足条件才NBA置位；直接导出原脉冲，不重新推导或延长。
- 原低有效异步复位110–117行清原身份/槽状态及generation；不是本观察增量自行规定的Pro板级复位或PLL稳定策略。

## 复用限制

本候选只增加诊断。原 `held_event`、状态转移、仲裁、allocator/sustain接线和所有功能寄存更新保持原功能源。新增7口需由bank/audio/chain及M2观察壳逐级显式连出，不能用私有层级读取替代。候选必须与M2最新冻结源字节核同并列入最终闭包后才可准入；原R06来源证明不等于当前Pro实际采集。

`apply_valid/data` 不再假称单一“所有状态同时应用”时点，kind明确拆分上述实际行为。旧窄黄金中一次 `event()` 的抽象操作不能直接替代这里的多沿数据；M1数学适配需分别消费身份更新和实际on/off沿，M3保留完整原始记录。延迟释放原因、同版Pro采样/复位合同与真实trace仍待闭合。
