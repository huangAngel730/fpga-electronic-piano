# 夜间任务2 → 夜间总控 / M2

R7-A public_capture_tb离线准备完成，状态SOFTWARE_READY、真实链PENDING。基线4fd3366e42fd2356e56eb96eee70b6771afd4bb1。仅以下三个根新增文件：

`code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r07_20261017/public_capture_tb/`

`code/tb/board/m3_pro_fourvoice_trace_20261016/pro_basis_r07_20261017/public_capture_tb/`

`code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r07_20261017/public_capture_tb/`

交付：复用R6-2 driver的公开整机TB、唯一passive observer、版本化实际61键外层schema、流式转换器、新36例夹具与2个CLI退出边界原件。初组1/≤90秒，实际2.062秒，7正29负通过；两CLI实际exit0/2，增量0；HDL/EDA/设备/旧组0。输入/源码/依赖/工具冻结与前后1266身份无漂移。自审修正MONITOR前缀/畸形重复、停止请求相位竞争、子进程超时原件保存及总预算PASS边界，均在首组前完成，无失败重跑。

实际接口：CAPTURE_SCHEMA.json SHA256 `6afe11ce7b0268ab8ca7c7553b7774bb5d185ac79b99fa229acc8d37c6bf8e3f`。schema版本M3_R7A_PUBLIC_ROW_V1，fields仍裸61键，TX资格/双clip在extensions。C桥样本在RUN_01/products/public_baseline.CLI/PUBLIC_ROWS.jsonl；标SYNTHETIC_SCHEMA_FIXTURE，禁止写成真实capture。23项缺失均null+原因，同ps epoch歧义也null；无FRAME_PLAN生成、无DSP私有读取、无真实Pro/finish/board通过。

原件入口：RESULT.md、RECEIPT.json、RUN_SPEC.json、RUN_01/PROCESS.json、RUN_01/RECEIPT.json及原双流；R7A_PUBLIC_CAPTURE_ORIGINALS_20261017.zip包含本次源/输入/夹具/结果本体，FILELIST.json与SHA256SUMS.txt列逐文件身份，ARCHIVE_RECEIPT.json给ZIP SHA和文件数。失败历史：无意外失败；29个指定反例及exit2反例均保留原件，不删除拒绝证据。

待M2决定精确事项：按SOURCE_ASSEMBLY的现有M2替换闭包，冻结实际source/ROM/IP/时钟模型、工具、窗口6参数及一次真实HDL执行准入；不得由本包软件PASS恢复P7/旧额度。M1负责23项中相应真实语义差额及数学；R6-5/6负责独立FRAME_PLAN/账本/尾端核验；C保持unsupported profile，不丢HOLD或F-A。M2最终签收及Pro物理/电气/板采仍待，board_release_allowed=false。

未提交、未推送；本窗口未fetch/改索引/门禁/共享状态，请夜间总控按本轮规则集中串行核验发布。给M2真人的通知：**待用户转发，尚未送达**。窗口消息送达状态另见COMMUNICATION_RESULT，不等同真人通知或最终签收。
