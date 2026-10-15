# M3：40 MHz 音频 STA 端点准备综合交付

2026-10-15。工作区：`E:\FPGA\GAOYUNFPGA\team\fpga-electronic-piano`。

**结论：两个窗口的软件／静态成果已合并核对，L0/L1；完整网表端点任务仍为 PARTIAL／待 M2 补原件和决定真实 STA。** 未启动 Gowin、ModelSim、综合、PnR、STA 或板卡操作，`board_release_allowed=false`。

## 分工与保护

主对话2独占本任务软件目录，完成验收器、软件负例和自审；主对话4独占本任务文档测试目录（除 coordinator），完成原报告端点、片段、提案和自审；总控只写 coordinator，完成 schema 适配、两成果联接和综合封存。主对话3／5未收到本总控消息，T052／R04 文件未由本轮修改；其他窗口的并发工作保持原状。不启用审核员／预审员。

开工 HEAD 为 `39b2ab2eef49e47f7816dd86b4f1901f96aea3ca`，实际 fetch 后任务单版本为 `e2200b2571afe3c38807a2d8ee2e4264c5881fd8`。交付时共享 checkout 的 HEAD 已是后者；本总控与两个实现窗口均未执行 merge/pull/switch，不推定由谁同步。任务单从该远端提交完整读取，附件位于 `E:\FPGA\GAOYUNFPGA\Callback3\chat7`，见 DISPATCH.md。

## 成果入口

- 端点观察：`../targets.json`、`../observed_r03/observations.json`、`../README.txt`。
- 定向 STA 文本提案：`../STA_PROPOSAL_NOT_EXECUTABLE.tcl.txt`，**不可直接 source，未执行**。
- 验收器：`code/software/m3_m2td_audio_endpoint_audit_20261015/endpoint_audit.py`。
- 输入合同：上述软件目录 `TARGET_SCHEMA.md`；原始软件执行：`runs/R02/RUN_RECEIPT.json`。
- 清单自检：`../verification_r03/RECEIPT.json`、原 stdout/stderr。
- 总控联接：`integration_R02/INTEGRATION_RECEIPT.json`，每个目标子目录保留真实 CLI 双流及适配后的目标 JSON。
- 本轮所有失败／旧轮次原件保留；两个窗口各自 FAILURE_HISTORY、自审说明及旧 R01 不替换为新结果。

## 实际验证

| 执行范围 | 实际结果 | 等级／边界 |
|---|---|---|
| 主对话4离线提取、来源逆适配核对、13项自检 | 三子命令 exit 0/0/0，13/13 PASS | L0/L1，派生源码不是综合网表 |
| 主对话2独立验收器 | 32项单测通过，10次软件子进程均按预期结束 | L0/L1，无 EDA |
| 合成完整原格式正例 | exit 0，明确标识 SYNTHETIC_TEST_ONLY | 仅软件正例，不是新物理报告 |
| 缺端点／inactive／仅不相关音频／仅Setup／仅Hold／负余量／错时钟 | 各 exit 1，并匹配指定拒收诊断 | 原 HTML／targets／双流／SHA 留存 |
| 原 ZIP 指定 lane3 pitch pair | exit 1，MISSING_SETUP | 证据不完整，不代表已有整机最坏路径 STA 失败 |
| 总控五对真实端点联接 | 5次 CLI 均按缺项 exit 1；联接入口 exit 0 | 四对 MISSING_SETUP，一对 MISSING_HOLD |
| 提案／验收器查询一致性 | 10/10 命令前缀与精确对象规则一致 | get_regs→get_pins，字面转义 []；工具内集合语义尚待 M2 核实 |

总控联接前后软件源、目标清单、提案、原 ZIP 的 SHA 相同。补强前 integration_R01 与当时执行源保留，最终以 integration_R02 为准。R02 的 `require_directed=false` **仅用于核旧汇总表中的精确 pair 是否双分析齐全**，不免除未来定向报告检查；未来 M2 交付应由独立核准 targets 打开 `require_directed=true`。

### 复现命令

已有输出目录拒覆盖，复现使用新的目录／run-id，不能覆盖这里原件。

```powershell
# 主对话2本轮实际执行，原始参数和各子命令见对应收据
& 'C:/Users/songdongkuan/miniconda3/python.exe' -B -X utf8 code/software/m3_m2td_audio_endpoint_audit_20261015/run_selftest.py --output code/software/m3_m2td_audio_endpoint_audit_20261015/runs/R02

# 主对话4本轮实际执行；解释器为下列 bundled Python
& 'C:/Users/songdongkuan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -I -S -B -X utf8 code/docs/test/m3_m2td_audio_endpoint_audit_20261015/verify_local.py --run-id r03

# 总控最终实际执行，exit 0
& 'C:/Users/songdongkuan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -X utf8 code/docs/test/m3_m2td_audio_endpoint_audit_20261015/coordinator/run_integration.py --run-id integration_R02
```

## 关键来源 SHA-256

| 对象 | SHA-256 |
|---|---|
| 原物理 ZIP | `17e71ebd5b54743fd0214af5fbfdfd1a4cca4eddbcedab56f7b3df7b3ca521ff` |
| 原 pnr/timing.html | `524cea6ebb93eca719c5aa86cd6413129299ac2c9da78467ac7709cdf4e8ec62` |
| 最终验收器源 | `5e50e8c74f82f01b0640005788ea9e09c8d3c8f5cd82839a88f5bac65de7318e` |
| 软件R02收据 | `5781d7182e3ad627491656aa8b5dbd1cacbaddcc3a3cf3beb0baffa64b755dd0` |
| 真实目标清单 | `c95001a3e8faaac2d66cd8d16c4868e393d631dbaafc8c3afdf7b54070188a15` |
| 清单最终自检收据 | `80a3883c3f40b522ac9a7bbd8e5a21855f13edb0a73a82ee3b29aa4936c9445b` |
| 总控联接R02收据 | `a9d145e68b86b500b053c7b2c5e6c85e28c91dd7eec91540af91a4dfdf74f72f` |

## 未完成项与 M2 下一责任

1. 本机没有任务单所指原 output；原物理 ZIP 15成员不含同次 `.vg`／实现数据库。现只能核原报告内节点、物理位置和单类时序事实，不能完成同次网表的对象清单。请 M2 提供原网表／实现数据库原件及 SHA。
2. `base_s1→base_s2` 物理 pair、voice→mix 与 PCM→I2S 的实际精确 pair 均 UNKNOWN。源码和有限报告未显示对象，不证明优化掉，也不允许拼接旧名字。M2 核实际对象后决定最终目标。
3. 五对候选分别只见一类分析，现无指定 pair 的完整双向报告。M2 核 get_regs/get_pins 集合、转义、时钟关联与活动路径后，另定机器／工具 SHA／精确命令／预算／新输出目录，才可执行定向 STA。
4. 用户补充工具目录 `E:\FPGA\GAOYUNFPGA\138K\tools`；仅记录，不代表已核工具或获得执行许可。
5. **未提交／未推送。** 本任务仍有原件缺口，不冒称彻底完成。发布门禁未执行：原 `check_repo.ps1` 会调用 `run_t025_top_stat.py`，后者第28–29行固定在 `code/output/` 创建目录，超出本轮两个新目录的严格写集；当前还有其他窗口 T052 脏改动，不能冒称冻结精确发布树。请 M2 决定门禁写集／串行发布安排；未经明确许可不改原门禁、迁移工作区、改临时 index 或绕过 9/9。共享编号／状态由 M2 登记，本轮不取号。

本准备不替代 R04 真链功能、逐帧 deadline、电气或板级实物验收；不增加任何码流放行权限。
