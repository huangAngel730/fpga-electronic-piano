# 夜间任务2 A包：PARTIAL / 平台阻断

基线 `c12636c034be62e10c564217298564422a533b9c`。本轮只在 A 三个目录的 `night_20261016/` 与预授权 E 的隔离子目录写入；无 Git 写入、无共享状态/正式顶层/约束/算法/ROM改动、无实物。纯仿真观察board最终位于 `code/tb/board/m3_night_fourvoice_integration_candidate_20261015/night_20261016/`，没有把文件日志结构留在可综合RTL目录；迁移前副本保存在STATIC_PRE_R04，旧原件未动。

本任务原目标是补真实 R05 的公开逐沿/请求/PCM/串行采集，**未完成**。原 7 ms 真链 PASS 不重跑、不升级。本轮已完成采集候选与合同、静态修复、纯软件反例及封存，不代表新RTL通过。

- 新 board 保留原真实 UART MIDI→事件FIFO→四声部frame_core→buffer→PT8211 TX，新增观察只连接模块公开端口线。撤销补丁后静态逐字节等于 R05 原 board。
- 原 7 ms TB 的所有检查保留，只延长末尾观察到下一帧 fence 后再复位；新 observer 固定 40MHz 正沿 pre-NBA，first_valid=null，不读取新内部寄存器。原 TB 历史层级断言原样保留，不冒称已消除其边界限制。
- 初始 epoch=0，time-zero X→0 不伪造 RESET。输入文件 HEADER 后以 #0 确定写 INITIAL_INPUTS；仅后续实际输入变化写边沿，保留原时间与来源。上述新 RTL 仅 L0 静态检查，未编译/仿真。
- 新副本 ledger 修合法 RESET 后状态未清导致误拒；原 bug 用同一合成原件复现。clip_count 同步改为饱和一致性。软件 14 项正反例及静态检查通过，退出0；最终日志、耗时、SHA在 `SOFTWARE_R04/RUN_RECEIPT.json`，此前R03也通过并原样保留，R04因观察board路径迁移核新树再次运行。只证明 L1 软件逻辑，不证明真实采集。

## 实际执行与失败原件

`RUN_01/RUN_RECEIPT.json` 是本轮唯一 ModelSim 相关预检：固定原 ModelSim SE-64 2020.4安装、同EXE/DLL pin，`vlib.exe -help` 在 suspended CreateProcess 返回 WinError623，process_created=false、exit_code=null、双流均空且保留。功能调用0，无消费标记。`RUN_02`从未建立。

随后同一标准平台审批命令被两次拒绝；第一次只识别旧只读授权，补读总控直接用户消息后仍要求本窗口直接批准具体运行。原回复位于本对话两次 `require_escalated` 工具错误；`PLATFORM_REJECTIONS.json` 是忠实文字摘录，**不是**不存在的进程stdout/stderr。平台未给本地原始文件，原件缺口已标明。总控随后明确停止提升，转软件/静态收口。没有第三次请求、换版本、换工具、换窗口代跑或系统改动。

准备过程另有两个软件入口失败：PATH的 `python` 指向不可启动WindowsApps别名，改用先前已验证的Miniconda明确路径；一次内联 `-c` shell引号导致SyntaxError、未执行任何语句，随后改成显式 `repair_static.py` 文件。两者工具原回复在本对话，未保存独立进程双流，不冒称已齐备。它们均不是 RTL 运行或额度消费。

初始 RUN_01 失败 runner 当时仅记录SHA、未同期复制源码本体；其 stage HDL 原件仍在，不能事后重建冒称同期原件。最终当前新源、14项软件调用执行源、测试完整原件和必要依赖本体齐套，源前后核同。

## 交付与未验项

主回执：`NIGHT_RUN_RECEIPT.json`。封包：`SEAL_PARTIAL_R03/M3_NIGHT_A_STATIC_SOFTWARE_PARTIAL_R03.zip`，SHA见同目录 `SEAL_RECEIPT.json`；包内含新源/逐项diff/固定R05 ZIP/只读依赖源码/预检失败双流与收据/合成正反例及旧PASS/失败日志原件。旧证据均标原等级。

无 `REAL_CAPTURE.jsonl`、无 `CAPTURE_READY.json`，真实逐请求deadline与真实串行逐样本均 UNKNOWN；first-valid未公开、模拟≤10ms、PLL/HDMI/新候选完整STA/实物均未验，board_release_allowed=false。C应按 `CAPTURE_BLOCKED.json` 结束真实输入部分为PARTIAL，不能用本轮合成fixture签真链。

未提交、未推送；由夜间总控统一门禁与串行发布，保留所有他人未跟踪文件。M2最后复核与真人交接：待用户转发，尚未送达。下一责任为总控汇总此阻断；后续实际采集须先取得有效平台权限，本包不恢复旧许可。
