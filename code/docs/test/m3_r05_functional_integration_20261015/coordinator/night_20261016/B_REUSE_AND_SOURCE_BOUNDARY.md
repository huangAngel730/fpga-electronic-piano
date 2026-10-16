# B复用与A/B同源边界

2026-10-16夜间总控及只读子智能体核验；本夜新增B物理调用0。
原B ZIP SHA256：59f40000f25bccc492199e4a0f6e843e4a7ccf68ddaeab5823c756b888d44ce3。
原B RUN_RECEIPT SHA256：bee129d8c7ebacf82764d7cf52904e5cb24e2a0728d7a54ed48b5670d75fa75c。
原物理工具调用1次、344.813秒、退出0；首轮通过，不重跑。

## 同源关系

A原R05的84项物理输入映射为69项原字节相同、15项ROM/include路径逆恢复相同，另5项仿真/准备输入。B逆迁移后83/84与原物理输入相同，唯一SDC变化为原24106字节完整保留后追加10条report_timing。
原A/B算法RTL、9个ROM、CST及原顶层身份链成立。原顶层SHA为f2a8f30fef8ad2da26d1d3b80793b727f45806b6d5c78f2a071fb383322639be。
本夜A在新隔离副本增加观察器和公开端口接线，必须另列diff/新SHA，不能直接称该观察候选已获B物理签收。

共同编译单元65个。B另有真实DVI_TX_Top.v和TMDS_PLL_800_600_60.v；A使用clock_plan_sim.v、dvi_sim_stub.v、vendor_GSR_pROM.v和TB。A的时钟模型固定产生时钟、1000ns置lock，DVI stub常量输出；不能据其功能PASS签真实PLL/TMDS或物理时序。

## 原B报告限定范围

| pair | Setup ns | Hold ns |
|---|---:|---:|
| post_right_ram_address |22.505|0.000|
| voice_lane2_phase_to_rom |22.534|0.000|
| pitch_lane3_total_to_oct |20.908|0.000|
| pitch_lane0_total_to_sub |22.511|0.000|
| event_fifo_to_audio_slot |1.736|2.814|

仅五对端点的双向报告；不覆盖所有lane/位、PCM/I2S全链端点或新观察候选。原name未出现不证明逻辑被优化掉。board_release_allowed=false。

## 原件入口与核验方式

- A：code/docs/test/m3_r05_functional_integration_20261015/RUN_01/INPUT_BINDING.json中的same_version_mapping；原input_binding.py的inspect_archive。
- B：code/output/m3_m2td_endpoint_probe_20261015_r01/PATH_MIGRATION.json的before/after/inverse_identity/changes，原/新SDC及RUN_RECEIPT.json。
- 发布封包：code/docs/test/m3_m2td_audio_endpoint_audit_20261015/successor_R03/delivery_night_r03/B_DIRECTED_STA_CANDIDATE_20261016.zip；518个声明成员的大小/SHA核同，无额外成员。
- CURRENT_RESULT.txt包含旧D失败时点，当前D以已发布REPAIR_REPORT_20261016.txt为准；本夜新D增量另留新回执。

此文为只读同源核对L0，不是新增RTL/EDA运行。原B实际checker终端双流未另存的历史缺口继续保留，不能由此核验补写原始流。完整旧失败/工具版本/命令及双流沿用原B封包；本夜只追加A/C/D必要增量。
