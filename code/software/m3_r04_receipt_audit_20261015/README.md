# R04 回执返修后继：软件 L0/L1

本包只读核对材料。它不启动 vlib/vlog/vsim、Gowin 或设备。

## 写集与原件

开工 HEAD：`904ccfbf33fddcb3f248be08c5aa0f5e3a446980`，工作树无脏改。
按该版本 `code/docs/M3_完赛任务单_2026-10-15.md` 第一阶段并行第4项，
本次仅新增 `code/software/m3_r04_receipt_audit_20261015/` 和
`code/docs/test/m3_r04_receipt_audit_20261015/`。
旧 `r04_receipt_check/`、`r04_coverage_review/`、`frame_budget_offline/`
及旧包保持原字节；不把旧写集差异改写成事先已获准。
本次直接通知要求的返修落在当前已明确授权的新写集，不请求扩大写权。

旧 core SHA：`f6a2a695a7ffa1d61b6691cd7fc76dcba71bac131ba9943f3cf942f9b2d3cfe1`。
原 core、snapshot helper、原11项测试复制到新目录后，只有新 core 加入
`Error:`、非零 `Errors:`、`** Error`、`FAIL/FAILED/Failure` 全日志拒收。
精确整行 PASS 规则保留；`Errors: 0` 正常汇总不被误拒。

## 两个入口的结论边界

- `receipt_check.py`：保留原参数接口，核包身份、vlog/vsim 退出/超时、编译标记、
  精确 PASS 和输入快照。`PASS` 只表示这些日志/身份条件满足；JSON 始终输出
  `scope=R04_LOG_AND_INPUT_IDENTITY_ONLY`、`real_execution_validated=false`。
- `audit_receipt.py`：按 [真实回执合同](REAL_RECEIPT_CONTRACT.md) 检查三工具双流、
  完整命令/cwd、工具和依赖 SHA、预算及独立提供的 M2 确认 SHA。
  显式合成来源/带 synthetic 标签的流拒收；缺件退出2。
  一致时仅返回 `CONSISTENT_PENDING_M2`，不签回执来源真实性或整机通过。
  M2 确认格式是本工具的拟议输入合同，不能由该软件自发产生或恢复执行许可。

两入口均不认证未经独立核对的操作者声明，不能识别所有恶意伪造。
真正来源与执行额度仍由 M2 核原件。缺逐请求接受/下一真实帧边界/对应 commit
公开轨迹时，逐请求 deadline 始终 `UNKNOWN`；现有 max_cycles 阈值不代替该轨迹。
T052 新长窗没有在本任务运行，旧4207发布完整性保持 UNKNOWN。
一次指定 SHA 的 SRAM 现场诊断仍按原任务单优先，由 M3 真人按其许可操作。

## 文件清单

| 文件 | 用途 |
|---|---|
| `receipt_check.py` | 原日志/输入身份 checker 的隔离修后副本 |
| `snapshot_inputs.py` | 原字节快照 helper 的新目录副本 |
| `audit_receipt.py` | 三工具原始回执一致性检查入口 |
| `test_receipt_check.py` | 原11项回归，复制字节不改 |
| `test_diagnostics.py` | 新增36项错误/精确PASS/严格类型测试 |
| `test_real_contract.py` | 11项合成来源/双流/身份/预算/缺件测试 |
| `reproduce_diagnostics.py` | 旧2例缺陷和新24例矩阵的原始材料导出 |
| `run_selftest.py` | 90秒单步/300秒总预算的软件执行与SHA收据 |
| `seal_delivery.py` | 校验已测试源码稳定、九门禁原始双流、新封包SHA/CRC核对 |
| `REAL_RECEIPT_CONTRACT.md` | 真实回执的明确字段与未验边界 |

## 实际运行与结果

在仓库根目录执行（输出必须是全新目录，拒覆盖）：

```powershell
& 'C:\Users\songdongkuan\miniconda3\python.exe' -B -X utf8 `
  code/software/m3_r04_receipt_audit_20261015/run_selftest.py `
  --output code/docs/test/m3_r04_receipt_audit_20261015/RUN_20261015_R01
```

实际软件执行退出0；原始双流和完整命令在输出的 `SOFTWARE_SELFTEST_RECEIPT.json`。
子调用3次：旧core两例误收复现（预期退出1/实际1）、新core24例指定拒收
（预期0/实际0）、58项unit test（预期0/实际0）。
58项=原11+新错误36+真实合同软件11。子代理预检另有2次软件调用，首次
临时目录权限错误退出1、获批执行身份后退出0；失败边界见测试目录的
`FAILURE_HISTORY.md`。本任务实际 ModelSim/Gowin/设备调用均为0。

新运行收据包含机器、实际 Python 版本/路径/SHA、已加载运行依赖SHA、
运行源码前后SHA、每次命令/cwd/退出码/耗时/timeout，以及原始输出SHA。
`SYNTHETIC_DIAGNOSTIC_CASES.zip` 保留旧误收及修后完整合成输入/输出和被测源。
旧11/新36软件测试不是实际 ModelSim 日志；原R04仍PENDING。

冻结 R04 输入 ZIP SHA：
`1101f1af0809530a150143456aab8ff9a1c66373e9ccbc174c6459e8c916b3bf`；
manifest SHA：`015bf0199c5118ecfe7ec96bfd0b216d8f195daaf4989ec6bc08779def180815`。
本轮复制复用这些身份常量，未再执行旧整机或改变封存输入。
