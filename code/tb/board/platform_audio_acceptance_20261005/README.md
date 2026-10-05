# M2平台捕获准备：默认40MHz

用户已于2026-10-05选择后续40MHz系统版本；音频逻辑采样48kHz、视频25/125MHz、MIDI31250/UART115200目标保持。60K50MHz是保留的演示/回退，不自动迁移或覆盖。

本目录仅新增隔离观测和报告测试；不改M3 E/F/G/H/I/L或新优化副本，不执行PnR，不签收尚未收到原件的I/L。运行入口在code/scripts，新增内容不改变正式外部接口。

## 捕获入口与界限

```powershell
python -B -X utf8 code/scripts/run_platform_audio_capture.py --output code/output/<new_capture_directory>
python -B -X utf8 code/tb/board/platform_audio_acceptance_20261005/test_observation.py
python -B -X utf8 code/tb/board/platform_audio_acceptance_20261005/test_platform_gate.py
```

首个命令默认138K C40时序profile，但仿真DUT仅H40原件中的实际UART→公共FIFO→音频银行/FCW/DDS/ADSR/PCM子系统。时钟由TB产生25ns周期，不测试PLL、TMDS、屏幕或模拟音频；不把H的STA失败改成通过。profile065只是未来时钟/参数选择，不代表使用L实物约束。

复用已签收F的17场景与独立FCW/DDS/Q15 PCM检查，实际UART每bit1280clk、每秒1kHz间隔40000clk、48kHz帧833/833/834clk。原F仅这些频率相关量和edge-alignment等待数适配；allocator用generic lower，include转basename，原reference bank仅rename与已签6/4等待计数调整，SHA严格核对。仅模型比较包络输入不能叫独立ADSR数学验收，后者保留M1职责。

## 只读观察合同v1

audio_observation.jsonl使用ASCII JSON lines；第一行为META(schema1、sys_hz40000000、sample_hz48000、physical_PLL_test=false、analog_test=false)，最后为END和真实计数。唯一样本身份为(epoch,request_id)，reset合法取消尚未提交请求，不能伪称漏样本；END前需完全排空。

- RESET：epoch、cycle；epoch仅在真实复位进入时加1。
- REQUEST：epoch、cycle、request_id；对应实际sample_req。
- STATE：每声部在lane_tick或slot NoteOn/Off时采样。含身份source/channel/note/generation、10bitvelocity、note_on/off/tick、原ADSR内部state和公开state、level/start/peak/sustain Q16、33bit带符号step原补码、elapsed、DDS phase/fcw/table与envelope。**全部是posedge进入NBA之前的原状态**，不能当成已完成本拍运算；按周期/事件排序解释。
- COMMIT：epoch、cycle、request_id、左右signedPCM24，实际提交值。
- END：REQUEST/COMMIT/STATE/RESET累计数。

原F midi_pcm.capture同时保留UART U、parser握手P、公共FIFO接受E、银行请求Q/控制S/FCW F/DDS D/银行返回H/PCM M/复位R/场景T。M1应合用两份capture，不用STATE里的观测值当黄金答案。

独立运输审核检查请求/提交身份、reset、漏/重复、宽度、结束计数，再将所有JSON COMMIT与原F M逐条对照。已用实际捕获的空/截断、错profile、重复请求/提交、错req_id、PCM1LSB、错velocity宽度、未知Q16、错END计数证明拒收。

## 平台配置与报告门禁

platform_profiles.py明确60K B50、138K C50、C40_hold055、C40_hold065；用户方向为40MHz，hold065只预声明交接要求，未取得I/L原件仍不能称正式冻结。完整输入当前56文件/47 GPRJ项；新增功能后必须更新来源清单和资源合同，不能沿用冻结资源判断。

check_platform_timing.py按真实时钟type/master/object/waveform、引脚表头、Bank/电压/差分对、有效SDC、7组CDC后级14路径/两类存活payload、完整TNS/端点、Setup/Hold/Recovery/Removal/pulse、actualLOC、PnR选项和原源码SHA/PLL输出/参数传播/构建凭证审核。负零端点不被舍入抹掉；不设置clock_groups、multi-cycle或降低guard。065诊断report的具体拼写仍需M3原件到件核对，不匹配则拒收而非静默放宽。

本轮不包含Gowin综合/PnR、正式顶层迁移、板测或新码流交付。M2接到最终候选后统一增量融合/STA，M1独立数学验收与M3板型电气核对仍待。
