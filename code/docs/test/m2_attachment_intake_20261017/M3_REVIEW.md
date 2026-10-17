# M3 下载附件与既有签收的精确核对（2026-10-17）

结论：M3 核心技术交付已经由 M2 限定复核并进入 develop；本次下载外包增加的是发布收据、原门禁原件和最终转发文本，没有新增待接入的功能源码。不能据该包宣称真实 Pro 基础或板级通过。

## 本次附件身份

| 输入 | 字节 | SHA256 |
| --- | ---: | --- |
| M3_TASK_DAY_FIVE_WINDOWS_HANDOFF_20261017.zip | 2279067 | 146428ff2aaebd253f627356c327e7026a1b9a25d4c82204b58c5d9e50b1e549 |
| FINAL_REPORT.md | 2322 | e77fb675ef75acad6f679d21dc41f9b7dad34a89a95a5e2f66c036fdffa052cc |
| M2_FORWARD.md | 5464 | d6c0910ac50d14b4a3a606f383ca1a4b9bd64e5c0b24704d8db890e65643180c |

两个单独 Markdown 与外包 HANDOFF_FINAL 中同名成员逐字节相同。它们写的历史请求仅为交付背景，不产生新执行许可、恢复旧额度或覆盖 R06 的权限。

## 复核与接入证据

- 附件声明的源提交为 `5aa4959341c9fcc070e9213b66c6ea82ac8d2225`，树 `86ab7472c1a343a2a0f728d885705961c3f6dd46`；本次 Git 读取核同。该提交是核验时已发布 HEAD `ea17d8d2a6f93ea2ebc1195efafb2ceea4fd43a0` 的祖先。
- 附件 PUBLICATION_FILES / INDEX_VERIFICATION 对应的 79 个路径与该提交实际新增集合一致；79 个 Git blob 的大小/SHA 与附件 INDEX 一致，当前发布树仍逐字节保留，工作树文件也与当前 blob 相同。
- 既有正式结论在 `code/docs/M2_M3_Pro新增两次推送限定复核_2026-10-17.md`，该报告由 `170213a17ab3d613be7c857f0ebed8eb8fc536d5` 发布；`code/docs/验证记录.md` V0389 与当前状态 R03 已登记。没有把新下载文件名或旧转发文字当作未签依据。
- 外层 27 成员、总原件 50 成员、四内包分别 62/320/45/209 成员；共 6 个 ZIP，707 个清单载荷。全部 CRC、安全路径、无重名、完整成员集合、大小及 SHA 校验通过。
- 内总包 1268310 字节，SHA `62051d1fe25b914aa59c17e06be0e4e13c74237b0b6b10edcc37314d7118f14f`，与既有 M2 签收表及仓库内原件完全一致。B1/B2/E1/轻量摄取四包 SHA 也与签收表一致。
- 外包相对仓库 coordinator 的 10 个既存文件均逐字节相同。另 16 项是 PUBLICATION_STATUS / INDEX / AST、SEAL_DAY 原双流与收据、GATE_R01 原门禁与输入清单、HANDOFF_FINAL 文本；本次补做其文件身份和内部一致性核验，无新增功能载荷。
- 本次原门禁数据核验：原收据 exit0 / 9项PASS / 142.140秒；stdout/stderr 大小与 SHA 核同。13321 项输入 BEFORE/AFTER 完全相同，79 个提交文件的身份均对应门禁清单。本次没有重跑仓库门禁，也不据旧门禁签新树。

## 限定接受与仍待部分

| 内容 | 已签范围 | 仍未完成 |
| --- | --- | --- |
| B1 | L0 候选观察合同与软件 metadata 准备；原41项结果 | authority_verified=false、真实61字段映射与日历仍待 |
| B2 | L1 适配准备；原版19项加取消修复3项增量 | 最终版22项并未全量复跑，61→29生产连接、真实TX/HOLD/startup/finish仍待 |
| E1 | L0 接入差异与可逆提案、首失败保留 | 正式生产者/CDC/Pro闭包与物理/实屏未签 |
| B0/轻量摄取 | L0 原件身份与既有审计准备 | 实物Part/修订/Bank/MIDI电平/商业工具与同版.fs/完整物理/板测仍待 |

外包旧 D3 未修的叙述是形成时状态；当前源码已经由后续 M2 R05 定向修复并以 L1 限定签收（SHA `eb74ca9ef3cc363163d51e0c8af1a3f9bd8d15905ba3307a5ea1ab8d1c6ed764`）。R06 对合法取消后空闲漏 FRAME 的独立全窗覆盖另有要求；本次不回退 D3、不重跑旧25 CLI、不采用旧提案补丁。

本次附件未提供 R06 M1 19项完整语义、M2实际公开观察出口/TX旁带、M3独立日历/实际成功finish、真实Pro物理与板测等缺件。应按 R06/R06-C1 继续主线，board_release_allowed=false。

## 实际执行边界与原件

仅执行本地自写的文件/ZIP/JSON/哈希及 Git 只读对象核验；未执行附件脚本、测试、HDL/EDA、硬件、Git写命令或外部通信。输出仅本助手的独占目录。详细逐件数据见同目录 `M3_ATTACHMENT_VERIFICATION.json`、`GATE_79_FILE_BINDING.json` 与 `verify_m3_attachment.py`。

辅助检索中一次 rg 将 Windows 未展开文件通配符作为路径传入，报语法123，仅该读取路径失败；无任何修改和被审执行，也未为无必要路径重试。其他核验命令退出0。
