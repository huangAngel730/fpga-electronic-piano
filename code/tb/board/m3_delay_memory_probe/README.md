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

## 2026-10-04 实际结果和未通过条件

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
runner 已提供显式 global_freq 的后续复现入口，该修正尚未重新综合；
遵守“各一次”边界，须 M2/用户同意后才追加三档修正运行。

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
I 工具可提交复核，容量合同暂未收口；G/H 不受此条件问题阻塞。
不改共享状态/编号表，由 M2 统一登记；待用户转发，尚未送达。
