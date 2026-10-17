# task-day E1：双滑块 Pro 正式接入差异

责任窗口：夜间任务4。任务是当日 E1 静态接入差异，不是昨夜 E2；旧 E1 487检查/4坏例及 E2 成果只读，不重跑、不复制 RTL 自测、不修命中闪光 FAIL。

依据：E:/FPGA/GAOYUNFPGA/night_task/10.17/task-day/ 两份 M3 任务单及 pro_binding_20261017/coordinator_20261017/DAY_PLAN.md。用户在总控消息01a14797-672a-7462-a629-9845497d8ee2直接授权1–5派单/回传与自有子智能体自审，已通过read_thread核原文；最终只回总控01a14050-cd98-7c41-8004-5d3e25765167。未启用审核员/预审员制度。

T0=2026-10-17 10:04:35北京时间，最晚14:04:35收口，必要静态交付齐套即停。现场HEAD=414e1a9d3ee0617c5e8ba72dd4b22c36122c9926，tracked/index检查无变化；远端实时fetch归总控，本窗不fetch或Git写入。

仅授权三处 m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017/：rtl/input、tb/input/visualizer、docs/test。本轮预计只需docs/test产生差异/证据/封包，不为占位创建RTL/TB。正式top/pkg/PLL/CST/SDC、M1模型、旧pro_parallel/formal_geometry、旧seal只读。

目标：逐项核mode/score producer及frame epoch、accepted唯一复制点、40/25/125MHz/唯一TMDS、七组CDC及64/98bit保持路径，给文件/行/SHA、UNKNOWN/冲突和最小可逆接入提案。新Pro源缺失时明确PENDING，不能从名字猜端口或从旧PG484工程推导新Pro通过。

执行预算：最多2轮必要新静态/软件核验，每组≤90s；计划仅1轮终末来源/锚点/封包核验，成功即停。先人工静态阅读和冻结输入，不恢复旧工具额度。Python仅用现有安装、独占新输出、原argv/cwd/双流/退出与SHA齐套，Job Object拥有子树。ModelSim/Icarus/Gowin/PnR/STA/码流/设备调用均0；不安装、不换工具、不运行仓库门禁。

自审：主窗口核来源、差异和表；自有只读子智能体只核七组CDC/时钟/旧源与新Pro边界，不执行任何软件或编辑文件。当前无新Pro源/ROM/top/trace/许可与可控实物原件；正式接入、完整STA、实屏仍后置基础+双音色，board_release_allowed=false。集中交付为L0静态准备DONE、整体接入PENDING，由总控汇合发布及M2最终受控决定；真人M2待用户转发，尚未送达。
