# 夜间任务3 C包：PARTIAL／真实采集未到

本轮授权目标：消费A真实R05 capture，独立核PT8211串行逐样本、frame/request/commit/reset取消及数字时间。本轮完成新消费者、来源绑定入口和必要软件自检；**真实R05验收未完成**。基线`c12636c034be62e10c564217298564422a533b9c`，未提交、未推送，由夜间总控统一门禁和发布。

本轮新增仅 C `code/software/m3_40mhz_pcm_i2s_latency_20261015/night_20261016/` 与本证据目录，没有新TB/RTL；旧C诊断夹具保持只读，未重跑；无A仿真/Gowin/板卡/Git写入或共享表修改。

## 结果与证据

- 最终消费者49/49：严格JSON/连续沿/RESET/END/ID/pending/held/clip计数；833/834和2500拍分布；PT8211低右高左、32槽末16有效、正负PCM舍入饱和；完整左右样本与帧采样PCM独立比较。缺沿、重沿、错序、错PCM、错左右、错装载相位、X、欠载、首请求漏期限、尾停钟、未观察复位即END均拒收。尾部未到下一帧的请求保留UNKNOWN。
- 来源与输入时间线26/26：字节/SHA正反例，旧fixture/旧A成功/失败receipt均不能充当本次真实成功；完整输入25ns时间基、音频reset/cycle对应、INITIAL_INPUTS、RESET时间落沿窗口、缺件/X/错误范围负例通过。真实成功回执完整正分支尚无原件可运行，明确UNKNOWN。
- 实际TB成功标记11/11窄回归：原7ms stdout仅只读核字符串，准确标记为`PASS M2_M1TD_REAL_CHAIN_BOARD_FUNCTIONAL_ONLY`；错名/前后缀/重复/混Error/Failure/Errors:01拒收。不把原stdout计作新真实capture或重跑旧组。

三个最终组原命令/退出0/耗时/双流/源及Python SHA分别在 `software_R02`、`binding_R03`、`marker_R01` 的 `RUN_RECEIPT.json`；所有前后SHA核同。早先软件R01=43项、binding R01=23项、R02=25项均保留，不拿旧较弱版本冒充最终源码。仅变更处做必要增量；原始SYNTHETIC captures、执行源和全部流在封包。

## 失败与自审修正

初次PATH选中WindowsApps python别名，进程未启动；查原A真实Python路径后改明确的Miniconda3 Python3.12.4，启动失败文字摘录见`START_FAILURE_01.json`（不是未产生的进程双流）。本轮正常软件运行双流齐全。

自审与总控窄审收紧：RESET→END未低沿不签复位；首次请求即使硬件ever_committed=0也不得漏过下一帧；每TICK检查7拍BCLK/834拍frame停钟上限；已commit未sample而遇RESET记录已知取消，保留commit事实、不混尾UNKNOWN。另纠正来源入口最初的错误PASS字符串并补实际原stdout/错名反例。旧C已有失败原件和测试日历一概未改。

`software_R01`首次只冻结源SHA，未同期复制源码本体；后按精确三处guard差异重建checker并核回原SHA，明确不是同期快照。其余原文件未改；后续运行均在创建子进程前保存执行源本体。源码重建限制保留在主回执。

## 未完成与交接

A `CAPTURE_BLOCKED.json`说明本轮平台审批阻断，新增功能进程0、无真实capture/READY。C没有申请EDA提升或绕过，也没有消费旧ModelSim/Gowin额度。实际真实R05串行逐样本、逐请求deadline与真实数字≤10ms仍UNKNOWN；first-valid未导出，数学clip/音色黄金、模拟端到端≤10ms、PLL/HDMI/STA/板级均未验，`board_release_allowed=false`。

本地封包：`SEAL_PARTIAL_R01/M3_NIGHT_C_REAL_CONSUMER_SOFTWARE_PARTIAL_R01.zip`，主回执`NIGHT_RUN_RECEIPT.json`，SHA/逐成员清单/CRC核验见`SEAL_PARTIAL_R01/SEAL_RECEIPT.json`及`MANIFEST.json`。含本轮源/双流/退出/合成正反例与来源合同、输入身份、A阻断原文副本；没有伪造REAL_CAPTURE。

给M2（待用户转发，尚未送达）：请将本包只登记为C真实消费者软件准备L0/L1、整体PARTIAL；恢复真实采集需先有A有效平台权限及新成功capture、inputs、READY和成功run/source/tool/log原件。到件后按README入口对精确SHA跑独立消费者，核结果再决定限定L2等级；正式发布/共享树/物理与模拟验收仍由M2及原岗位负责。本窗口不要求重复已签旧夹具或旧7ms组，不恢复历史许可。
