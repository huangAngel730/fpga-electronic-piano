# 真实 R04 回执输入合同（拟议软件格式，实际材料尚缺）

本合同明确 V0355 所列缺件。它不产生执行许可，不替代 M1 执行器，
不授权 M3 代跑 R04；只有 M2 确认精确输入/机器/次数/预算后，M1 才可执行。
当前无真实回执，不写实际机器、工具版本或 M2 引用的猜测值。

## 原件清单

1. 独立提供的 M2 原始确认文档及 SHA/引用，精确绑定输入 ZIP、机器、
   vlib/vlog/vsim 的参数向量、cwd、工具/依赖身份、分项和总预算。
   SHA 必须从独立确认获得，不能只信运行者在同一回执中自报的哈希。
2. 三步骤各自的完整原始 stdout 和 stderr（空stderr也保留空文件及SHA），
   literal command参数数组、cwd、实际进程退出码、elapsed_seconds、timed_out。
   只给合并日志、截图、PASS摘录或摘要不满足本合同。
3. 工具绝对路径、实际版本、二进制 SHA 和运行时实际依赖文件路径/SHA。
   如工具依赖尚未穷尽，应记 UNKNOWN，不冒称完整冻结。
   工具身份是操作者原始记录；本离线工具不能仅凭其自报SHA认证远端二进制。
4. 完整 R04 原 ZIP、manifest 和源/ROM/编译输入的执行前后快照。
   每个成员的大小/SHA必须与冻结清单一致。输入快照helper只读文件，不能启动EDA。
5. 整轮开始到最终产物收集结束的总耗时及原件清单；不能只用三个工具时长
   的和代替包含收尾的墙钟预算。失败/超时同样交原件，不自动重试。
6. 若要签逐帧期限：另交公开逐请求接受、下一真实帧边界和对应commit轨迹，
   绑定ID/取消/复位寿命；当前R04只有累计max状态，故该项UNKNOWN。

## `audit_receipt.py` 的 JSON 结构

这是提议的输入结构描述，不是实际运行收据；需 M1/M2 对接后采用。
所有文件路径相对 `--evidence-root`，拒绝逃逸目录；工具/cwd字符串保持原执行身份。

执行记录 `schema=r04_original_receipt_v1`：

- `evidence_kind`：真实原件声明 `REAL_TOOL_OUTPUT`；合成/未声明拒收。
- `machine`、`source_archive_sha256`、`package`、`inputs_before`、`inputs_after`。
- `total_elapsed_seconds`：包含最终收尾。
- `steps`：恰含 `vlib`、`vlog`、`vsim`；每步包含：
  - `command`：非空字符串数组；`cwd`：原工作目录。
  - `tool`：`path`、`version`、`sha256`、非空 `dependencies`（每项path/sha256）。
  - `stdout`、`stderr`：各含 `path` 和原字节 `sha256`。
  - `exit_code`：严格整数；`timed_out`：严格布尔；`elapsed_seconds`：有限非负数。

独立确认 `schema=r04_m2_confirmation_v1`：

- `reference`：M2实际确认引用；`machine`、`source_archive_sha256`。
- `total_budget_seconds`：M2实际确认的正数预算。
- `steps`：同三步骤，各含完全一致的 `command/cwd/tool`，以及 `budget_seconds`。

离线检查命令（占位符必须替换为真实原件，不填合成值运行后冒称实测）：

```text
python -B -X utf8 audit_receipt.py --evidence-root <原件根目录> --record <原始记录.json> --m2-confirmation <独立M2确认.json> --m2-confirmation-sha256 <独立获得的确认SHA>
```

退出码0：字段/流/输入/确认绑定一致，仅 `CONSISTENT_PENDING_M2`；
退出码1：明确不一致/错误/超时/合成来源；退出码2：缺件或格式/身份不可解释。
输出始终 `real_execution_validated=false`、`per_request_deadline=UNKNOWN`，
M2 独立核来源后才决定实际功能等级。`REAL_TOOL_OUTPUT`自报标签不是防伪签名；
本工具拒绝已知合成材料，不能保证识别人为去标签或全套重造的假证据。
