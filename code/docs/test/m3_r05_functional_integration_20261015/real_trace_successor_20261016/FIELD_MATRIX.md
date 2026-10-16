# P1：R06 后继真实日历缺口与来源合同

本交付是 L0 静态合同＋软件 schema 拒收自检。REAL_RESULT=PENDING_REAL_CAPTURE；board_release_allowed=false。
不是新 oracle、真实采集、PCM 数学签收或板级放行。代码允许的唯一阳性 origin 是 SYNTHETIC_CONTRACT_SELFTEST。

## 精确身份

原 R05 = 6 ms watchdog FAIL。其 TB SHA 为 `6e677154d0a53ff97e794555ef57695e385a9963de43f1ac9135a54c32fc9777`。
既有成功 7 ms 后继按 R06 引用，TB SHA 为 `24e7407f6abfcc28ed9dd886f41539e8f07b64da6e67c5932abbe504f6b5096a`。
本次只读的连续捕获是 **由 R05 链派生的 R06 7 ms 后继，另含夜间 observer 增量**；不能说原 R05 PASS，也不能把观察增量称为原 R06 全树逐字节相同。
旧封存的名称、内容和失败收据全部保留。303 样本固定窗口数学重放仅 REUSED 限定软件结果，不提升为真实日历完整。

精确 M1 外 ZIP 750224 bytes / SHA `842fa8f75356090440a5e8237acafc209620d114f9e3c0ce2eab5ffdf30862da`，从既有 SEAL_CHAT9R02 ZIP 的原始内嵌成员读取，不重新压缩冒充原 ZIP。
根目录数学判据 SHA `d7a4ec69f04736fc414ab856c9e99893779e2b2192b16d2b727684fbba3e88c0`。
运行目录 INPUT_IDENTITY.json 给出载体、内嵌成员、实际 stage 全输入、源码及两份连续 capture SHA；SOURCE_BINDINGS.json 对每一标量字段给源模块、原 SHA、表达式、用途及缺件处理。

## 字段矩阵（所有沿均采；不是只采 commit）

| 字段组 | 必要字段／实际接点 | 既有捕获与缺口 | 期望来源与限制 |
|---|---|---|---|
| 时钟/复位 | cycle/time_ps/epoch/rst_n；每 posedge pre-NBA | 原公开流有 cycle/epoch/rst_n，输入流有 time_ns；没有完整异步复位边沿流 | 同源 TB 控制记录，首次低复位为 epoch0，后续每次 assertion 增1；不能按 ID 回绕猜 epoch |
| 事件入口 | event_valid/ready/data；accept=valid&&ready | REAL_INPUTS 有入口信息，**不是实际应用** | 独立 driver 发送队列＋router 控制 FSM 校验资格，DUT ready 仅对照；不能以 DUT ready 自报定义完整期望集合 |
| 事件实际应用 | applications 每项 event_seq/event_data/lane_mask/kind | 全缺；不得用入口+4替代 | 待新增公共观察口：分配生效、NoteOn/Off 到 lane、Program 写入、控制命令接受、退休、忽略；seq 为本 epoch 接受顺序，不能从 PCM 找事件 |
| 四路控制 | lanes[0..3] 每沿齐全：note_on/off、occupied、source/channel/note/generation/velocity/timbre | 全缺 | bank 内已有 router 接线，需受控只读透出；source/channel 各4位、velocity10位、generation32位；slot note容器8位，但本合同只接受合法 MIDI 0..127 |
| 全部 DSP 推进 | lanes[*].tick；math_valid/ready/accept/id | 全缺；未发布、取消和空槽推进都要记录 | bank 的 lane_tick 同时接四路 voice/envelope；u_pitch_mod 接受也记录，取消前 LFO 推进不回滚；禁止只保留有 commit 的 tick |
| FCW | lanes[*].fcw_observed | 全缺 | 对照量，不是期望输入；黄金按原事件、实际推进日历和冻结 ROM/算法推导 FCW，不从该输出倒推 |
| 请求 | request_valid/ready/accept/id/current_id | 原公开流只够接受后的账本，不足以独立证明接受前资格 | adapter 的 candidate_sample_* 与 current_id；source map 是提议端口，不是已接线的事实 |
| 效果接受 | fx_valid/ready/accept/id/left/right/clip_left/right | 全缺 | stereo_delay 的 input_*；PCM 是中间比较对象，不可直接作为完整声音黄金；效果历史从独立上游黄金及真实接受沿推进 |
| 效果配置 | config_valid/ready/accept/enable/delay/dry/wet/feedback | 原流只有顶层 valid/ready，无完整 payload/生效序列 | 原配置端口，config_take 才生效；enable/delay 改变时 flush，gain 改变不自动清历史 |
| 取消 | frame_tick、cancellations[{request_id}]、复位边沿表 | 有 frame_tick，缺逐未完成 ID 的取消账本 | 独立事务表由 request、epoch 和取消条件生成；空列表只能表示经过完整记录证明无取消，不可缺件填空 |
| 结果/HOLD | result_valid/ready/id/left/right/clip_left/right | 既有 first_valid=null，不能当0或未发生 | stereo_delay 输出；首次 valid 与握手分列；HOLD逐沿稳定，frame取消后未提交旧结果不接收 |
| buffer提交 | commit/id/left/right/clip、clip_count | 公开流已有 | commit为buffer握手，只计一次clip；不得把重复HOLD、静音或重复播放算新发布 |
| 播放/串行 | pending/play_left/right/underflow/bclk/ws/din | 原公开流已有 | 保留C既有限定消费结论；旧末尾截断不补造串行帧，不从串行PCM反推输入 |

applications.kind 拟议编码：0 allocation 生效；1 lane NoteOn；2 lane NoteOff；3 Program 写入；4控制命令接受；5退休；6明确忽略；7控制RAM应用。
一种入口事件可能在多个沿产生多项应用，不能要求一入口只一条；退休等自主事件需独立关联表，不得伪配新的 MIDI 入口。当前 seq 关联设计待 M1/M2 确认，软件 schema 通过不证明关联正确。
为避免异步复位短脉冲丢失，真实格式最终还必须附 RESET_EDGES(time_ps, rst_n, epoch) 并检查每个非时钟沿变化。当前 schema 仅检查采样沿 epoch：**不能接收 REAL，亦不声称覆盖子周期 reset**。

## pre-NBA 与独立性

采每个 posedge 的边沿前值，不使用 $strobe/post-NBA 代替。router 的寄存 note_on/off 在产生沿 NBA 后更新，lane 真正消费是后续 posedge 的 pre-NBA 高值；两者分别记，不混用。
观察口不导出 wave/env/phase 作为黄金。允许导出 `lane_tick` 和 math-request 的实际控制谓词，但不是把 bank phase 数值喂入数学 oracle。
效果 accept 后可能继续历史写入/排空，即使 frame_tick 撤销结果资格；不能删除被取消事务来重建历史。

SOURCE_BINDINGS 为冻结源码到**拟议**观察接点的静态绑定，不是新采集来源证明。未来必须给新增 observer 源 SHA、接线树 SHA、命令、工具依赖、授权/消费记录和全流校验，才可另行设计 REAL 校验路径。
现检查器只做严格字段/范围、全四lane、连续沿、采样间隔、epoch、握手算术及尾记录数拒收，不验证 router FSM、真实 ready 资格、应用匹配、全部语义、独立 PCM 或签署真实声音。所有成功也输出 PENDING。

## 精确待决事项

请 M2/M1 核准最小只读观察口（见 TB 目录 PROPOSED_OBSERVER_WIRING.diff）和 event_seq/自主退休关联，以及异步 RESET_EDGES 格式；不修改原算法或冻结接口。
核定新精确隔离树、实际工具身份、独占输出及新一次额度后，另由获准执行者采集。旧7ms ModelSim额度已消费，本包不含执行入口，不启动 ModelSim/Gowin/板卡。
