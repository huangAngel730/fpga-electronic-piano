# M3 R12 软件前端增量交付

本包按原批准计划及用户后续三项阻断修复、精确写集并行授权实施。九个源文件来自互不重叠写集；总控统一冻结、测试、集成与发布，协作窗口没有独立执行测试或发布。

当前 J/G/C/W 四组 40 项限定软件验收通过；G 初轮因夹具路径过长失败，原件保留，唯一 R 修复组复验其完整12项通过。P0、原始失败、条件修复、C/W 结果及真实双流均收入 PUBLICATION_ORIGINALS.zip。C 是真实历史算法处理链，使用明确的合成小窗；W 只在私有 D4.process 边界使用固定软件替身。不能据此宣称真实 C9、数学、RTL、时序、板卡或整体 Pro 通过。

SOURCE_MANIFEST.json 给出最终冻结源码，CASE_MATRIX.json 给出实际验收结果，CAPACITY_PROFILE.json 给出大文件、Windows工作集、物理分块与便携原件。源码内 DEPENDENCIES/CALL_CHAIN_BINDINGS 的 PENDING/NOT_YET_ACCEPTED 字段保留冻结前的声明状态，不能代替独立运行收据。

原 START 11:57:42、16:57:42 截止、3次网络180秒与失败S1的60秒均不重写。用户随后授权修复的 R01 从17:09:21起，操作上限20:09:21；授权、并行计划和新旧消费快照均在 ZIP 的 output_originals/RESUME_R01_20261018 下。旧S1及旧源码/证据按原字节保留；S1修复诊断在释放根进程句柄后、关闭原Job前实测 active=0，涵盖自然结束、晚退子进程和超时清理。

先候选 Gate01，再 S1_SUCCESSOR 封存冻结，最后 Gate02。GATE_02.json、PUBLICATION_RECEIPT.json、RESULT_RECEIPT.json、INTEGRATION_HANDOFF.json 中未来发布状态诚实保留 PENDING；Gate02之后不改 tracked 字节、不增加 metadata 提交。实际最终门禁、Git单文件暂存/提交/普通推送/远端包含关系及完整SHA，只在 S2 的 FINAL_HANDOFF.zip 交付。两次新门禁通过前不得发布。M2只复核本次增量，M2_ACCEPTED/INTEGRATED不由M3代签。

SOURCE_PAYLOAD.zip 是九源原件；PUBLICATION_ORIGINALS.zip 含软件证据、所有正负原件、旧失败、只读依赖和完整便携大文件压缩片。压缩片按 PARTS.json 全序拼接，每片解码≤64MiB，可核每片与全局SHA；未把巨大裸文件直接加入Git。所有ZIP按每成员SHA/CRC核验，自身摘要不写入自身清单。最终树和两门禁之间不改源码。

原定时GitHub检查已按用户要求删除；仅保留必要的任务交接/发布前核验。

## 实际停止点

候选Gate01实际仅6/9 PASS，退出1；bare python 命中WindowsApps占位入口，日志出现9009。已停止发布，Gate02、git add/commit/push均未启动。软件40项仍通过；不是整包完成或M2验收。原本描述门禁/发布的流程段只说明顺序，不能当作执行成功。环境修正建议与新准入条件见GATE_01和PUBLICATION_RECEIPT；不借第二门禁重试。

R02最新用户已明确允许继续并解除20:09截止；实际恢复计划及全部新/旧消费见封存原件中的EXECUTION_PLAN和CONSUMPTION。生产9文件保持原已测SHA，原40项不重跑。新增120秒一次组的两项证据补测通过：持久化实际关键函数有序嵌套调用轨迹，并在已成功读1字节的私有verified文本读取路径第二次物理读取注入同一OSError，异常传播、无关闭排空/追加读取及所有reader/context关闭均有实际证据。历史R01两项未验描述保留为当时快照，本轮由增量闭合。新候选门禁及剩余最终门禁仍分别一次，不互作重试；最终门禁后受跟踪字节不再修改，最终结果/提交SHA/包含性只在ignored输出S2实际包。真实capture/数学/RTL/时序/板卡仍未验证。
