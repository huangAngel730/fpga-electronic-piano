# R13 A 合同总成候选

本目录九件同属 `M3_R13_CONTRACT_20261019_R01`，只组装已有源码/可达原件的机械合同及真实差额，不修改原schema、算法、公共出口或finish行为。交付等级为 **L0 静态候选**；测试、全窗生成、准入、消费、门禁、发布由夜间任务1唯一执行，后续实际结果在 `../backend_close/`，本目录不预写PASS。

从 `CONTRACT_INDEX.json` 进入。它为其他八件保存路径/字节/SHA；其他对象通过同一 bundle_id 与文件名回指索引，避免自含SHA循环。先核索引和上游权威，再读路由与profile、plan/epoch/finish，最后看一页决定表。所有来源ref均指实际文件，来源可信、执行许可和机械SHA相等分别判断。

- A1：`FIELD_ROUTE_TABLE.json` 逐项说明74字段的源公开位、宽度/符号、变换、时基、消费者及null/X/Z理由。72个raw信号和67个DUT公开观察口不是74字段的同一集合。
- A2：`PROFILE_AND_CAPACITY.json` 覆盖D4 raw43/public/CSV往返、intake、serial、math行索引/三类历史、metadata、ZIP快照/重建/分卷，不以raw尺寸代表全产物容量。静态估算不等于W实测；需冻结geometry、存储实现、资源和跨电脑通道再准入。
- A3：`PLAN_IDENTITY_MAP.json` 从原始独立plan复制63字节/23事件和各事件ID/到达窗，实际accept/apply保持null；`EPOCH_RESET_FINISH_CONTRACT.json` 保留D/D+1差额、PRE_NBA、真实reset边、全局行号、唯一finish/END/MONITOR_END与终末身份复查。
- A4：`SOURCE_PROVENANCE.json` 绑定原源码/ROM/include、拟议工具/argv/cwd及可公开环境摘要，显式区分真实原件缺失、合成声明receipt和已执行软件证据；`OPEN_DECISIONS.json` 与 `M2_DECISION_SHEET.md` 只列真实待决。

M1七个INPUT角色已由 `MATH_INPUT_JOB_TEMPLATE.json` 与 `c9_inputs.ROLES` 定义：`mechanical_index/public_rows/raw_capture/independent_plan/frame_plan/reset_edges/provenance`。索引逐项列真实生产者、schema、原件入口和当前消费形态，七件命名没有缺口。D4数学OUTPUT是另一个集合，实际六件：`MATH_ROW_INDEX.jsonl`、`FX_HISTORY.jsonl`、`ADVANCE_HISTORY.jsonl`、`INPUT_AND_APPLY_HISTORY.jsonl`、`MATH_INPUT_BUNDLE.json`、`RECEIPT.json`；17个 REQUIRED_ROLES 则是D4依赖集合，三者不能混数。

M1已签 `CONSUMER_COMPATIBILITY_R11_20261018.json` 明确：唯一未来适配目标为既有 `M3_D4_C9_MATH_INPUT_BUNDLE_V1` manifest及原字节四JSONL流，方向不重问、不另造schema。旧R10 `mechanical_index.rows[]` 消费者和每artifact512MiB整读限制保留；**M1 R13 bounded reader／independent semantics已有L0候选到件**，不能继续说没有实现候选。其新入口 `r13_bounded_consumer_20261018/run_stream_math.py` 使用 `M1_R13_STREAM_JOB_V1`，尚不等于任意旧七INPUT job直接兼容。

真实待办是M1候选的精确输入/envelope及reset原始JSONL→受支持投影、独立plan、canonical FRAME/calendar和origin/来源等价绑定，以及M1自身准入、54案和容量执行验证。CAP01代码仍明确 `CAPACITY_GENERATOR_BINDING_PENDING`，不能在处理时钟外预造fixture绕过。M1功能提交`86cd5975f5679ad2db9da7b0d20d2892e76e76b1`及绑定`7319fe670d3524252ac299e11f00d00ae52c9953`的36声明原件由总控接收，原件入口/去重见 `code/output/m3_backend_stream_r13_20261018/INTAKE/M1_R13_NEW/M3_RECEIPT.json`；索引已绑定关键原件与源码。仅L0到件，无54案/容量/数学通过，不改M1或借M3预算执行。首版及R02九件、交接单继续保留历史。

当前树检查点按总控安全FF收据为`544f5af23fa427db0a931df719dc6135c75a180f`；R13已批功能基线仍为e39，不重开START/截止或旧消费。本次A R03只定点记录到件及状态，不重新审旧包或重做合同。

W仅可使用明确合成的独立数据，≥1130662行且raw≥1398627657B，实际走完整D4后段，无私有D4替身。大对象实际读≤1MiB；单worker/有后代时并发树峰值≤512MiB；全workspace≤24GiB，启动free≥32GiB并保留≥8GiB。仓库路径 `EXECUTION_ORIGINALS.zip`须≤32MiB且能恢复所有逻辑原件；另一既有用户转发通道必须先明确位置与M2可取方法。压缩比未知或只在ignored本机，不构成通道通过。

当前通道更新：用户已在 `code/output/m3_backend_stream_r13_20261018/DELIVERY_CHANNEL_CONFIRMED.json` 确认人工转发 `DELIVERY/` 全目录，包含所有无损卷及清单。独立“缺可取通道选择”项已关闭；GitZIP≤32MiB只放索引/小原件，大卷不要求塞入该ZIP。M2_RECEIVED/M2_ACCEPTED仍false；实际卷名、字节和SHA由生产后原件封存，未预造。24GiB物理几何和其他W前置未因此通过。

真实Pro/HDL/C9、M1数学、时序和板卡仍PENDING，`board_release_allowed=false`。与合成软件容量的前置分层，不自动扩大阻断；整包R13_SW_COMPLETE由总控按原完成条件判定。NoteOn旧勘误已接受，不重提；R12旧42不重跑。七个窗口的协作、直接回传和本写集已经授权，不把静态自审升级成审核员制度。
