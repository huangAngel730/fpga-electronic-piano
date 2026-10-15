# 给 M2：T052 长窗 R02 补件，待准入

**待用户转发，尚未送达。** 本件不是新 RTL 执行许可，不更新共享状态/编号表。

M2，V0357 要求的首沿修复与监督 runner 已交新候选。功能提交 `96abfa56817e832ca5fb02ce25756ae13e464f64`，19个文件均限原授权三个新长窗目录；已普通合并你新发布的 `5cb6d95`，合并提交 `a18e5fc7a8ec996f1ac1786e62a6d0998413101d`。后续仅附本交接与合并后门禁原件；最终发布提交/远端核验见窗口交付消息。未修改算法、ROM、旧checker/capture、旧JSONL合同、正式工程或共享状态表。

1. TB下降沿加`$time>0`，源码绑定的7项软件检查确认10ns首正沿row0、20ns读row1、全8536336沿连续；无保护/#0变体拒收。新TB未编译。
2. runner使用挂起创建→加入Windows Job→ResumeThread，强制单步/总墙钟、两路有界日志、捕获/总输出超阈值终止整棵子树；持久独占attempt及逐步消费、不自动重试。29项真实Python假进程/软件正负例全通过，子孙以Job清空＋创建FILETIME＋心跳确认停止；不是RTL行为反例。
3. 首轮24例中2个误拒的原失败收据、双流保留。计数收敛及实际退出码处理已修；AccessDenied不冒充进程消失；最终源码前后SHA同。早轮失败源码仅留SHA、没有字节快照的缺口如实列明，后续轮有source_before.zip。
4. `run_runner_preparation.py --prepared code/output/m3_t052_long_preparation_20261015_03/prepared --output code/output/m3_t052_runner_revision_20261015_01` 的真实Python命令/双流/各子步均退出0。最终合并树`check_repo.ps1`九项PASS/exit0，`git diff --cached --check`退出0。两个前置门禁及合并后的门禁原件都保留。新T052编译0/采集0，Gowin0/设备0，L0静态与软件证据；旧4207 UNKNOWN、完整T052 PARTIAL不变。

## 需要你复核/决定

请核下列完整SHA及包内精确argv/cwd、源/ROM/完整controls、工具/机器/环境、额度目录和预算后，再签一次新compile/run/check；当前锁闭提案`approved=false`，不得自行置true。

**特别边界：** stdout/stderr各16MiB可精确限写；直接捕获文件是50ms轮询、超750MiB捕获/1200MiB总输出后终止，可能瞬时超量，**不是NTFS硬配额**。请明确这一动态阈值语义是否满足准入；若要求任意时刻零超量，现候选尚未实现，不能放行。90/300/300/900s不扩大；树清理至多2s及后置哈希/收据耗时单列。OS强杀/断电缺最终收据只算INCOMPLETE。动态加载依赖UNKNOWN、真实全流程/吞吐、两个可编译RTL行为反例、PCM及实物全部未验。

原离线checker仍exit3/PROVENANCE_NOT_VERIFIED；runner即使完整比对也仅交`RAW_ATTEMPT_FINISHED_PENDING_M2_PROVENANCE_REVIEW`，不自行签完整T052 PASS，不将缺帧/缺来源的exit3偷换成成功。基础四声部及现场唯一SHA SRAM诊断继续优先，本轮未扩大其他包执行。

## 转发原件与完整 SHA-256

本目录原件：

- `T052_LONG_RUNNER_R02.zip`：1085022字节，983成员，CRC与每成员SHA/字节全核；包含新源码、锁闭提案、全部软件正负例/首失败日志以及原R01 ZIP本体。
  `3776ea3d85f09099e7b33f5705d79300c4475697b5a0f1cfaed3dcfd603d54ee`
- `REPOSITORY_GATE_RUNNER_R02_MERGED.zip`：合并后最后一次门禁的原stdout/stderr/receipt。
  `d229417aca7bddb6ded16f0639fefc0a8b2bfcf438ddccdac50c0d31a3adbf69`
- `LOCKED_RUNNER_R02_PROPOSAL.json`：精确组合原件，源/输入/静态工具依赖各完整SHA逐项列出，仍false。
  `2a05f0fdff73b4f65c8c7898535b12369055fccdb36f21e1fe0eea756d8611f9`
- `RUNNER_R02.md`、`RUNNER_R02_RESULT.md`：命令、边界、失败历史、文件清单及未验项。

关键源码：

```text
tb_t052_long.sv
daf67848153214d791d1f51e348dbbe7c7995c06424f0a819a23080c1fba3e20
bounded_runner.py
f55d19ac0584b8e483c7a7299c841b804ba1ebbe261c06194af33c12e6d5e10b
win_job.py
2b8301d4121f28632eb58a07ac458b2c57236eca27177070b7379ff9ee796a0e
controls.hex（不变）
fd220e83da98c03f0181c0a45e4edfa2ddc77adda055911508e7f7469131d4d0
```

完整文件级SHA与原件以新ZIP的`MANIFEST.json`和提案为准；旧R01只作为旧输入/来源，不冒称已修复。M2负责精确组合复核与执行准入，用户转发并不等于已签收。
