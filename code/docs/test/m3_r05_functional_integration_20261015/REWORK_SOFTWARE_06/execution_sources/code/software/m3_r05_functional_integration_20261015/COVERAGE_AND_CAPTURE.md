# R05增量覆盖与公开capture合同

## 冻结TB实际覆盖（源SHA见README，不以软件测试扩大）

| 项 | 原TB66行 | 判定边界 |
|---|---|---|
| MIDI输入接受 |14/34/38–46/51接受计数与字节注入|间接；没有逐事件数据核对|
| 一／二音 |36/41 active下界和nonzero提交数|未证明每音独立频率|
| 四音 |48 active精确4和非零提交数|状态间接，不是4峰/4路逐样本证据|
| 第五音 |53–55 接受增加／active仍4／帧与提交继续|具体退休/抢占身份未公开|
| PCM |16–18 commit／nonzero|无左右PCM/ID/clip逐沿|
| 串行 |22/41 serial_ones|活动，不是左右/LSBJ相位解码|
| 期限 |55 max_cycles<834|DUT自报，独立逐请求deadline UNKNOWN|
| 复位 |31/61 静音／active和buffered左右清零|无逐寿命排空／在途取消账本|

R05四处四态拒收只覆盖被检active/max/reset值，不等于整个PCM/握手/串行无X。
clock_plan_sim的40MHz源独立于50MHz参考输入，DVI为stub，不签PLL/HDMI真实行为。

## 新隔离候选（未编译）

`m3_r05_observed_frame_candidate.sv` 外接40MHz/同步释放reset/原64bit事件/效果配置，
实例化原 `m2_fourvoice_timbre_delay_frame_core` 与原 `i2s_tx`（659706977、PCM24、DAC16）。
新observer只看公开port，不读取DUT内部寄存器、不修改旧R05 TB或board。它没有MIDI parser，
不能宣称已补原MIDI输入链；不因为接线文本已生成就称L2。

`M3_R05_PUBLIC_PRE_NBA_V1` JSONL 每sys_clk正沿pre-NBA一行；HEADER后完整连续TICK，
异步reset每个下降沿另记RESET（epoch加1、当时cycle、整数time_ns），最后唯一END。
TICK：cycle/epoch/rst_n/frame_tick/request_accept/request_id/commit/committed_id/left/right/clipped/pending/
play_left/play_right/clip_count/underflow/bclk/ws/din/first_valid。所有bit严格整数0或1、PCM24 signed范围、
ID/计数32bit无符号；first_valid固定null，因为原公开frame_core并未导出它。
frame_tick是源码取消围栏，不另编造取消握手。合法已提交held播放可重复，不算新提交；
clip计数按pre-NBA下一沿核单次commit增量。缺下一真实frame的尾段请求deadline保留UNKNOWN，
不由833/834统计或DUT max补填。

## A/C接入关系

A原R05只有汇总，不满足此合同，也不满足C的独立公开串行capture合同。当前没有真实A capture可交C。
C已完成新模块诊断生产者→原buffer/tx仿真，独立观察协议/数字时间，但不是A替身。
未来实际采集必须先冻结新增候选源与工具、输出、许可次数，再明确字段/采样相位映射；
不能单纯把合成数据文件名改成“真实”或把缺少ID/clip/首次valid填0求通过。

## 软件预算与真实预算分层

SOFTWARE_02合成ledger只有3frame间隔833/833/834、3接受/2提交/1取消，仅L1。
原R05无真实逐帧CSV，因此该CSV未生成，frame_cycles/max_processing_cycles/underrun不得从END凑造。
新账本只针对有真实下一帧的请求独立比较commit/取消，模拟输入到模拟起音≤10ms仍待同一时基仪器实测。
