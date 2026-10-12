# PROPOSED_FRAME_TRANSPORT_V1 合同

## 观察口径和字段

所有输入均在一个抽象音频时钟上升沿前采样（pre_NBA）；`pre` 是本沿动作/原 held 播放，`post` 是按优先级推进后的状态，二者不能混用。RESET 标记只在 reset 首个低沿出现，随后的低沿不另增 epoch。cycle 从 1 连续到 END，无跳沿。初始 epoch=0；32 位 epoch 用尽时拒收，不静默回绕复用。32 位请求 ID 按模 2^32 回绕。

| 输入/状态 | 定义/范围 | 身份与限制 |
| --- | --- | --- |
| rst_n, frame_tick, backend_ready | 整数 0/1，bool/浮点不接受 | backend_ready 是环境输入，不计算后端 ready 日历 |
| result_valid, result_id, left/right | valid 整数 0/1；ID uint32；PCM signed24 | PCM 原样运输，不做声音计算 |
| result_epoch | uint32 软件寿命注记 | 非现有 b2d/M2 adapter 公开端口；真实映射另审 |
| clipped | 整数 0/1 | PROPOSED_ADAPTER_METADATA，非当前 b2d 公开字段 |
| result_sink_ready, pcm_sink_ready | 整数 0/1 软件接收门 | 仅背压模型环境门，非生产端口变更提案 |
| current_id / pending_request | 当前代/最多一笔未派发请求 | frame 边沿更新 ID；该沿 dispatch_valid=0，下一沿公开请求 |
| dispatched / received | 当代已派发/已接收结果 | 每代最多一次结果接收及一次提交 |
| pcm_record / committed_pending / held | 注册结果/合法已提交待播放/播放保持 | 三者不可混称；旧合法 held 允许重复 |
| clip_count | uint32 饱和计数 | 只在本沿成功 commit 且随行 clipped=1 时增加 |

META 必须精确匹配 schema/origin/contract/region 和字段来源标签；`initial.current_id/clip_count` 仅用于软件入口夹具（回绕/饱和）。它不是执行了数十亿时钟的证据；reset 无条件清零这两个种子。其余状态始终空。未来真实捕获格式和寿命映射必须另经 M2 审核。

## 单沿状态转移（优先级从上到下）

| 条件 | 派发/结果/commit | 后状态与保持 |
| --- | --- | --- |
| rst_n=0 | 全部不接受 | 首低沿 epoch+1；清当前 ID、请求、结果、pending、held、clip 和软件诊断计数 |
| frame_tick=1 | 全部不接受，取消未派发/在途旧代/未提交 PCM | 旧 committed_pending 若存在转 held，否则旧 held 保持；清 pending PCM；ID+1，产生一笔下一沿可见请求 |
| 普通沿 pending_request && backend_ready | dispatch_valid && ready 真接受 | 清请求，置 dispatched；ready 单独不计数 |
| 普通沿 dispatched && !received && result_sink_ready && result_valid && 当前 epoch/ID | 真结果接受 | 注册完整 PCM/clip 身份；received=1，本沿不能提交刚收到的结果 |
| 普通沿旧 pcm_record 存在 && pcm_sink_ready | commit 一次 | 转 committed_pending；清 pcm_record；clip 按元数据恰加一次/饱和 |
| 普通沿旧 epoch/ID 或当代重复 result | 不接受 | 明确 discard 诊断；不能覆盖已注册/已提交 PCM |
| 未 ready 的当前合法 result | 不接受 | 直到接收前 valid/payload/ID/epoch/clip 保持；frame/reset 可取消保持责任 |
| 无新合法提交的后续 frame | 无新结果播放接收 | 合法旧 held 可继续重复，不能据重复播放增加 clip |

`result_ready` 是接收门/信用状态，身份仍须限定接收；错误 ID 即使环境保持 ready 也只记 discard。未来 adapter 若采用不同公开 ready 口径，需另建映射，不据本模型签现有 RTL 的 pin-exact 等价。frame 沿 readiness 的源值可为 1，但本模型所有 qualified 接受为 0。

诊断计数为 Python 软件审计量（reset 清零），END ledger 为全轨迹独立累积、不随 reset 清零；除 clip 外不冒称硬件计数器位宽。epoch 与 ID 同核并不证明实际 DSP 排空或解决硬件身份回绕问题。

## 固定场景与行为反例

正例覆盖：833/834 帧输入、frame/result 同沿、派发延期成功/过期、result HOLD 与 PCM 背压、常 ready/重复拒收、pending/held 期间复位、ID fffffffe→ffffffff→0、held 欠载重复、clip 单次计数/饱和，以及 frame 取消已接收但未提交 PCM。每例 END 给出真实模型 dispatch/result/commit/discard ledger，不以 PASS 文本计事务。

六份单目标行为坏轨迹保持原输入、完整逐沿记录和 END 不变，各仅改变一个观察字段。它们不是 RTL 变异，也不是截断/格式坏例：

| 坏观察 | 指定拒收诊断 |
| --- | --- |
| ready 单独造成派发 | DISPATCH_VALID_READY |
| frame 当沿接受旧结果 | FRAME_OLD_RESULT_REJECT |
| reset 前 epoch 被接受 | RESULT_CURRENT_EPOCH_ID |
| 未 ready HOLD payload 改变 | RESULT_HOLD_STABILITY |
| 同 ID 再 commit | COMMIT_CURRENT_ONCE |
| 非 commit 时 clip 增长 | CLIP_COMMIT_EXACTLY_ONCE |

另有独立手写断言和输入 HOLD 违约自检，以及重复 JSON key、NaN、bool 混整数、越界、未知字段/tag、cycle/epoch、RESET/END、缺文件和拒覆盖异常检查。输入违约与坏观察分列，不拿输入格式错误代替六份行为反例。
