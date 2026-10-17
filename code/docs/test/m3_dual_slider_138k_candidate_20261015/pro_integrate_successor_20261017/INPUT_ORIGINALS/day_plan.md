# M3 task-day 五窗口执行单（2026-10-17）

当前目标是用户新交的task-day当日单，不恢复昨夜任务或其轮数。用户在总控本轮直接授权夜间任务1–5互发任务/结果，1调配2–5，允许各窗口用子智能体自审；审核员/预审员制度未启用。通信证据见USER_COMMUNICATION_AUTH.md。

有效输入：E:/FPGA/GAOYUNFPGA/night_task/10.17/task-day/M3_当日任务单_2026-10-17.md（10460 bytes，SHA256 4142a701d0f48c3965c0596641be859d85cf7788b2d17d5d3af64f0e1745af75）；同行M3_完赛任务单_2026-10-15.md（62906 bytes，SHA256 7235fb23d4584687259d2743aaa4b91a517e2b5bd3dc8867f0e29857f3b14033）。原件复制入INPUT_ORIGINALS，保持原始字节。开工GitHub fetch成功，本地HEAD/远端跟踪均414e1a9d3ee0617c5e8ba72dd4b22c36122c9926，跟踪文件与index干净；旧未跟踪原件保持。现场SHA和status另存START_IDENTITIES.json。

优先级：Pro四声基础→M2双音色→M3双滑块→固定左波形→最小真实传谱→N32。后项只允许当日单明确的无板独立准备，正式接入/EDA/设备按原顺序。已签C/D、E1–E4和上午被动监视器只读复用，不重跑旧303/487/22坏例。

时间盒：本轮T0=2026-10-17 10:04:35 Asia/Shanghai，最长4小时（14:04:35前封存/停机），必要成果完成或无可行动任务即提前停止；这不是最低工时或自动续跑安排。当前没有可控实体板卡/仪器会话及新Pro码流准入，B0只做既有资料静态核验，所有电气实测、下载、音频/实屏为NOT_RUN。商业许可未核定。ModelSim SE-64 2020.4版本认可不等于新增执行预算，本单ModelSim/Gowin/PnR/STA/码流/下载0；现有Python/可选Icarus仅在当日授权新隔离写集有界自检。

| 窗口 | 主责 | 独占写集与输出 |
| --- | --- | --- |
| 夜间任务1（夜间总控） | B0官方资料/实物缺口核查、来源冻结、汇合、自审、门禁及发布 | docs/hardware/pro_fourvoice_board_intake_20261017/；本pro_binding_20261017的docs/test/coordinator_20261017和software/coordinator_20261017。任务/状态文档归M2，不改共享状态。 |
| 夜间任务2 | B1新Pro独立事件/交易接入；toy差异、最小公开字段和严格来源门禁 | software、tb/board、docs/test下m3_pro_fourvoice_trace_20261016/pro_binding_20261017/，明确排除intake_20261017/及coordinator_20261017/。不另造toy黄金；缺源时PENDING_PRO_SOURCE_OR_TRACE。 |
| 夜间任务3 | B2公开逐沿→既有串行检查入口、同源身份及拒收路径 | software、tb/board、docs/test下m3_pro_fourvoice_trace_20261016/pro_serial_successor_20261017/。只读消费B1合同，先做无需真实源的有效部分；不复制已有D3/解码器或重跑其已签组。 |
| 夜间任务4 | E1双滑块Pro接入差异/七组CDC及64/98bit源身份 | rtl/input、tb/input/visualizer、docs/test下m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017/。本轮只补静态真实来源/UNKNOWN及可逆差异，不复制旧RTL做相同自测、不修闪光FAIL。 |
| 夜间任务5 | B1到件身份审计；兼核下游E2/E3真实Pro依赖和现有原件，不重复实现 | software、tb/board、docs/test下m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/。来源检查不代M2构建预检；E2/E3旧目录只读，不运行旧耗尽6/6组。 |

B1总六轮分配：夜间任务2最多4轮，夜间任务5最多2轮，分别记本子目录消费；不能各领取六轮。B2最多六轮，但成功停止，首失败保留。E1只读静态核验及必要新软件自检最多2轮，不启动新RTL/EDA。Python每组≤90s，可选Icarus编译+新夹具每组≤240s；全窗口新功能执行累计≤3600s，四小时时间盒优先。所有实际启动记录argv/cwd/工具版本与SHA、UTC起止、PID/退出码、原始双流、源/依赖/产物SHA，不用盲重试凑轮数。没有新实迹只完成当日单允许的接收/拒收入口或差异表，未验真实Pro保持PENDING。

各窗口先读用户任务原件和本计划，再核旧成果及当前输入，先写自己的START/预算。每窗口可委派必要只读子智能体检查新代码/关键反例，避免重复全面审核。实际工具执行仍由主实现窗口按预算控制。

只发一次完整派单和一次最终回执；确需澄清写集/实迹/许可阻断才追加消息，常规进度放本地收据。只向总控回传，不互相安排工作。发送许可来自用户原文，不能把本条AI消息本身当成新的通信授权；有需要可读总控最新userMessage核验。

其他窗口不动Git index/commit/push，不跑仓库门禁、不取V/D/T、不改状态/看板、不编辑正式top/pkg/CST/SDC、M1模型/M2工程或旧封存。总控最后汇总只提交授权且齐套内容，精确树check_repo 9/9、单文件暂存、普通推送并核远端SHA。每项区分DONE限定准备/PARTIAL/BLOCKED/NOT_RUN，保留失败原件及旧等级。

收工每窗给RESULT、机器化RECEIPT、实际文件清单及ZIP本体，含输入/源码/依赖/工具/输出SHA、正负例/首失败/退出码、额度消费与未验项。M2最终限定复核与共享状态登记待用户转发；本轮五个AI的送达/回传不等于真人M2签收。board_release_allowed=false。
