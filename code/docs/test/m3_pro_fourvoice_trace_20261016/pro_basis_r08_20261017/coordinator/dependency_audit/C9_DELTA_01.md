# C9 合同差额及后继接入阻断（夜间任务5）

基线 `16ac226552f6fb65347b229b8fad42146ed45644`。本次仅 L0 / STATIC / NOT_RUN；只读 M2 转交、实际 C9 schema/exports/捕获合同、M1 勘误与必要前驱消费点。没有运行、导入或编译候选，没有消费 R08 组、HDL/EDA/设备额度；没有改实现、暂存区或原封存。源码与文档身份见 `C9_DELTA_01.json`。

## 实际合同差额

- C9 schema `$id=M2_R06_NORMALIZED_ROW_CANDIDATE_C9_V1`：74 required，additionalProperties=false，保留 null/X/Z；exports 为 67 个公开 obs 口、28 条新增路由。67 口、74字段、嵌套 R7-A record 的字段/扩展数是不同概念，不能混数或靠裁剪凑旧格式。
- 相对现存旧 61 字段 schema，增加 13 字段：已有 TX 五项 `tx_metadata_valid/tx_req_id_valid/tx_clip_mask/metadata_error/frame_id_overflow`，加本次八项 `apply_kind/apply_mask/router_apply_seq/router_apply_seq_valid/config_take/upstream_clip_mask/effect_clip_mask/feedback_clip_mask`。因此“66→74”与“旧61→74”一致，没有少算或删除旧字段。
- `apply_valid/data` 和十九项槽/推进/效果观察在 C9 已有真实公开路由，不再整体沿用旧 `PENDING_M1_SEMANTICS`。但独立 `apply_event_seq` 没有公开口，仍需独立输入计划→实际 `event_valid&&event_ready/data` 接受记录→有效 router seq 的有证映射；不能以内部计数同数值替代。`audio_stable` 仍无已批准真实策略/公开实现，继续 PENDING，禁止填 0 或固定 accept+1。

| 必保信息 | C9 实际语义与最易漏项 |
|---|---|
| kind/mask/router seq/valid | kind 0 NONE、1 ALLOC_COMMIT、2 NOTE_ON_CONSUME、3 RELEASE_COMMIT、4 NOTE_OFF_CONSUME、5 PROGRAM_COMMIT、6 CONTROL_ACCEPT、7 IGNORE、8 RETIRE；四项一起保存，按 epoch 和有效位解释 u32 序号，回绕不保证唯一 |
| 无效零哨兵 | kind3/4/8 的 data=0、router seq=0、valid=0 是无原事件因果标记，不是有效全零输入事件；真实有效 seq=0 仍可合法。kind0 闲置时原始 data 也可保留旧值，不能仅凭 payload 造应用事件 |
| 多阶段同 seq | kind1/2 可以共享同一有效 router seq，按原始行/周期和阶段保留两次观察，不能按 seq 去重或强制一条接受只出现一次 apply |
| config | 以实际 `config_take` 解释 62bit payload：[61]enable、[60:45]delay_samples、[44:30]dry、[29:15]wet、[14:0]feedback；保持原位宽、X/null，不能从请求值或固定下一拍代造 take |
| clip | bit0左/bit1右；三项 upstream/effect/feedback 各自保留，还要保留 effect_input/result/TX 原观察，不能全部压成 tx_clip/任意一个 OR |
| 请求 tag 与 F | `advance_frame_req_id` 接 M1 `obs_advance_frame_id=pending_req_id`，是请求 tag，语义不是 FRAME F 编号；两者可偶然数值相等，不能直接别名，也不能强制数值必须不同 |
| 四 lane 推进 | 实际 `lane_tick=rst_n && !frame_tick && phase==ADVANCE && live_identity_matches`；`advance_mask={4{lane_tick}}`，四路 DDS/包络 sample_tick 都取该 tick。不能从 frame_tick、A 或 occupied_mask 造推进；只有 1111 才是已知四 lane 共进，X/null 不升级为 true |
| NoteOn 勘误 | M1“分配发生在前一沿”文字待所有者确认；ALLOC_APPLY 的 E 沿、CTRL_ON 最早 E+1 握手、bank 最早 E+2 消费且背压可更晚。以实际脉冲为准，不生成 allocation+1/accept+1 期望 |

采样仍为 `posedge obs_core_clk PRE_NBA`，按 rst_n/epoch 和 obs_polyphonic_valid 限定；fixed-tone 分支的零输出不构成真实多声部观察。

## 后继具体阻断与最小接手事项

这是新合同迁移清单，不把历史已测组重新判失败。21:24–21:25 的只读目录快照尚未见 M3 `c9_binding`/`r06c9` 后继到件，以下定位针对前驱代码；待新件后只核其增量，不能宣称新件已有同样缺陷。

1. **夜间2，R7-A/R8-02**：旧 `public_capture_tb/PORT_MAP.json:365–385` 仍将本次已路由字段整体列 PENDING；旧 `r7a_public_observer.sv` 端口/原始行未含 C9 新观察。须在独立 C9 后继中同版绑定 C9 sources/schema/exports，采完整公开值并保留缺件原因，旧原件不覆盖。R8-02 前驱 `selftest.py:29–37` 的 actual 用例仍指旧 observer 和旧 A；其 `m3r08_02.py:233–247` 仅强制缺失 input，允许 output 留空，所以端口解析 ACCEPT 本身**不能证明 67 口已全部采样**。C9 静态绑定应额外列全期望口→实际连线→raw/normalized 字段（及明确排除理由），不是只改模块名或复用旧 PASS。
2. **夜间3，R7-B**：需同版 C9 来源及阶段合同，保留 kind/mask/router seq/valid、config_take 和三 clip；特别不要按 seq 去重，不用固定延迟解释 NoteOn。独立 apply_event_seq/audio_stable 继续待件，不让真实路由齐备冒充数学期望/输入因果齐备。未有新 B 原件，本轮不代签实现。
3. **夜间4，R7-C**：前驱 `oracle_bundle_bridge.py:419–420` 明确只收 61 字段，直接送 C9 74 schema 会被拒；不能裁掉13字段绕过。`build_index:359–368` 的派生索引只保留旧 apply seq/推进，后继须保留完整原始阶段信息与有效位/原因。另 `tri_nonzero_mask:212–217` 把任何非零值当 common_advance，`1` 也得到 true；C9 四 lane 共进不得据此成立，后继按精确 4bit 1111 判定，保留 partial/X 原值并给差异或待件原因。此为静态反例，未运行。更新 schema/record/扩展的身份绑定与所有消费点，不仅将 61 改成 74。

## 收口边界

M2 C9 路由与 M1 原软件记录仍仅 L0，不能签行为等价或真实捕获通过。M1 NoteOn 文字更正、独立输入计划映射、audio_stable 策略、真实同版 trace/完整 FRAME_PLAN 和真实 PCM/ID/clip 原件仍待相应责任方。新 C9 没有新增或恢复 R08/R09 执行许可；本轮不重跑任何旧组。

本报告仅写 dependency_audit，供总控只读取件并随最终 C9 包统一发布；未提交、未推送、未发送跨窗口消息，既有暂存和原封存未动。`board_release_allowed=false`。
