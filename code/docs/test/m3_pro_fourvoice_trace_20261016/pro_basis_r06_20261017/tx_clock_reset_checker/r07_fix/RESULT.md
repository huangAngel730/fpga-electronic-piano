# R6-6 R07 定向修复结果

状态：**限定软件修复与新夹具 L1 完成；实际 Pro 接入 PARTIAL/PENDING**。只在本包新增 r07_fix，旧 checker 和原 RUN_01 二十例保持原字节。未修改 RTL、接口、约束、M1/M2 或共享状态。未提交/推送；按本轮分工交夜间任务1统一封存发布和 M2 最终复核。

## 实现

- checker.py 为新增 CLI，boundaries.py 独立核 F/首valid/A、原始 source_line 以及 RESULT/COMMIT/CANCEL 的 `t-F<833 && t<next_independent_FRAME`，另报 t-A；兼容视图的 request_cycle 仍为 A，不挪到 F。
- R6-5 唯一 `M3_R06_UNIQUE_FRAME_PLAN_V1` 与冻结输入/rules SHA/canonical identity 绑定；按 `n_k=ceil(128*k*2**32/659706977); cycle=release+n_k-1` 独立复核，覆盖 reset/idle/cancel 至实际 finish。允许 global cycle=0、release=0、首功能沿 n=1；不虚构 cycle=-1。只验证收到的计划，不输出第二份生产计划，不导入/执行 R6-3/R6-5 候选。
- 显式 C3 profile 保留无效 ID=null 与有效数字 ID=0、metadata_valid、双 clip mask、error、overflow。HOLD 继承已持有 ID/clip；01 与10即使 OR相同也拒收。未知/缺失语义保持 PENDING，不删列补0。
- 所有 REAL_PUBLIC_TRACE 在可信 M2 来源、同版工具/源码/finish 准入尚未接通时，先返回 PENDING_SOURCE_PROVENANCE。自报字符串、SHA、PID、approved/authenticated 或混合成输入不能产生 real_pro_tx_pass。
- crosspack.py 无损读取实际 A `M3_R7A_PUBLIC_ROW_V1` 与 R6-5 `M3_R65_R07_CALENDAR_REPORT_V1`。保留原61字段、source、extensions、missing_reasons、events 和完整 R6-5 report；新报告 crosspack_preservation 保存原对象，输入原文件未改。TX_ADOPT 是 rst_n&&tx_sample_valid，STARTUP/HOLD 都可带该标签；分类仍看显式标志，不把 HOLD 当新消费。原生观察账本不升级为独立 TX 选择期望；其 pending_reasons 继续保留。
- serial_core.py 是旧 checker 的新增副本和最小 C3 兼容修改；旧源不覆盖。它继续负责串行/PA/PCM/finish 检查，局部边界通过不能替代该检查。

## 实际执行与边界

仅消费原 R06 尚余的一次 ≤60秒定向修复组，**RUN_02 exit0，8.671999999991385秒，PID6724，2026-10-17 11:41:57 UTC启动**，stderr 0字节，275项冻结输入前后身份核同。RUN_SPEC SHA `65260e0758314d9cb08fa87182f2ffbcea295ac451e748c4ce836fe457261b75`。真实 argv/cwd/UTC/工具版本/依赖/双流/返回码在 RUN_02/LAUNCH.json、CONSUMED.json、RECEIPT.json、stdout.bin、stderr.bin；源码及手写夹具在 RUN_02/frozen。

28项为**预期结果符合28项**，不是28个实义成功：3个局部交易/profile机械正例，2个原生格式机械正例（仍保留准入/M1/TX期望待定），1个零基计划正例；10项返回指定PENDING，12项按指定原因拒收。逐项输入、预期、诊断和结果在 RUN_02/products，顶层 RESULT.json 汇总。

关键反例：F834/V835/A835/t1667，t-A=832而t-F=833，RESULT/COMMIT/CANCEL三种都拒收 FRAME_BUDGET_DEADLINE。合法取消1666和延后接受836保持原行及t-F/t-A；错原行、缺idle FRAME、计划与trace一起移位但输入未移、EOF代finish均拒。REAL自报权威不通过；startup数值0、双clip互换、metadata_error拒，metadata无效/overflow/未知profile/缺oracle双clip保持待定。

3次新 CLI 调用同在此组：静止 BCLK 的新合成输入拒收 PIN_BCLK_STALLED_OR_MISSING_EDGE；实际 A/R6-5 **同合同手写夹具**返回 PENDING_TX_SELECTION_PLAN 并保留原行及原pending；REAL在其他路径缺失之前返回 PENDING_SOURCE_PROVENANCE。没有运行实际 A 或 R6-3/R6-5 生产程序，没有真实 Pro capture，没有完整正向 serial 回归。旧20例未运行。初组 RUN_01 原记录继续为 1合成/7待定/12拒收、exit0/5.205964088439941秒，不能与本次合并声称最终48例全量通过。

自身只读子智能体做过静态增量自审，未执行/import/修改；不是审核员/预审员制度，也不替代 M2 签收。冻结后功能源码没有再改。OLD_ORIGINALS_BEFORE/AFTER 记录旧42件前后核验。

## 剩余与责任

原修复额度已用完，不再测试。真实来源/工具执行/同版finish准入归 M2；真实十九语义、advance和完整PCM oracle由 M1提供；原生 R6-5 ledger 当前未提供独立 TX selection plan，保持PENDING。当前 CLI 可读取真实跨包**格式**，不能认证其生产者/采样相位真实性。商业工具可用、文件SHA和R7-D结构封存均不等于执行许可。

后续需 M2 核精确新候选、所需原件与独立期望，授权后才能做正向串行或真实 HDL 接入；本轮 HDL/EDA/设备/Git写入均0，board_release_allowed=false。C3中不支持的M1字段null/XZ、歧义reset/epoch、overflow不抹除；实际来源缺件不能签整机/板测通过。

入口：CONTRACT_AND_CLI.md、RECEIPT.json、FILE_SHA.json、SEAL_R01/。R7-B C5静态绑定在 `pro_basis_r07_20261017/public_equivalence_tb/c5_binding/`，B/D旧成果冻结，B最后 `<=stop` 修订继续L0未执行。
