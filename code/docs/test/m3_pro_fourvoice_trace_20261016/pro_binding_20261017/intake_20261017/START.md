# 夜间任务5：task-day 到件身份审计（2026-10-17）

当前任务：M3 B1 同版 source/ROM/top/公开 trace 到件身份审计，兼只读核 E2/E3 原件和真实 Pro 依赖。按总控 DAY_PLAN 与 task-day 两份用户任务原件执行；不恢复旧夜间任务。总控通信授权已通过 read_thread 的最新 userMessage 核验，允许本轮向夜间任务1回传。

独占写集：software、tb/board、docs/test 下 `m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/`。本轮以 docs/test 审计原件及 software 审计脚本为交付，无需新增 TB。旧 C/D、上午 passive monitor、E2/E3 原件只读；不改 M1/M2 源、共享状态、Git/index 或旧封存，不运行仓库门禁。

时间盒：总控 T0 北京 10:04:35，最迟 14:04:35 结束；必要成果齐套提前结束。无板卡/仪器会话、无新 Pro 码流执行准入。ModelSim/Gowin/Icarus/设备调用均 0。

预算：B1 六轮共享中本窗口最多两轮新 Python 身份审计/有据修复，每轮 ≤90 秒；夜间任务2最多四轮，本窗口不得消费其份额。旧 E2=3/6、E3=6/6 仅作历史只读核验，不恢复任何次数。执行前落消费标记，原始双流、argv/cwd、工具身份、耗时与退出码封存。

验收：机器化到件清单、源码位置/行号及现场 SHA、旧与新来源分类、缺件/责任人表、原件 ZIP 和 receipt。实际等级最高 L1（Python 审计通过），仅静态到件事实为 L0。没有同版真实 trace 时保持 PENDING_PRO_SOURCE_OR_TRACE；board_release_allowed=false。

止损：不凭 Pro 文件名或 candidate 代替 M2 交付身份，不重写 M2 构建预检/D3，不重跑已签功能或 N32。缺件并且无可行动增量时封存交总控，常规进度只存本地；M2 最终签收待用户转发，不声称真人已收到。
