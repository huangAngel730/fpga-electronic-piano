# 主开发收尾交接：R13 Flash 版本（2026-11-13）

请主开发接手核对当前有效任务单、Git 工作区和远端状态，再决定将下列版本作为交付基线并完成项目收尾。用户本轮明确要求：整理版本信息交主开发，由主开发收尾并推送 GitHub。本文是交接材料，不代替主开发的最终验收或发布回执。

## 2026-11-13 主开发接收与发布状态

- 已接收 R13 版本交接。烧录窗口的历史执行记录显示，操作 53 与 66 使用同一路径的 R13 位流、GW5AST-138C、同一下载器位置 9009，两个进程均自然退出 0。回执生成时的完整 JSON 记载位流 SHA、Flash ID、写入和校验成功。当前可回看的两次 Programmer 输出有截断，结束提示取自该回执。
- 入库范围为本文、外部 Flash 烧录经验及本次小型 JSON 回执。回执副本按仓库规范使用 LF，字段和值与本机原件相同。本机原件路径为 `code/output/n32_c1_r13_lissajous_sram_20261105_r01/FLASH_PROGRAM_VERIFY_RECEIPT_20261105.json`，1030 字节，原 SHA-256 为 `59ac372999d6597b2fca1e9047c2a2649aa5b550cd86f29cf2af2563e0169b37`。
- 2026-11-13 固定 Git 窗口恢复原命令入口后完成 fetch，确认本机工作历史与 `origin/develop` 分叉。主开发采用独立发布树承接这三份资料，固定 Git 窗口负责最终树九项门禁和普通 `develop` 发布。
- 断电自启动及 HDMI 功能实测待补。当前交付范围是版本身份、烧录经验和写入／校验记录，整板功能验收保留待测状态。

## 版本身份

- 工程/版本：`N32_C1_R13_LISSAJOUS`（R13 李萨如显示增强）。
- 输入包：`N32_C1_R13_李萨如放大与标题_转发包_20261105.zip`，SHA-256 `f659555efc082d932e3bd76a4b4dc6d9435a6bc50c06c21939fe6325ef0cf188`。
- 实际烧录文件：`N32_C1_R13_LISSAJOUS.fs`，SHA-256 `0b994492ecd4ac4a6e504568e2a71ed9f048ef572ceea56ac03193f4bd26363c`，文件长度 42,340,876 字节（`.fs` 文本文件；Flash 有效配置写入区间由 Programmer 报告为 `0x000000`–`0x0509E00`）。
- 目标：Tang Mega 138K Pro C / GW5AST-138C，JTAG ID `0x0001081B`；Programmer 读到外部 SPI Flash ID `0xEF4018`。
- 构建工具：Gowin 商业版 V1.9.12.04；包内构建回执 `STA=PASS_ALL_CRITERIA`，状态 `TOOL_EXIT_0_REPORT_REVIEW_REQUIRED`，原构建记录标记 `board: NOT_RUN`。

## 实际板上结果

- 2026-11-05 SRAM：一次 SRAM Program，退出码 0，User Code `0x000060E8`，状态码 `0x00026230`；未执行 Flash/Erase。
- 2026-11-05 外部 Flash：用 Gowin Programmer V1.9.12.04，操作 `exFlash Erase,Program Arora V`（index 53）一次写入，Flash ID `0xEF4018`，起始地址 `0x000000`，工具报告 `Program Flash finished` / `Finished`，退出码 0。
- 随后对同一 `.fs` 执行 `exFlash Verify Arora V`（index 66），工具报告 `Verify Flash successfully` / `Finished`，退出码 0。
- 仓库证据见 [Flash 写入与校验回执](evidence/r13_flash_20261105/FLASH_PROGRAM_VERIFY_RECEIPT_20261105.json)和 [Flash 烧录经验](Tang_Mega_138K_Pro_C外部Flash烧录经验_R13_2026-11-05.md)。SRAM/JTAG 会话保存在本机 `code/output/n32_c1_r13_lissajous_sram_20261105_r01/SESSION_20261105_163800`。
- **尚缺硬件功能验收**：目前材料没有记录 Flash 写入后断电再上电自启动、HDMI 显示或功能实测。不能将“Flash Verify 成功”表述为上电启动通过。

## 请主开发收尾时处理

1. 按仓库 `AGENTS.md` 与 `code/docs/协作入口.md` 读取最新有效任务单、唯一当前状态快照及活动任务索引，确认 R13 是否是本次交付应采用的版本；若仓库/远端已有更新基线，按有效任务单处理，不以本交接覆盖更新版本。
2. 核对本地实际位流、包清单、SHA-256 与上述值一致；检查两个新文档和烧录回执是否在当前工作树，保留其他人的未提交修改。
3. 将断电重上电/HDMI 的真实结果补入验收证据；如果暂时无法实测，明确标记待验，按项目的最终交付规则决定能否发布，不写成完全实测通过。
4. 依据用户授权，由固定 Git 工作会话执行收尾、仓库门禁、提交和 GitHub 推送；遵守当前分支、单文件暂存、最终 fetch、`check_repo.ps1`/九门禁及禁止 force push 等规则。推送后核远端包含精确提交并回报提交 SHA/链接及剩余未验项。

## 交接边界

本交接确认的是 R13 这一位流的本地构建与板上 Flash 写入/读回校验记录，不自行认定它覆盖所有项目功能，也不代替主开发的任务单核对、最终集成验收、提交或远端核验。
