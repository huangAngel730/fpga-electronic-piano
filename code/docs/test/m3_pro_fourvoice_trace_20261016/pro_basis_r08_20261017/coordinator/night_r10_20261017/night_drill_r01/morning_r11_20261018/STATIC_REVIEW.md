# R11 包 A 静态自审

本窗口及自己的只读子智能体自审。没有启用审核员/预审员制度，没有新运行结果。

R02 仅处理总控在精确 index 封存中发现的换行存储阻断：LF JSON 为正式 baseline，原字节与 R01 所有原件在 ZIP 留存；候选仅替换 baseline SHA 常量，未改比较/运输逻辑。检查限字节、JSON 等价、归档成员、引用和哈希；本轮未扩大自审或运行程序。旧9/9门禁不能代签当前最终 index，仍由总控重跑。

## 原缺陷与后继

| 原件位置（同级旧 night_drill_r01） | 可由源码确认的问题 | 后继 |
|---|---|---|
| software/network.py:34–100；intake/engine.py:238–300 | 原真实网络仅记 network.json，未调用安全 outbox；合成 outbox 用例不能证明真实发送已复用 | transport.send_once 实际路径调用原 Store.enqueue → begin_attempt → 原 network.run → finish_attempt；完整提交 refspec、原始流与稳定 key 持久化 |
| software/run_group.py:127–139；verify_inputs.py:75 | freeze 后重新读取 HANDOFF，并从同一个可变对象取得 task/version；sample tree 硬编码 | verify 独立 raw descriptor、冻结预期、输入/源码、结果与归档核验；receive_frozen 用冻结预期，先留下 RECEIVED，不自动 advance |

## 本次静态发现及修正

1. 初版结果 equalities 可为空，SEND 只要求归档 contract，可能混合 run A 结果与 run B contract。已加入新生产强制 provenance 与必要结果归档；历史样例不能入队。旧原件缺 raw-contract 绑定不能修复为旧运行通过，保持 MISSING。
2. 初版仅前置检查 deadline，剩余 1 秒也可能启动固定 30 秒运输。已在消费前及实际调用前重新要求 ≥31 秒；消费后失败不回退尝试。当前未用模拟时钟验证。
3. 本地 manifest 相等不证明待推提交树相等。准入中新增完整 commit 的逐 blob 原始输出身份核验，禁止凭本地文件状态认定提交正确。当前未执行 Git show。
4. 固定旧网络完整快照 SHA，防止把空/缩短的 snapshot 当成全部历史；原历史前缀逐项不许改写。当前原 ledger 未修改。
5. 排除 provenance 中尚未产生的 outgoing result_commit，避免 Git 内容自引用；发布后 commit 证明单独保存、另核实际提交树，不要求倒灌进执行归档。

## 实际检查边界

只做文本阅读、JSON 读取、文件字节/哈希、ZIP 成员清单和本体身份核对。候选未 import、compile、AST、selftest 或执行；未启动任何子进程组、worker、网络、HDL、EDA 或设备。静态推导不能替代语法、运行、故障注入、跨进程锁或真实传输验证。

旧失败、CONSUMPTION、RUN_CONTRACT、HANDOFF、结果、源码、共享状态和看板均保留。新包在两个授权后继目录。当前发布仍由总控使用旧已验入口；本窗口不 add/commit/push，不代签 M2 接收、复核或集成。

元数据封存脚本曾在未使用的 `$oldrefs` 赋值中误把 `network.py,$null` 传给单路径 Ref，产生 PowerShell 非终止路径错误；工具进程退出码仍为0，不能据此把整个脚本称为无错误。该变量没有用于已写出的 SOURCE_BINDINGS。已保留 `METADATA_TOOL_NOTE.json`，去掉该无用调用后重新核对最终描述符；这不是候选运行或旧测试重试。

## 未验及准入缺件

固定依赖的动态装载/Windows Job 的实机接合、outbox 与 network ledger 在异常边界的一致性、计时边界、硬退出/锁恢复、重试分类、精确 commit refspec、文件变更并发及新 schema 正负例均未运行。真实故障/UNKNOWN/双机恢复依旧 PENDING。当前没有新同次 provenance、精确新发送成果、测试 runner 或新运行准入，不得从历史样例启动。
