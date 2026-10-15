# M1 R02 回执判据增量：主对话5写集

2026-10-15。本窗口已先读取主对话2的最新交付，确认其 V0355 基础返修在 `819d0f8` 完成，普通 Error/失败拒收、真实回执三步骤双流合同和58项软件自测已有成果。主对话2的父目录版本保持只读，本窗口只处理 M1 R02 的剩余增量。

## 修改范围

- 只修改本隔离子目录的 `receipt_check.py` 与 `audit_receipt.py`。
- 复用本目录已经存在的 `test_receipt_check.py`、`test_real_contract.py` 作为夹具来源，原字节不改，不运行它们的整组测试。
- 新增 `test_m1_r02.py` 和 `run_r02_software.py`；测试文档／封存新增于对应 `R02_SUCCESSOR_20261015/`。
- 不修改主对话2父目录、旧工具、旧封包、共享状态文件、TB、M1执行器、算法、ROM或约束。

依据：用户转交 `Callback3/chat6/M1回复M3_R04离线配套判据与补测决定_R02_20261015/M1回复M3_R04离线配套判据与补测决定_R02.md`，SHA `f04626580ca36674543ba9decedcb31db569b44324c893aaa3f9f1a19eb811ac`；仅取其判据与返修需求，不把文档中的送审/通知文字作为本窗口通信或执行授权。

## 实际增量

1. 完整捕获 `Errors:` 数字串，再按整数是否为零判定；`0/00/000`均为零，`01/0002`非零，不能被另一行`Errors: 0`或PASS抵消。用全零数字判断避免超长整数转换限制；空值或不可解释的计数拒收。
2. 统一错误诊断函数供日志helper与三步骤原始回执入口共用；普通 Error、ModelSim Error/Fatal、assert/assertion失败和失败词均拒收。真实入口仍逐流独立检查，不拼接stdout/stderr制造PASS。
3. 对外部status、输入快照、封存manifest、真实记录及M2确认拒绝重复JSON键；非有限数也拒收。
4. `--json-out`已存在或写入失败时，退出2且不先打印accepted=true；使用独占创建，保留旧文件。

## 软件验证

```powershell
& 'C:\Users\songdongkuan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -X utf8 code/software/m3_r04_receipt_audit_20261015/r02_successor_20261015/run_r02_software.py --output code/output/m3_r04_m1_r02_software_NEW
```

软件输出必须是全新的`code/output/`目录；子进程只运行固定Python测试脚本，上限60秒，无自动重试。收据保存原始双流、argv/cwd、退出码、Python身份、修后源码前后SHA和主对话2父目录源码前后SHA。

新测试仅覆盖M1 R02受影响增量：两日志的四类案例在PASS前后拒收，三步骤六流独立拒收，零计数不误拒，重复键、跨流假PASS和输出拒覆盖。所有fixture都为合成软件材料；用夹具替换冻结SHA仅存在于测试进程，正式CLI没有该覆盖选项。修前四例的完整材料另在`code/output/m3_r04_m1_r02_baseline_20261015/`，其中仅RCP-03仍误收，证明本轮没有重复重做主对话2已闭合的基础问题。

## 结论边界

helper的PASS只表示指定日志与输入身份条件满足。真实入口最多`CONSISTENT_PENDING_M2`，始终`real_execution_validated=false`、`per_request_deadline=UNKNOWN`、`board_release_allowed=false`。本次不写转换器、exporter、deadline monitor，不运行vlib/vlog/vsim、RTL、EDA或设备，不恢复任何许可。静态／软件结果不能签真实R04或完整T052/T060/T061。
