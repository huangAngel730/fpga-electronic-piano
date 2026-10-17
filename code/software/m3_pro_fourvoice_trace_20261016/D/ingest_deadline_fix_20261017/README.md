# D3 漏 FRAME 期限旁路：本轮新定向组

用户于 2026-10-17 明确要求 M2 尝试修复旧 D3。本目录只保存原字节旧入口与新软件定向 harness；不调用任何旧 selftest、runner、捕获、RTL、EDA 或设备。`before_ingest.py` 保持原位置相同深度，使其只读固定解码器的根路径计算不变。

旧入口 SHA 必须为 `3217f97e57daec534306a213c64566fa111e3116f15a15967ca881847c218e07`。新入口是 `../ingest/ingest.py`。harness 在首个 CLI 前冻结自身、Python 可执行文件、旧入口、新入口、固定 decoder 及原始 `D3_COUNTEREXAMPLE.json` 的路径、大小、SHA；每例前后以及组结束再次核同，并为全部输入生成独立 manifest。

新额度仅本组一次，整组最多 90 秒，每个 CLI 最多 5 秒。固定 argv 为当前 Python、`-B -X utf8`、旧或新入口、当例 manifest 和 manifest SHA，不使用 shell。入口及其固定 decoder 不启动后代。stdout/stderr 直接写入当例 `stdout.raw` / `stderr.raw`，保留真实原始双流与实际退出码。超时将停止本次持有的子进程，不按旧 PID 查杀。若 `RUN_01` 已存在则拒绝写入和启动，禁止为补数字反复运行。

矩阵为旧反例 1 次加新修复版 24 例：

| 组 | 数量 | 预期 |
|---|---:|---|
| 原 M2 反例：相同 calendar 与逐行 trace，旧源码年龄835 CANCEL 后 END | 1 | 旧错误接受，记 `KNOWN_BUG_REPRODUCED`，不算正例 |
| 正常消费年龄833、834，RETURN 均在年龄832；834例含年龄833 PA 及年龄834 FRAME 前同沿 PA | 2 | 接受 |
| 年龄832 CANCEL，分别 REQUESTED / ACCEPTED / RETURNED | 3 | 接受 |
| 年龄832 RESET，分别 REQUESTED / ACCEPTED / RETURNED | 3 | 接受 |
| 年龄833 CANCEL，三种 state；REQUESTED 例附后续同沿 FRAME | 3 | `CANCEL_AFTER_UNOBSERVED_DEADLINE` |
| 年龄833 RESET，三种 state；REQUESTED 例附新 epoch 同沿 FRAME | 3 | `RESET_AFTER_UNOBSERVED_DEADLINE` |
| 年龄834 ACCEPTED 与年龄835 RETURNED 的 CANCEL；835例与原 M2 反例本体完全相同 | 2 | `CANCEL_AFTER_UNOBSERVED_DEADLINE` |
| 年龄834 ACCEPTED 与年龄835 RETURNED 的 RESET | 2 | `RESET_AFTER_UNOBSERVED_DEADLINE` |
| 年龄833 / 834 RETURN | 2 | `RETURN_AFTER_UNOBSERVED_DEADLINE` |
| 年龄835 pending 直接 END | 1 | `UNFINISHED_TRANSACTION` |
| FRAME 到期后同沿漏 CONSUME，分别 CANCEL / RESET / END | 3 | 依次 `CANCEL_AFTER_DUE_FRAME` / `RESET_UNCONSUMED_DUE_FRAME` / `UNFINISHED_TRANSACTION` |

新例合计 8 个接受、16 个拒收。每个负例匹配完整首拒字符串及真实退出码1，不接受仅“非零即可”。所有输出都必须保留 `pro_dut_pass=false`、`board_release_allowed=false`。

唯一启动命令由根 M2 在完成 AST 与源码阅读后执行：

```powershell
python -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/D/ingest_deadline_fix_20261017/run_targeted.py
```

输入、逐例命令/双流/收据、首启前来源 `PRELAUNCH.json`、结束来源 `POST.json` 及总收据 `RECEIPT.json` 均在 `code/docs/test/m3_pro_fourvoice_trace_20261016/D/ingest_deadline_fix_20261017/RUN_01/`。此说明不是执行结果；仅以该收据存在且实际判定为准。

source/ROM 载荷全部明确标为 `SYNTHETIC_FIXTURE_PLACEHOLDER`，不冒充 Pro 工程、M1 黄金、真实观察或硬件。完成本组最多支持 L1 合成软件期限拒收结论，不能签完整 Pro 链、串行/时序、板测或功放安全，也不能把旧版历史例合并成最终版全量复跑。
