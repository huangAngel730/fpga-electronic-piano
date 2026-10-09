# 新封存工具首轮失败（不是业务/行为反例）

首次封存命令（仓库根目录、已有Python3.11）：

```powershell
python -B -X utf8 code/docs/hardware/polyphony_scaling_v1/seal_repair.py --run code/output/m3_t061_b0_repair_20261009_02 --prior-run code/output/m3_t061_b0_repair_20261009_01 --package code/docs/hardware/polyphony_scaling_v1/REPAIR_20261009
```

实际 exit1。工具返回 traceback 指向 prior receipt 的 `.relative_to(ROOT)`：

```text
ValueError: 'code\output\m3_t061_b0_repair_20261009_01\receipt.json' is not in the subpath of 'E:\FPGA\GAOYUNFPGA\team\fpga-electronic-piano' OR one path is relative and the other is absolute.
```

上文是本次工具调用错误输出摘录，不冒充已存磁盘的完整raw stderr。
该失败发生在资格验证、旧载体验证、预算相等检查和deadline注入检查之后，尚未写最终ZIP/manifest。
原 `REPAIR_20261009/` 仅留deadline probe两个raw输出，保持不覆盖，并收入新包。
最小修复先将 prior-run resolve 并检查仍在 code/output；新封存使用
`REPAIR_20261009_02/`。不影响已完成runner02的源身份、40测试及九门禁。
这是封存脚本开发失败，不计入两项Python指定行为反例或RTL负例。
