# 40 MHz 音频精确端点：独立只读软件验收器

本目录只完成任务单第 3 项软件工具和反例，验收等级 **L0/L1**。
`board_release_allowed=false`、`new_sta_executed=false`、`physical_signoff=false`。
没有 Gowin、ModelSim、RTL、综合、PnR、STA 或设备调用；不改原 checker、RTL、SDC、CST、LOC、封存或共享状态。
由主控合并主对话 4 的真实对象清单和报告提案；本窗口不提交、不推送、不占号。

## 输入事实与限定结论

- 仓库开工 HEAD `39b2ab2eef49e47f7816dd86b4f1901f96aea3ca`；已读任务单来自
  `origin/develop` 的 `e2200b2571afe3c38807a2d8ee2e4264c5881fd8`，不切分支/merge/pull。
- 原物理 ZIP：`code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1TD_整机PnR_STA_20261015.zip`，
  SHA256 `17e71ebd5b54743fd0214af5fbfdfd1a4cca4eddbcedab56f7b3df7b3ca521ff`。
- 原 HTML 成员 `pnr/timing.html`，2715163 字节，SHA256
  `524cea6ebb93eca719c5aa86cd6413129299ac2c9da78467ac7709cdf4e8ec62`。
- 原 HTML 是 Gowin `V1.9.11.03 Education` 的实际格式；器件
  `GW5AST-LV138PG484AC1/I0`，`sys_clk` 周期 25.000 ns/40.000 MHz。
- 软件解析其 241 条 Setup 和 28 条 Hold 的 slack-table 行，保留原字节片段和行号。
  **指定音频端点没有同一精确起终点的 Setup+Hold 成对证据**；其中 lane3
  `total_s2_10_s0/Q` → `oct_lut_oct_lut_0_0_s/AD[7]` 只有 Hold 0.000 ns，工具按
  `MISSING_SETUP` 退出 1。原最坏路径报告的 L5 结论不受此软件缺口观察推翻，也不能升级为指定端点通过。
- ZIP 中没有 `.vg` 网表。HTML `Design File` 元数据只指向原 `impl/gwsynthesis/*.vg`；
  不把该指针当成本机存在网表，更不把综合网表自动称为布局后网表。
- 合成正例使用真实 HTML 表头/锚点语法和原报告中实际的音频端点拼写；其中 Setup 行和余量是
  **SYNTHETIC_TEST_ONLY**。它只证明分析器逻辑，不是真实新 STA，不宣称目标物理通过。

## 文件与职责

| 文件 | 用途 |
|---|---|
| `endpoint_audit.py` | CLI / 原始 HTML 解析 / 错误即拒 / 精确端点逐项检查 |
| `fixtures.py` | 原 ZIP 身份核对和明确标识的合成完整 HTML 正负例 |
| `test_endpoint_audit.py` | 身份、精确匹配、数值、双分析、活动状态、结构和原报告单测 |
| `run_selftest.py` | 90 秒单步、300 秒总预算的纯软件入口，保存实际命令/双流/退出码/SHA |
| `seal_software.py` | 验证最终执行源身份并封存限定软件交付，不运行仓库门禁或 EDA |
| `TARGET_SCHEMA.md` | 给主控适配真实清单的精确 schema 与命令合同 |
| `FAILURE_HISTORY.md` | 首次解析代码故障和修复/软件轮次，不抹掉旧结果 |

## 执行

在仓库根目录，使用实际本机解释器（回执记录机器、版本、解释器与依赖 SHA）：

```powershell
& 'C:/Users/songdongkuan/miniconda3/python.exe' -B -X utf8 code/software/m3_m2td_audio_endpoint_audit_20261015/run_selftest.py --output code/software/m3_m2td_audio_endpoint_audit_20261015/runs/R02
```

输出必须是本目录 `runs/` 的新直接子目录，已有目录拒覆盖。每一 CLI 正负例有完整 HTML、targets、
stdout、stderr 和真实退出码；原物理 HTML 原字节复制/manifest、完整解析观察另列 `originals/`。
执行账本、首轮/后继源码 SHA 与实际调用数见各轮 `RUN_RECEIPT.json`，不能跨轮混用。

## 判据与边界

- 不接受自行撰写的中间 JSON timing-records。每次从原始 HTML 重解析；输出记录都携带原报告 SHA、
  row/table/clock 的 UTF-8 原字节偏移（右端不含）、片段 SHA 和行号。CRCRLF 不归一化。
- 外部明确提供 `--targets-sha256`；ZIP 模式还明确提供 `--zip-sha256`。plan 内重复目标、重复 JSON key、
  通配符、整型冒 bool、空目标、错误 source 身份均拒收。SHA 不证明签发者，主控/M2 必须独立核准 targets
  与原件来源；本工具没有创建许可的能力。
- 每个目标分别要求同一精确 from/to、Setup+Hold、双端 `sys_clk:[R]`、对应 relation25/0、有限非负
  slack、真实正整数 path number、有限 skew/data delay、非 inactive/disabled/unconstrained、有效时钟绑定对象。
  任何一条目标缺失即非零，不以其他音频路径或汇总最坏余量替代。
- `require_directed=true` 还要求每个分析的原报告命令为精确单 from/to collection，拒泛化汇总和重复选择器。
  from `/Q` 用 `get_regs` 实例；RAM/ROM `/AD[n]`、`/WAD[n]` 和 FF `/CE` 用 `get_pins` 完整终端，
  只有 FF `/D` 额外允许 `get_regs` 实例。collection 内 `[]` 必须字面转义，原报告端点名仍保持不转义。
  不执行查询，也不证明当前工具可展开；与主对话4提案对齐的只是软件合同，不签新的查询存在性。
- 只支持本次已观察的 Gowin HTML slack tables 与 rising→rising 单 `sys_clk`、25 ns/0 ns关系；
  新格式、其他时钟/边沿、max/min-delay特例不能静默放行，需明确受控适配。
- 可见 HTML 中 Error/FATAL/Failure 或非零 Errors 诊断拒收；Errors: 0 不误判失败。
- 端点双报告不是整机功能、所有音频流水级或实时期限覆盖。无新资源报告、无新物理签收、无下载许可。

最终机器自审与原始执行结果见 `runs/R02/`；原 `runs/R01/` 保留，但 R01 对应的是补强前源码，不能代替 R02。
R02 预期矩阵为 10 次实际纯软件子进程、32 项 unittest 方法（含独立子例），以原收据和双流为实际结果准。
