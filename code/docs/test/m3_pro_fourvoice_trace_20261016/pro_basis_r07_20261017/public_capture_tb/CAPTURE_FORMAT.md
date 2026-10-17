# R7-A V1 实际输出接口

`CAPTURE_SCHEMA.json`定义`PUBLIC_ROWS.jsonl`每行：schema、capture_id、origin、source、fields、extensions、missing_reasons、events。`fields`为未经扩列的M2裸61键；原行号/time_ps/SHA/epoch关联在source，TX新增资格/双clip/错误在extensions。缺23项真实语义/出口时fields为null且missing_reasons逐项给原因；不补0。C桥应读取本版本外层，再取fields/extension，不能把外层直接喂旧61键schema。

原件由两层构成：

- `RAW_CAPTURE.jsonl`：`M3_R7A_RAW_CORE_ROW_V1`，每个实际obs_core_clk posedge PRE_NBA一行；source_line从1、cycle从0连续，time_ps来自实际$realtime。ports恰含38个obs口及i2s_bclk/i2s_lrck/i2s_din/pa_en/uart_tx五个引脚，均为固定宽度二进制字符串，X/Z原样留存。finish直接取TB停止输入；raw epoch为null，原因BIND_FROM_INDEPENDENT_RESET_EDGES，不从FRAME猜epoch。
- `RESET_EDGES.jsonl`：`M3_R7A_RESET_SNAPSHOT_V1`，edge_seq从1；时间0的INITIAL及此后外部sys_rst_n、公开obs_rst_n、obs_pll_locked变化逐次记录原binary值。独立于逐core行，不用逐行reset反向造边沿。软件以真实本地reset进入边界绑定epoch；同time_ps若存在不同epoch的可行采样前缀，保留epoch null并标PENDING_RESET_PHASE，禁止选一个猜测。
- `END.json`：单一`M3_R7A_END_V1`，记录capture_id、plan_stop_id、实际finish_cycle/time_ps、row_count、PLANNED_WINDOW_END、公开采集的结束原因。另有stdout唯一`MONITOR_END capture_id=... cycle=... time_ps=... rows=... reason=PLANNED_WINDOW_END`。外部工具exit0/timeout/cleanup收据由M2执行器后置交付；TB不能自报通过。
- `PUBLIC_ROWS.jsonl`由本包assemble.py机械转换。source.raw_sha256/reset_edges_sha256和source.line绑定原件；source.cycle/epoch与fields一致。events仅是同沿实际位产生的FRAME_F、ACCEPT_A、RESULT_TRANSFER、COMMIT、TX_ADOPT、FINISH，不是独立期望日历。即使TX metadata无效，实际采纳行也保留；req_id_valid不为已知1时tx_req_id=null，原32bit留extensions.raw_tx_req_id_bits。

软件自检输入固定标SYNTHETIC_SCHEMA_FIXTURE；未来TB原件也只能标HDL_PUBLIC_CAPTURE_UNVERIFIED，不能自行approved/authenticated或称真实Pro验证。A不生成FRAME_PLAN，不核私有DSP/声音黄金、四声语义、期限或串行解码；这些由既定R6-5/6及M1继续。工具结构检查通过不能掩盖missing23/M1语义、reset初相位或首轮真实执行准入。

整机复用R6-2 driver原文件，驱动独立40MHz输入时基上的外部sys_rst_n/midi_rx；观测使用真实obs_core_clk，两个时基不直接当同一拍号。driver.event_ready接悬空诊断wire，绝不驱动obs_event_ready。ready.drv无法制造整机背压，driver_aux_not_authoritative.log不能当真实接受；真实A仅来自公开req_valid&&req_ready。冻结计划/driver SHA和实际两个时钟/边沿原件必须随首次M2准入。

HDL源码未编译/未仿真。首次运行必须M2固source装配、时钟模型、独占路径和明确STOP_DRIVER_CYCLE/EXPECTED_FINISH_CORE_CYCLE/MAX_CORE_SAMPLES/MAX_SIM_TIME_PS，再签工具与预算。不等同本包软件合成组许可，不沿用旧R06消费。

停止顺序为driver计划拍到达→driver下降沿→实际core下降沿置finish_requested→下一core上升沿记录finish。结束拍必须按此相位重新冻结；不在独立driver边沿直接置位，避免与PRE_NBA采样竞争。转换器兼容ModelSim stdout的`# MONITOR_END`前缀，所有出现MONITOR_END的行均计数，额外畸形标记也拒绝。

新软件组仅依赖Python标准库；selftest内的schema断言覆盖本冻结schema所用关键字，并拒绝未知关键字，不宣称通用JSON Schema验证器。实际命令/退出码另存；进程内负例的拒绝码不冒充独立进程退出码。
