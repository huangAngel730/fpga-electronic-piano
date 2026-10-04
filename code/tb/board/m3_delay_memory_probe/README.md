# I：原 T028 三深度独立综合容量检查

不改原 `delay_effect.sv` 的异步复位或 RAM，不做 PnR/seed 搜索/码流。
探针所有 PCM/增益/反馈/延迟输入、sample_enable、输出均为真实 top 端口，
无常零激励。深度仅在 scratch 替换探针参数，不替换算法原件。
目标 GW5AT-LV60PG484AC1/I0，报告必须明确 Device Version B。
逻辑/寄存器/BSRAM 使用值取实际综合 utilization，RAM16/DSP 原语取 usage。
DSP 汇总字段缺失写 unknown，不从加密 netlist 的不可读内容推断为零。

```powershell
python -X utf8 code/scripts/run_m3_delay_memory_probe.py
python -X utf8 code/tb/board/m3_delay_memory_probe/test_report.py
.\code\scripts\check_repo.ps1
```

runner 自动查找已有 gw_sh 或原生 GowinSynthesis，不安装工具。
后者参数来自本机 `-help`；默认目标 50 MHz 同时传 20 ns SDC 和
`-global_freq 50`，报告仍须实际显示 20.000/50.000 才算合同通过。
每个深度一次独立综合，失败/超限/timeout 返回非零，保存全部产物与 SHA，
不自动换浅深度或重复综合。无工具/prepare-only 退出 2，不宣称综合已执行。

## 2026-10-04 初次实际结果和未通过条件（历史保留）

本机存在 GowinSynthesis V1.9.11.03 Education（缺 gw_sh）。原件 SHA：
`3e31669f268d5fa93ec64dc33dbc8f8bb5490d80ecbbb83bb9695a05f703d0bd`。
1024/4096/16384 各已实际综合一次，原生工具均退出 0，报告器件/封装和
B 版一致，未超出表内 Logic/Register/BSRAM 容量。报告与加密 netlist
原样保存于 `code/output/m3_I_actual_20261004/`。

但初次原生执行仅传了 SDC，工具报告仍显示默认 **10 ns/100 MHz**，
并非要求的 20 ns。本轮最终检查器正确拒收，`contract_passed=false`，
不能写 I 合同通过或 50 MHz STA 达标。初始 evidence 的 passed 只代表
工具执行成功，最终验收以 `code/output/m3_I_review_20261004/evidence.json`
的失败关闭结论为准，旧执行 driver/SHA 保留，不伪造新选项已运行。
初次交付时 runner 已提供显式 global_freq 的后续复现入口，但尚未重新综合；
当时遵守“各一次”边界，未获追加授权。后续授权与新结果独立记录如下。

| DEPTH | Logic | Register | BSRAM | RAM16SDP1 | MULTALU27X18 | 非零最大延迟 @48k |
|---|---:|---:|---:|---:|---:|---:|
|1024|740|103|2|64|3|21.3125 ms|
|4096|2397|105|6|256|3|85.3125 ms|
|16384|8978|107|24|1024|3|341.3125 ms|

上表只绑定实际 10 ns 综合设置，不外推最终整机总量/布局结果。
delay=0 对应整 DEPTH 圈历史（21.333/85.333/341.333 ms），非旁路；
500 ms 未实现。综合估计 Fmax 不是 PnR/STA，不以它作最终时序证明。

```powershell
# 只复核已封存的一次运行，不启动综合，不覆写旧结果：
python -X utf8 code/scripts/run_m3_delay_memory_probe.py --review-existing code/output/m3_I_actual_20261004 --output code/output/new_I_review
```

10 项检查器自检覆盖正确资源、unknown、10ns 错时钟、缺时钟、错误器件/
版本、缺 BSRAM、超容量、畸形数、重复资源和缺 RAM16。真实报告复核
非零退出，证明没有把时钟条件错的报告当 PASS。
初次交付为 I 工具可提交复核、容量合同暂未收口；G/H 不受此条件问题阻塞。
不改共享状态/编号表，由 M2 统一登记；待用户转发，尚未送达。

## M2批准的有界50MHz修正入口

固定原效果器和本probe：除scratch中1024/4096/16384参数外，不改算法、
复位、RAM结构或端口。每档最多追加一次，先1024核对实际报告，再允许
4096和16384；任一档失败/时钟或器件不符立即停止，不自动试其他选项。
必须显式指定已有原生GowinSynthesis.exe，不走gw_sh/Tcl频率默认值。

```powershell
python -X utf8 code/scripts/run_m3_delay_memory_probe.py --native-clock-correction --tool D:/program/gaoyunFPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/GowinSynthesis.exe --output code/output/m3_I_50MHz_correction_20261004
```

上述命令是本批实际执行入口，不应再次执行已用完的三档额度；复核报告
用`--review-existing`，不启动工具。原生每档命令均含`-global_freq 50`和
`-sdc <probe.sdc>`（20.000ns）。每档结束写checkpoint evidence，记录
命令、退出码、实际clock row、器件B版、输入/报告SHA及独立归档执行driver。

I身份校验仅限冻结DUT/probe，不再绑定与本容量检查无关的生产音色/G/H
输入；M2后续生产接入变更不应使I拒绝开工，DUT/probe改变仍必须拒收。
报告检查器12项自检包含实际时钟拒收、资源异常、unknown以及native工具/
首档失败停止检查；这些是检查器测试，不冒充RTL仿真或容量实测。

旧交付ZIP的清单仅删不存在的`manifest.json`条目，独立更正版为
`code/output/M3_G_H_manifest_final_corrected_20261004.json`；其余104个载荷
SHA与原ZIP逐项匹配，原ZIP/G/H证据不重打包、不重测。

### 2026-10-04批准修正实际结果（独立L4，待M2复核）

1024报告先实际检查为20.000ns/50.000MHz后才启动4096，再启动16384。
三档各恰好一次追加综合，Gowin V1.9.11.03 Education、目标完整料号和
B版均匹配；三个native exit0，三个报告contract_passed=true，总runner
exit0。新产物另存`code/output/m3_I_50MHz_correction_20261004/`，
旧100MHz报告/driver及原ZIP保留，未覆盖或替换。

| DEPTH | 实际period/frequency | Logic | Register | BSRAM | RAM16SDP1 | MULTALU27X18 | DSP汇总 |
|---|---|---:|---:|---:|---:|---:|---|
|1024|20.000ns / 50.000MHz|740|103|2|64|3|unknown|
|4096|20.000ns / 50.000MHz|2397|105|6|256|3|unknown|
|16384|20.000ns / 50.000MHz|8978|107|24|1024|3|unknown|

上述资源与旧100MHz结果数值相同，但本表只绑定新报告，不借旧结果
代替实际20ns执行；每档Logic/Register/BSRAM均未超过对应报告容量。
DSP原语单位数不是实际总DSP块数；RAM16容量报告未提供，保留unknown。

原效果器SHA仍为`3e31669f268d5fa93ec64dc33dbc8f8bb5490d80ecbbb83bb9695a05f703d0bd`；
未改probe模板SHA为`ece4917989b0b299423432142ca5dff53e5146089ea531a92d806078da837606`。
实际执行runner SHA为`1d024f4571defd2fda934f3f666067585086fb41421e211ba77b334106442a14`，
driver_executed.py原字节归档，每档生成源码/SDC/选项/报告SHA见evidence.json。

报告12/12检查器自检PASS；真实缺native工具入口exit2且未综合；新报告
`--review-existing`复核exit0，未启动新综合。仓库九项门禁PASS（160份
Python语法、原T007/T019），日志`code/output/m3_I_50MHz_gate_20261004.log`。
清单更正版SHA：`707f35910157555add801a5bd1696bb1b88061beaad751f5f8795aa8a9995764`。

本批仅I容量检查的独立L4，G/H已签收不重跑；无PnR、正式STA、正式工程
接入或上板，不声明参数平滑/无爆音/500ms。状态与V编号仍由M2收口，
不写任务排除的共享表；通知待用户转发，尚未送达。
