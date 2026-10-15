T057离线事务／ACK／逐条READ审计候选（2026-10-15）

任务来源：M3新任务表P2的逐包／ACK／读回记录和恢复用例准备；用户在本窗口完成MIDI导入后授权自行认领一项代码补充。只读原T057协议、PC编码器及T062同步双银行接收器；不依赖延迟重放或现场准备对话，不修改上一项MIDI成果。

用途：检查已整理的完整帧事务日志及独立预期曲谱，不发送帧、不打开串口、不运行RTL、BLE、播放器或EDA。输入日志的真实性不由本工具认证；将evidence_kind标成recorded_frames不构成硬件证明。

运行（仓库根目录，输出目录必须不存在）：
python -B -X utf8 code/software/score_session_audit_candidate_20261015/session_audit.py --trace E:/your/local/trace.json --output code/output/score_session_audit_manual_001

软件自检、合成恢复用例和原始日志封存：
python -B -X utf8 code/software/score_session_audit_candidate_20261015/run_acceptance.py --output code/output/score_session_audit_acceptance_NEW

本地证据JSON格式（不是新T057线路协议）：
schema：整数1。
evidence_kind：synthetic_fixture或recorded_frames。
initial_committed：必须null，声明从复位后空状态开始；不能冒作实际已观察复位。
expected_scores：1..64个{score_id,records_hex}，score_id唯一，records_hex是独立期望的原T057事件字节。每份1..512条8字节合法记录。
ack_timeout_us：1..500000。
max_retries：0..2。
total_timeout_us：不超过30000000且不小于ACK窗口。
attempts：1..20000条{request_hex,response_hex,elapsed_us}；每项表示一次完整请求及一个响应，或response_hex=null的ACK窗口到限。hex必须小写、偶数长度且无空白，时间必须非负整数。
禁止重复JSON键、未知字段、bool冒整数及超限文件；输入文件限8MiB。

支持范围与判据
独立位运算CRC核每帧；检查session/seq/offset回显、原命令、ACK/NACK与错误码、全部metadata、READ事件及整体曲谱CRC。记录字节按现有T057合同检查，不复用原编码器的解析函数。
BEGIN／DATA／COMMIT只从合法ACK推进确认账本。请求无响应时不声称接收方没执行；只能允许同一请求字节完全一致的有界重试。首个被观察ACK与该操作执行一次的结果对应。
重复最后一次成功请求必须原字节重放ACK，不能再次写入／提交。STATUS／READ成功也更新最后请求缓存；不是只靠CRC相同判定重放。
每次成功COMMIT前后均核独立预期曲谱。每一提交代的全部索引必须有正确READ，才能继续覆盖下一提交代或结束；重复读取不能补齐漏读，不重复计提交。
暂存新曲期间可核旧提交曲谱READ，ABORT清暂存并保留旧提交。检查早期NACK后恢复与完整坏曲谱CRC／事件拒收后的恢复。CRC9／事件10失败使会话失效但保留received计数；早期参数／会话／序号／未齐套拒收按冻结接收器行为处理。
按冻结接收器实际优先级先判记录合法性，再判最终整曲CRC；注释中的泛称“失败COMMIT”不能替代源码中各分支差异。
结束要求无未解决超时、无活动暂存、至少一次成功提交、所有声明目标均有提交，当前及先前提交代完整读回。

时间profile与未覆盖
elapsed_us是整理日志声明的耗时，不是本工具测得的UART波形。无响应条目必须恰等于配置ACK窗口；较大未知间隔、5s会话超时、20ms逐字节超时、停止位错误、部分帧／噪声／断线、同时多个在途请求及未观察初始银行均不在本工具支持profile中，不推测恢复结果。活动会话累计耗时采用保守上界；STATUS／READ和早期NACK不刷新该计时，BEGIN／成功DATA／缓存重放刷新，跨5s报SESSION_TIMEOUT_PROFILE_UNSUPPORTED，不伪造NACK12恢复。
本地审计通过仅说明给定记录和独立预期在限定profile下符合合同。synthetic_fixture全为合成软件夹具，不是FPGA／实物证据。没有实际上传、FPGA ACK、播放或声音结论。

返回码：通过0，输入／核验失败1，参数或已存在输出目录拒绝2。创建目录后的失败保留receipt.json，不能覆盖成成功。
工具源码／冻结参考／Python运行时前后SHA、实际命令、日志、退出码和失败历史见验收输出；未提交／未推送，自审完成后交M2限定复核。
