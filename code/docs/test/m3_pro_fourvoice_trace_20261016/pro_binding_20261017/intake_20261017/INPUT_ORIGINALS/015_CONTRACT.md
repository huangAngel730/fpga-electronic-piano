# Pro 被动帧监视器接入合同（候选，待 M2 固定映射）

本文件只定义隔离 TB 观察合同；不改变正式公共接口。实现是 `code/tb/board/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017/pro_frame_monitor.sv`。自检生产者 `tb_pro_frame_monitor.sv` 是人工端口刺激，不是 Pro DUT。

## 时基与连接

所有端口在调用方的 40 MHz `posedge clk`、NBA 更新前采样。调用方应从真实公开端口连线，或由 M2 提供不影响 DUT 的只读观察出口；不得用 DUT 内部黄金状态反填期望。初始必须观察到至少一个 `rst_n=0` 沿。监视器内部 cycle 从1递增，epoch 每次进入复位递增，统计跨 epoch 保留。输入无 epoch 字段，epoch 是该采样时基上的观测代际。

| 端口 | 候选语义与接入要求 |
| --- | --- |
| `clk/rst_n` | 40 MHz 同一观测域、低有效复位。真实 Pro 时钟和复位同步规则由 M2 固定。 |
| `frame_tick` | 真实音频帧脉冲；复位间隔内相邻脉冲833或834拍。相位容差为 `abs(3*elapsed-2500*intervals)<=3`，即最多一拍；它检查本观测时基的平均比例，不测晶振物理频率。 |
| `req_valid/req_ready/req_id/req_payload` | 帧级事务接受为 valid&&ready。ID32，payload64 为冻结的不透明字段，不假定其编码。一个未清理事务在途；背压期间 valid、ID、payload 必须保持。取消优先于当沿握手。 |
| `lane_tick/lane/lane_req_id` | 每事务四个互异 lane0..3，归属于同一帧事务 ID；每沿最多一个 lane。此处不等同 MIDI voice slot 或 note generation，M2 须确认帧 ID 到每 lane 的公开映射。 |
| `result_valid/result_ready/result_id/left/right/clipped` | 返回 ID 和有符号 PCM24×2、clip1。首次 valid 时就核 ID 和四 lane，不依赖 ready；背压保持完整81位元组。只允许一次返回握手。 |
| `commit/commit_id/commit_left/commit_right/commit_clipped` | 实际提交，须与已握手返回的整个元组相同；可与返回握手同沿，不能与新请求重叠。这里只核传递身份，不核 PCM 算法。 |
| `cancel` | 清除在途、请求/返回保持状态；取消当沿不得提交。清理不能掩盖已到截止的事务。 |
| `pll_locked/audio_stable/pa_en` | PA高有效；复位期间必须0。运行时 pa_en=1 要求 lock且stable。稳定后允许持续静音，不规定开启延迟，也不代写 M2 控制器。 |
| `bclk/ws/din` | 同沿保留实际串行引脚原始值；此监视器没有串行解码器，不据此签 PT8211/LSBJ 正确。后续只读复用已有 D 解码器。 |
| `finish` | 调用方声明此观察窗结束；不得有在途/背压未收尾，accept=commit+cancel，之后不得再有采样沿。只在非复位域有效。 |

请求接受到提交/清理必须严格小于833拍，并且不能越过下一真实帧。接受+832拍取消/复位合法；接受+833拍取消/复位拒收。这里是候选服务预算，不是对缺失 Pro DUT 的性能测量。每 epoch 的 ID 可从ffffffff回绕到0，但不得重复；复位后允许复用。`MAX_IDS` 是显式有界历史容量，默认4096，用尽拒收，不能拿它运行无限长窗。

## 原始输出与拒收

必须指定 `+TRACE=<独占新文件>`。CSV 每个采样沿一行，共29列：cycle、epoch、复位/PLL/稳定/PA、帧、取消、请求、lane、返回、提交和串行引脚。请求ID以8位十六进制、payload以16位十六进制，PCM按有符号十进制。未知值保留为仿真器输出的 x/z；控制/被使用数据的未知会触发拒收。

故障输出 `FIRST_REJECT <代码> cycle=<整数> epoch=<整数> request=<ID>`，然后 `$fatal(1)`。第二轮起 CSV 包含故障沿，周期连续，最后周期等于首拒收周期。不要将故障 CSV 当成完整成功轨迹。最终统计在 stdout 的 MONITOR_END 行；具体 argv、进程退出码、双流、版本/源码/工具 SHA 见原始运行收据。

## 现阶段不覆盖与 M2 最小到件

不覆盖 MIDI allocator/Release/抢占规则、wave/env/phase/效果数学、PCM24→PCM16 舍入、串行解码、模拟输入→输出延迟、PLL 模拟行为、失锁异步电气响应、正式 STA 或板级功放电平。正例允许稳定后保持静音，合法主动开启 PA 未单列正例。固定包络/左右数值是传输夹具，不是 M1 黄金。

M2 下一步需要提供：精确 source/ROM 文件本体与 SHA 清单、Pro 完整目标及 top、40 MHz/48 kHz 合同、上述每个端口到真实公开输出的映射、帧级和 lane级ID区分、cancel与reset的同沿优先级、lane掩码含义、PCM/clip提交时刻、PA的stable来源，以及有界 TB 的许可与新日志目录。未到件不得伪造实例化映射或声称真实 Pro PASS。本包不启动 ModelSim/Gowin/设备。
