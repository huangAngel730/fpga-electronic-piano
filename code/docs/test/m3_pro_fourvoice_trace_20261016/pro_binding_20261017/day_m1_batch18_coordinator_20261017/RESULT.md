# M3 白天总控：M1 第18批与夜间成果汇合（2026-10-17）

> **R06 更新：本文件只作为输入审计底稿，不单独发布。** 远端 `ade78a9d/42d28c4a` 已发布《Pro四声基础三岗扩充任务单 R06》，吸收本轮 M1/D3 结论并把后续拆为 M3-R6-1 至 R6-8。当前实施与最终交接以 R06 包为准。

## 结论

本轮完成的是 **M1 第18批字段适配的限定静态摄取、B1/B2 差额整理和原件定位**，实际等级为 **L0**。M1 的 496 条记录可以保真映射原 toy 日历字段，但不是正式 Pro 的数学黄金、真实 PCM/clip、串行提交或板级证据。

当前状态保持：`PENDING_PRO_SOURCE_OR_TRACE`、`pro_dut_pass=false`、`board_release_allowed=false`。

## 已核事实

- M1 第18批 `MANIFEST.json` 列出的 16 个成员均存在，大小和 SHA-256 一致；目录另含 manifest 自身。
- `CALENDAR.json` 与 `CALENDAR.jsonl` 均为 496 条记录，按序逐对象一致。
- 日历含 19 个 FRAME、76 个 lane 事务、75 个 PUBLISH、71 个 CONSUME、5 个 CANCEL；其中 4 个事务先 PUBLISH，后被 RESET 取消，所以不能把 75+5 算作 80 个独立终态。正确终态关系为 71 个消费加 5 个取消。
- 同 cycle 四个 Note On、四 lane 分拍推进、一次 3 cycle 背压、toy Note Off 立即释放，与正式 Pro 的事件应用、Release/retire、generation 和推进语义均有差额。
- 所有 `b0_request_id` 为空；lane ID 不是 stereo sample request ID。lane PUBLISH/CONSUME 不是 buffer commit、效果接受或 TX take。
- M1 第18批没有 effect/config 接受日历、真实左右 PCM24/clip、公开 buffer commit、独立 TX take 或逐沿 BCLK/WS/DIN。

## B1/B2 后续所需最小闭包

1. M2 冻结同版 Pro source/ROM/top、端口/reset/epoch、四 lane 到 frame transaction 的归并、公开 buffer commit、独立 TX take 和 finish/END/MONITOR_END 映射。
2. M1 对同一事件、config/effect、帧请求 ID 和 source/ROM/input basis 给出 PCM24 左右/clip 黄金，并确认 PCM24 到 PT8211 LSBJ16 的舍入、饱和和 clip 归并规则。
3. M3 只在取得有效许可和同版公开捕获后，采集真实事件应用、全部 lane 推进、Release/retire、generation、背压、取消/reset、effect/config 接受、公开 commit、TX take 和逐沿 pins；不得从 DUT 私有 wave/env/phase 反推期望。
4. 正确证据链应为：B1 同源事件/四 lane 日历 → M1 同 basis PCM24 L/R/clip 黄金 → buffer commit → 独立 TX take sidecar → BCLK/WS/DIN → 左右 LSBJ16 解码。

## D3 当前边界

M2 已在 `9fe5779d` 修复旧 D3 “漏下一 FRAME 后超期 CANCEL/RESET/RETURN 清账并让 END 通过”的已知缺陷，`600d5ca8` 登记 V0391；限定结论为 L1 合成软件定向验证。夜间总控已在 `0cbb4a70` 对齐该现状并发布静态交接。

本轮主对话3基于旧 R02 提案形成的审阅不再作为当前阻断，也不随本交付发布。`0cbb4a70` 提出的新静态范围问题已由 R06 明确：现 D3 L1 仍只签交易期限和已观察 FRAME 关系；R06 真实 G1 必须由冻结输入/时钟/复位合同独立生成有效 epoch、正常窗口直到真实 finish 的全帧计划。缺计划保持 `PENDING_FRAME_PLAN`，不重跑旧 25 CLI。

## 原件入口

- M1 第18批原目录：`E:\FPGA\GAOYUNFPGA\night_task\10.17\FROM_M1\M1_第18批独立日历字段适配_20261017`
- M1 缺少的离线总包：`code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/DELIVERY/M3_NIGHT_20261017_OFFLINE_ORIGINALS.zip`，5,284,872 bytes，SHA-256 `1849b9ce4ba89ec0f29756071615e6678a9a191b7083486ec1380157a98a6481`
- 对应发布状态：`code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/PUBLICATION_STATUS.json`，3,657 bytes，SHA-256 `1b91499cfd1dfaab8d4ec3cbd1d4b923c7e12be825da4bb488f1b6f078cffd98`
- 夜间 D3 当前交接：`code/docs/test/m3_pro_fourvoice_trace_20261016/D/d3_repair_proposal_20261017/HANDOFF_FINAL/M3_D3_R05_RECONCILED_HANDOFF_20261017.zip`，1,095,226 bytes，SHA-256 `115212a42b36c2bfb970dd59258cc025de10884f1fa0a840b6e42c47dd985b3b`

## 实际验证与边界

- 本轮四个白天实现窗口均只做读取、SHA、JSON/JSONL 解析和字段静态对照。
- 未运行 M1 mapper、B1/B2 checker、旧自检、HDL 编译、RTL 仿真、ModelSim、Gowin 或设备操作；功能轮次和旧额度消费均为 0。
- 未修改 RTL、正式接口、top、CST/SDC、任务看板或当前状态；审核制度未启用。
- 主对话3的两份旧基线审阅文件保留在工作区但排除于本轮发布，不删除、不冒充当前结论。

