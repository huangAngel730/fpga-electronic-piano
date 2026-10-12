# `REAL_PUBLIC_PIN_PROJECTION_CANDIDATE_20261013` 合同

每条 `EDGE` 同时记录同一上升沿的 pre-NBA 输入/输出与 post-NBA 公开播放观察。字段必须精确，整数 0/1 不接受 bool，ID 为 uint32，PCM 为 signed24；未知字段直接拒收，防止软件 epoch 或抽象背压门伪装为真实引脚。

| 字段 | 来源 | 投影规则 |
| --- | --- | --- |
| `raw_result_credit` | observer-only | `rst_n && dispatched && request_window && !frame_tick && !pcm_valid`；不是 adapter 端口 |
| `qualified_result_ready` | `candidate_result_ready` | raw credit 且 `result_id == current_id` |
| `true_result_handshake` | 公开 pin 派生 | `result_valid && qualified_result_ready` |
| `commit_pulse`/`committed_*` | adapter 公开观察 | 只接受旧 `pcm_valid` 与 frame buffer qualified ready；接收结果本沿不能同时 commit |
| `pre_play_*` | frame buffer 公开 `play_*` | pending 有效时选 pending，否则 held |
| `post_play_*` | 同一公开 pin 的 post-NBA 观察 | commit 后立即可见 pending；frame 后 pending 转 held |
| `frame_tx_*` | observer 采样合同 | 只在 frame 沿有效，取该沿 pre-NBA `play_*` |
| `result_clipped` | 新隔离 clipped 后继 | 原 b2d 无此准确公开字段；禁止绑 0 或从满幅 PCM 反推 |

优先级沿真实源：reset 清所有运输状态；frame 禁止 result/commit 并使旧未提交结果过期；普通沿先消费旧 hold 到 pending，或接收一个新 qualified result。已经 commit 的 pending 在后续 frame 转 held，可继续播放。frame 与旧 result 同沿即使 `dispatched=1` 也不得 ready/握手。

META 固定五份只读源 SHA，特别区分：

- 原 `b2d_event_audio.sv`：`5f1a0d2e...a0ce`，无准确 clip 端口；
- 新 `b2d_event_audio_clipped.sv`：`3fd292ab...427f`，只在隔离后继公开已有 `be_clipped`，未综合、未生产接入。

软件 epoch、`result_sink_ready`、`pcm_sink_ready` 没有真实 pin 映射；抽象合同中的这些字段只能留作软件环境信息，不能出现在本投影 `EDGE`。本合同只准备未来真实捕获格式，不批准任何 RTL 或接口修改。
