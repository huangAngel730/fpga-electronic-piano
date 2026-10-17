# R6-2 / R6-3 限定只读复核

本次只读查看附件与 `ffc8b4cc94606cdd70941d2abaee8bbd93a654c5` 的精确 Git 对象，没有执行被审 Python、HDL、EDA 或硬件，没有修改被审成果、共享状态或 C4 十项文件。文件校验脚本和结果独占本目录。实际核验记录见 `READ_ONLY_AUDIT.json`。

## 身份与原件结论

- 外层证据 ZIP SHA-256：`ac9bcb31d21b3af247ca6305b2d83c76922a657ae743a5c4690d294ceb1ca205`，与用户给定一致。
- `normalized_intake/KEY_HASHES.json` 的 17 项、`midi_stimulus/FILE_SHA.json` 的 26 项，共 43 项正文大小及 SHA 全核同。其中 10 件最终生产源码/参数/用例/TB 直接从该提交读取核同，33 件包内原件核同。
- R6-2 的 `RESULT.md`、`SELF_REVIEW.md` 发布正文分别与附件中的旧正文相差末尾一个 LF，前后 SHA 均符合 `POST_SEAL_WHITESPACE_NORMALIZATION.json`。R6-2/3 的功能源没有受到此 14 项 EOF 归一影响。旧原件 SHA 和发布正文 SHA 需分别记，不把归一后正文伪称成当时运行的原字节。

## R6-3 CANCEL 修复

限定接受 **L1 合成摄取器准备**；不能签当前 R07 真实采集适配通过。

- 最终 `normalize_intake.py` SHA：`b56f350f7d2f36dd64c1f053318479e9818a5807610bc942a7a21b3bf81b9ce5`。
- 最终 `selftest.py` SHA：`4cb7db51b7a0a193c8ff2bf7c39e0fbd707436c673491d37c2ef9bdae7ba4395`。
- 最终 `cases.json` SHA：`d0f1c0d333e7be55ec94f4d6d99415efb1f079473c50f7cbe2e62da337c735b8`。
- `RUN_03/receipt.json` SHA：`7a2ec03028b7e9f372742d47bc71b26b9895ed5bee95cec9914c2983fedd56bb`，记录 `exit_code=0`、`timed_out=false`、`elapsed_seconds=2.8781445026397705`。
- 源码 600–644 行跟踪活动 `(epoch, req_id)`，在 REQUEST 设置、RESET/CANCEL/CONSUME 清除；CANCEL 用活动请求号，`cancel_reason` 留在 canonical 数据。包内实际原件显示 canonical 第 3 行 `cancel_reason=99`，D3 同沿 `CANCEL.req_id=7`。无活动取消的原 stderr 为 `CANCEL_STATE_LINE_3`。
- RUN_03 的 15 项按预期结果为 **2 个合成成功、4 个 PENDING、9 个拒收**；`accepted=6` 仅是 6 个进程退出码 0，不能写成 6 个实义正例。15 对 case 原双流、顶层原双流均与收据 SHA 一致。
- RUN_02 的 13 项为 1 合成成功、4 PENDING、8 拒收，其 13 对原双流及顶层双流均核同。RUN_01 首次 `FileNotFoundError`、退出码 1 的原收据与 stderr 仍在；RUN_02 的未覆盖 CANCEL 缺陷和 RUN_03 最小修复说明保留。
- 当前包仅出现 RUN_01、RUN_02、RUN_03。`RUN_SPEC_R03.json`、`M2_PERMISSION_REQUEST.md`、失败历史都记载额外最多三次中第一次的 90 秒纯软件额度；用户本轮也明确确认已批准。原件支持只执行一次额外尝试，不把未用两次自动恢复到本窗口。

## 真实 profile 的具体接入阻断

以下均为源码静态路径结论，没有新增反例运行。原 15 项合成结果仍按原版本和边界保留；这些问题阻止把当前摄取器升级为最新 M2 公开观察合同就绪。

1. `normalize_intake.py:494–498` 在 `tx_sample_valid=1` 时无条件要求 `tx_req_id` 已知。最新 M2 sidecar 的 startup zero 实际采样没有业务请求身份，`tx_req_id_valid=0` 对应 canonical `null`，将触发 `USED_DATA_UNKNOWN_tx_req_id`。最小方向：按已冻结的 startup/metadata-valid 语义区别“真实采样存在”和“业务 ID 存在”，保留 null 与原因，不补 ID0。
2. `normalize_intake.py:531–533` 把每个非 startup TX 都要求为活动且已 COMMIT 的交易，随后清账；`640–644` 把每个非 startup TX 都导出一次 CONSUME。因此已成功采纳交易后的合法 HOLD，再发同一 held PCM/ID 时会被 `TX_ID` 拒收，或者错误再次消费。最小方向：按真实 `tx_hold` 区别首次 adoption 和重放，单独保存 held 身份；只有新采纳关闭 pending 交易，HOLD 留在 canonical/TX 视图，不伪造 D3 CONSUME。
3. `normalize_intake.py:515–516` 将每个 raw `cancel=1` 视为必须有活动交易的合法取消。冻结生产链的 raw cancel 由 FRAME 驱动，空闲 FRAME 也会置位，直接映射会在首次空闲 FRAME 被 `CANCEL_STATE` 拒收。最小方向：保留原始 raw cancel，按 M2 冻结的交易取消判据和实际活动账本派生业务 CANCEL；定义未冻时保持 PENDING，不把 raw FRAME 等同交易取消。
4. `normalize_intake.py:621–630` 在实际 `req_valid && req_ready` 沿同时写 D3 REQUEST 与 ACCEPT。旧 D3 要求 REQUEST 绑定 FRAME 原点 F，最新合同实际 ACCEPT A 可为 F+1 或更晚，因此现有投影不能表达 F/A 分离且不满足旧 D3 入口的 REQUEST 同 FRAME 约束。最小方向：canonical 保存各真实沿；旧 D3 视图只作为已说明的受限诊断，无法无损表示时标记 `PENDING_UNSUPPORTED_PROFILE`，不能把 A 改写为 F 或反过来。

## R6-2 MIDI 准备

限定接受 **L1 软件/纯文件计划**；SV driver 为 **L0 未编译**。

- 最终软件源/参数/用例五件和 SV driver 一件均与 FILE_SHA 运行冻结标识一致。SV driver SHA：`99e40266a46f1606409fa6ef270dd0c6b056dcb511363ae90dfbaf67653df89a`。
- RUN_02 原 stdout 记载 13 正检查、4 负检查、63 UART 字节、23 个事件、HDL runs 0，顶层双流 SHA 均核同。实际 `plan.json` 确有 63 条字节和 23 条连续事件序号，字节时间窗互不重叠。
- RUN_02 reset 计划从 cycle 0 低开始、800 释放，首字节从 5920 开始；40 MHz / 31250 对应 1280 周期/bit、8N1。中段复位 assert=1000480、release=1002480；公开 event-ready 背压 927520–988480。RUN_01 先把 reset 排到 5120 的已知问题原件和修复历史保留，RUN_01 不作为最终刺激签收。
- 软件正检查覆盖四独奏消息、四音保持不同完成沿、逐放、velocity0、重触发、第五键边界、running status/F8、中段 reset 和背压计划。slot/Release/generation/第五声算法语义仍是 M1 PENDING。
- SV driver 只驱动 reset、MIDI RX、event_ready 并观察 event valid/data，无私有层级。UART 在负沿切换、每位 1280 个负沿；posedge 记公开握手。它没有接入真实 DUT，参数/文件报错路径仅静读；arrival window 仍为夹具期望，未获 parser/DUT 实证。其 event_ready 驱动需要在实际装配时核公开方向，不能擅自连接到输出信号。

## 阅读边界

已完整读两包生产 Python、归一状态机/投影和最终用例、MIDI SV driver、关键 RUN_SPEC/receipt/失败历史，并核对两包清单及所列双流。批准依据按用户本轮说明和包内记录核验，不声称独立读取了 E 盘历史对话或外部 M1 原路径本体；未读未跑其他 R6 包、旧 D3 全套、HDL/EDA、硬件，也未审核 d53fcd4 的额外历史补充。
