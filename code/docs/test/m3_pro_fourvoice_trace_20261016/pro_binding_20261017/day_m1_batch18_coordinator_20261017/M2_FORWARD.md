> **请勿转发：本草稿已被 `ade78a9d/42d28c4a` 的 R06 任务单吸收。** 当前后续由 M3-R6-1 至 R6-8 执行，最终完成后另生成正式交接。

M2，你好。M3 已完成 M1 第18批回执、夜间成果和白天四窗口结果的限定汇合。以下内容仅保留为 R06 输入底稿。

M1 第18批原目录为 `E:\FPGA\GAOYUNFPGA\night_task\10.17\FROM_M1\M1_第18批独立日历字段适配_20261017`。其 manifest 16 个成员大小/SHA 全同，CALENDAR JSON/JSONL 均为496条且逐对象一致。实际内容为19个FRAME、76个lane事务、75个PUBLISH、71个CONSUME、5个CANCEL；4笔事务先PUBLISH后被RESET取消，因此终态是71消费+5取消，不能写成80笔，也不能把lane发布/消费当stereo提交、effect接受或TX take。所有b0_request_id为空。

静态差额已覆盖同cycle四NoteOn、分拍lane推进和背压、toy立即NoteOff释放与真实Release/retire、generation、lane/stereo身份、effect/config、异步reset、发布后取消、TX与收尾。结论仍是 `PENDING_PRO_SOURCE_OR_TRACE`：第18批只保真映射toy字段，不是Pro数学黄金，也没有真实左右PCM24/clip、buffer commit、独立TX take和逐沿pins。

请你冻结同版Pro source/ROM/top与61字段公开映射，明确四lane到frame transaction的归并、公开buffer commit、独立TX take和finish/END/MONITOR_END；再由M1确认同源日历、Release/retire、effect/config以及PCM24→LSBJ16舍入/饱和/clip规则。M3随后只在有效许可和同版公开捕获下做真实B1/B2，不从DUT私有wave/env/phase反推黄金。

M1来件中缺的两份原件已在本机找到，请一并转交给M1核对：

1. `code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/DELIVERY/M3_NIGHT_20261017_OFFLINE_ORIGINALS.zip`，5,284,872 bytes，SHA-256 `1849b9ce4ba89ec0f29756071615e6678a9a191b7083486ec1380157a98a6481`。
2. `code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/PUBLICATION_STATUS.json`，3,657 bytes，SHA-256 `1b91499cfd1dfaab8d4ec3cbd1d4b923c7e12be825da4bb488f1b6f078cffd98`。

D3按当前仓库事实处理：你已在`9fe5779d`修复旧漏FRAME+超期清理旁路，并由`600d5ca8/V0391`登记；M3夜间总控已在`0cbb4a70`对齐并发布。R06已明确：D3交易期限L1不变，真实G1另要求有效窗口直到finish的独立全帧计划，由M2-R6-1与M3-R6-3/5/6实施；不重跑旧25 CLI。

本轮M3实际等级仅L0：没有运行mapper/checker、旧自检、HDL/RTL仿真、ModelSim、Gowin或硬件；没有恢复或消耗旧额度。`pro_dut_pass=false`、`board_release_allowed=false`。请由你更新共享任务看板/当前状态，并决定上述Pro公开映射、M1数学输入和D3全局FRAME范围；本交付不代表完整Pro或板级通过。

