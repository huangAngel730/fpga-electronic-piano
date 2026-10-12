# C 最终预算收尾后继：供 M2 增量复核

2026-10-12。对应 V0301 的末尾 artifact SHA 越过 900 秒仍退出 0 问题。
仅软件 L0/L1 增量；不放行 A/B。完整 T060/T061 仍为 PARTIAL。
本说明及交付通知：待用户转发，尚未送达。

## 修改边界

只修改原授权目录的 controlled_runner.py、test_followup.py、prepare_followup.py、
deliver_followup.py；新增本说明及同级新封存目录。业务 RTL、ROM、TB、observer、
源码日历 oracle、数学模型、原 A/B 计划、原封存和失败证据均不改。
不更新共享状态/编号表，由 M2 统一登记。

runner 最终产物只遍历和取 SHA 一次，每次取 SHA 前后及遍历后均检查剩余总预算。
越界时返回 FAIL_PARTIAL/1，保留原日志和已取得身份，不在失败收尾重新扫描/哈希，
不重新执行任何工具。产物收集完成后才决定最终状态，并在主收据写出后再次检查。
最终元数据修订写出完成也检查预算；跨限只能追加 FAIL 元数据，不得恢复成功。

时间口径：正常收据 elapsed_seconds 包含产物取 SHA 及主收据写出；最终元数据写出
完成另做成功资格检查。文件不能在自身内容中记录自身最后一字节完成时间，故正常
elapsed_checkpoint 明示 AFTER_ARTIFACTS_AND_PRIMARY_RECEIPT_WRITE，不能理解为
最后一字节自计时。终端写出跨限则记录观测到的越界时间和 FAIL；保存该 FAIL 的
最后一次元数据写入不再递归自计时。单个 SHA 跨限在该 SHA 返回后拒收，不宣称能
中断底层单次文件读取。没有重启预算、忽略越界或多次重扫的放宽。

## 新增检查与实际结果

正式证据目录：code/output/m3_c_budget_tail_20261012_02。
总资格检查限制 300 秒，单步最多 90 秒；实际 3.390 秒，进程退出 0，
状态 NEW_C_BUDGET_TAIL_SOFTWARE_PASS，源 SHA 执行前后完全相同。
此前 _01 为加入原始源码差异收集前的软件中间资格轮，保留本地，不作最终证据。

| 新增合成时钟场景 | 内部 runner 结果 | 取 SHA 次数 |
| --- | --- | --- |
| artifact SHA 899→901 秒 | FAIL_PARTIAL，退出 1，保留部分身份 | 1 |
| artifact SHA 899→899.25 秒 | PRECHECK_ONLY_EXECUTION_LOCKED，退出 0 | 1 |
| 主收据写出 899.25→901.25 秒 | FAIL_PARTIAL，退出 1，不重扫 | 1 |

仅选择 FinalizationBudgetTests 三项；测试框架退出 0 表示断言通过，不能把拒收场景
的内部 runner 退出 1 误写为退出 0。合成时钟不是实际等待 900 秒。各 probe.json、
原 stdout/stderr 和步收据均封存。四步为授权四文件原始 diff、新三项测试、
新身份包生成、包内 runner 默认锁闭预检。

原 13 项软件检查引用 V0301，原 22 项引用 V0295，均 REUSED/NOT_RERUN；
A 长程软件检查 NOT_RERUN。不重复已签原专项，不新增数学或 RTL 结论。

## 精确身份及拟执行机器

拟执行机器：M3 当前本机 LAPTOP-KSS1MRR7。不能把这份 config 的绝对路径或工具
替换成 M2 机器版本而保持同一身份；迁移必须重新绑定并交 M2 复核。

新配置 CONTROLLED_CONFIG_NOT_AUTHORIZED.json，143354 字节，SHA256：

`deef8bc73b6f8f2789149f3c1558bf05954919dbe05cda1d03dd2e97fefce637`

配置位于最终证据 prepared/portable，execution_authorized=false。
修后 controlled_runner.py SHA256：

`7284f721fa5c9ba1e8e03be31df6b6a1e4b87b5234cb21130c33c07d07bb831f`

其余改动源 SHA256：

- test_followup.py：7c7e123b82327916b31ee763fd255beef6d49ae0e3c6a114ec78c0f68af598e9
- prepare_followup.py：360aa568302a1b5be6e60583a20c373ee85a1c566f80b389ecc52ba5eba5242c
- deliver_followup.py：6d915242ad67e409687bb7ada95b79da50debefc0b16a728b1aa22f9216e80ea

实际本机工具：

- Python：E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe
- Yosys：D:/Gowin/oss-cad-suite/bin/yosys.exe，0.69+75，f0b945f63-dirty
- Icarus：D:/Gowin/oss-cad-suite/bin/iverilog.exe，14.0 devel，s20260301-474-g5591c2dde-dirty
- VVP：D:/Gowin/oss-cad-suite/bin/vvp.exe，同一 14.0 runtime

配置包含 621 份实际工具/依赖文件 SHA 与输入身份；原版本/help 输出及退出码在
prepared 中。不以此声称工具在 M2 机器上相同。仅只读版本/help 查询，没有 HDL
输入或执行 lower/compile/VVP/Gowin。默认锁闭预检退出 0、steps=[]、授权 false、
ONE_SHOT_ATTEMPT.json 不存在；未消耗 A/B 唯一执行机会。

A 计划 SHA：dc05bc68552b81e782db2ad0a7edf3c2e8f1278cb89728316dc7c4c3a63277e5。
B 计划 SHA：288eff5d6d0249997adf7dd52a487d37b8d31f624695c332f77ba75bbe9ceee1。
二者沿用已复核计划，没有修改原取消点、Release 节奏或 B 复位尾段。

## 复现及交接

在仓库根目录，用上述 Python 路径替代 python；输出目录必须全新、拒覆盖：

```powershell
python -I -S -B -X utf8 code/software/audio_math_acceptance_candidate/t060_minclosure_20261011/deliver_followup.py qualify-budget-tail --output code/output/m3_c_budget_tail_review_new --suite D:/Gowin/oss-cad-suite
```

此命令只做上述三项新增合成时钟测试、身份包及锁闭预检。移机不能直接照搬本配置；
不得为了复核执行原 run_followup 全套、A/B 或附加 EDA。

新封存保留修后源身份、20 份软件/TB 依赖、原始差异、版本输出、新 config、
测试日志和退出码；转发 ZIP 另外包含精确提交/远端确认及九门禁原日志。
仓库强制九门禁中的短 T007/T019 与本任务新 A/B 捕获分开报告，不算补采许可。
请 M2 只复核本次新增变化，再决定是否给上述精确 config 的唯一 A/B 许可。
无安装、串口、接线、下载或烧录；不签真实资源、整机 STA 或完整 T060/T061。
