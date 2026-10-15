# 总控统一发布：40 MHz 音频端点离线准备

用户于2026-10-15撤销误发给主对话4的单独发布要求，改由总控统一发布本综合包。误操作没有产生提交或推送；21项暂存已精确撤销，其误发布副本移至 `E:\FPGA\GAOYUNFPGA\Callback3\chat7\chat4_upload_rollback_20261015\`，可恢复，原项目成果不变。

发布状态以本目录后续 `PUSH_RECEIPT.json` 为准；本说明生成时尚未推送。旧封包中的“未发布”是封存时状态，不篡改历史原件。

发布核对已收到远端 `5cb6d959f75fe7868d8993241b56fcd55d58d6fe` 文档增量并普通快进：最新四包授权允许后续独立有界定向STA。本次只发布先前L0/L1原字节成果，不启动或消费该后续EDA许可；原包“等待许可”的文字保留为形成时边界，后续任务应读最新授权。

首轮原门禁6/9失败：子进程未找到可用 `python`（9009），导致Python语法、T007和reference三组失败。首失败双流／收据和当时启动源保留；后继只为本次子进程PATH前置实际解释器目录，不改系统PATH、不改门禁、RTL或验收阈值，在同步后的精确树重新执行。

## 内容与复核入口

完整原字节交付位于同级 `../delivery_R01/M3_40MHz_AUDIO_ENDPOINT_PREPARATION.zip`，1181740字节，SHA-256：

`7de228bea2cf49341a9be10ac44d493a5c46792bde78e72faf6451ba0da70c52`

包内308份成果文件及MANIFEST，包含主对话2、4的全部源／测试、原报告、片段、派生来源证明、正负例／原双流／命令／退出码、失败历史、两份自审及总控联接证据。不是主对话4的单独包。外部 `MANIFEST.json`、`SEAL_RECEIPT.json` 绑定原字节。

Git只展开核心验收器、schema、目标清单和STA文本提案便于浏览；其余完整源／证据在上述ZIP，避免上传多轮重复的大HTML。Git文本按仓库规则LF存储，原执行的CRLF/LF精确身份一律看ZIP内原字节，不用Git浏览副本冒充原SHA。

需要复现时：先核ZIP SHA、CRC及MANIFEST逐成员SHA；将包在一份同版本仓库副本的根目录按包内 `code/...` 路径展开，不覆盖任何已存在且不同的文件。保留原物理输入 `code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1TD_整机PnR_STA_20261015.zip`（SHA `17e71ebd5b54743fd0214af5fbfdfd1a4cca4eddbcedab56f7b3df7b3ca521ff`）。展开后看 `code/docs/test/m3_m2td_audio_endpoint_audit_20261015/coordinator/README.md`，复验用全新输出名，不覆盖原件。未经展开不要在Git的精简浏览树直接运行依赖完整fixture的测试。

## 已验与未验

- 软件验收器32项单测通过；独立清单13项自检通过；合成正例及七类坏报告均符合预期。
- 总控5对真实端点联接一致：4对缺Setup、1对缺Hold，按预期拒收。10条精确查询提案与验收器一致。
- 仅L0/L1。本次发布门禁属于仓库回归，不是新定向STA，不代签R04真链或实物。
- 同次综合网表／实现数据库缺失；base_s1/base_s2、voice→mix、PCM→I2S实际精确pair仍UNKNOWN。待M2补原件、核query语义，并决定真实STA机器／工具／命令／预算／新输出目录。
- `board_release_allowed=false`。不改SDC/CST/LOC、正式RTL、旧报告／checker、R04/T052或共享编号／状态表。登记交M2，不预占编号。

发布隔离使用现有 `E:\FPGA\GAOYUNFPGA\worktrees\m3_task_delivery_rule_20261015`（detached HEAD），不新建分支，不改变主工作区T052脏改动。只暂存本任务精确清单，经原仓库九项门禁后普通推送 `HEAD:develop`，最终fetch核验；不force、不代发旧未发布成果。

发给M2：待用户转发，尚未送达。请转交上述完整综合ZIP、SEAL_RECEIPT及实际发布回执；原始详尽交接文字在ZIP内 `coordinator/M2_HANDOFF.md`，历史门禁／未发布状态以后续发布回执更新，不回写原包。
