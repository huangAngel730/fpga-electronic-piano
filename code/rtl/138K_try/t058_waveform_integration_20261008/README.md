# T058 新精确集成副本（M2）

此目录只保存新overlay及源身份，原L/原T056/生产/M3模块只读。不要在原L运行新工程。
`prepare_138k_waveform_integration.py`固定原ZIP56inputs+3已签模块=59inputs，
GPRJ原47排序+3module=50entries，器件GW5AST-LV138PG484AC1/I0/C、原50MHz外参
PLL40/25/125MHz、原CST/7ROM原字节不变。两overlay只改内部观察和视频合成。

波形从sender真实装载frame_tick采buffered左右signed24，no ready，新observer32queue
+mailbox。M3左波形固定512x256区域，仍按2048实际帧/4minmax，N到N+2输出。原scene/
HS/VS/DE增加3级采样，与原DVI寄存采预NBA waveform同步，新外部top端口保持原接口。

overlay SDC保留所有旧约束，增加观察80bitpacket稳定maxdelay10ns及report（综合仅
保留被使用的位数按实际报告，不假称右声道/全部80bit都保留），req/ack/source_up只切
首同步段、二段setup/hold完整报告；无clockgroup或multicycle放宽。全部旧时序/CDC/
引脚/LOC/复位/资源检查复用，profile只显式增加新3secondstages/1bus/实际RAM层级。
新增不含DSP，原46DSP保持；原audio20BSRAM+wave3+observer若推断单RAM按层级证明，
不能硬写23就忽略report未知。厂商VG可能加密，RAM检查从原hierarchyXML读取。

准备新副本：

```powershell
python -B -X utf8 code/scripts/prepare_138k_waveform_integration.py --output code/build/138k_waveform/<NEW>
```

只读复验同入口加--check。拒绝旧目录，不覆盖/删除原结果。新build输出放独立
code/build/138k_waveform/runs/<NEW>/project，prepare再次重建、原SHA验证，不直接复用
被仿真改动的staging。完整runall最长1800s、一次、不自动重试、不program。

仿真分范围，源/工具/适配不同清楚区分，不将nominalclock写成vendorPLL结果：
- 3short实际新旧top MIDI/4voice/CC64/PCM/BCLK/WS/DIN/STAT逐拍等价，含pixel暂停/
  queue满和显式producerfault、reset恢复；640真实audioframe，暖机video，非长全帧。
- 同一exact display_probe长扫描，封存真实5849A及原833/834间隔、oldscene+wave完整
  全active/blank行、独立signed24窗口oracle+N+3合成HS/VS/DE；不是同时liveaudio。
- 原vendorPLL primitive新top3startup验证上电高reset/earlyrelease/失LOCK停core恢复；
  加密DVI仿真stub不验证TMDS电气/屏幕。
- 2newstaging-onlymutants改senderPCM、少一拍HS。compile0/run0到指定assertion后
  独立capturechecker1；是到首次语义错误完成的诊断case，不宣称跑满longframes。

`run_138k_waveform_integration_once.py`要求所有9case实际PASS、exactsource/compiled
staging SHA一致和总elapsed≤1800，错源/缺case/旧output先拒，不启动Gowin。
部分旧module intunsigned/allocator结构和include路径只在simulation副本机械适配，
原Gowin输入与数学保持。长display900s/其余600s、全1800，实际elapsed最终再检查，
操作系统暂停/调度造成elapsed异常也不放行，仅保留原receipt并另行认定不合格。

构建完成还要`check_138k_waveform_integration_build.py <run>`报告全门禁，Setup≥0.5ns
工程门槛、不负Hold/Recovery/Removal/pulse、TNS/violated0、Fmax≥各运行频率、旧LOC/
Bank/pins/无latch、命令参数/设备/SDC全部Active、新payload/二段路径实际报告。
任何失败不升级L5/不发布/不下载，保留真实资源和失败路径。这里不是hardware release。

## 本次结果与已知阻塞

一次run_20261008_exact_waveform在182.251s/exit1停止：GowinSynthesis完成，
新SDC的source payload_hold pattern为空集，TA2003，PnR/STA/Bitstream均未完成。
综合真实Logic19149/Register9046/BSRAM25，audio20+observer2+wave3层级明确；
初版newgate允许observer0/1的预估已不成立，不能用于下一次build的资源放行。
checker原执行字节及当前源保持以复核失败，不改旧source receipt或隐藏该假设。
下一版本必须明确增加RAM2并查真实payload/sync对象，再受控新run；本轮不重跑。
新的物理DSP总量/STA/Fmax未知，旧DSPprimitive类别/数量保持不能当新PnR资源46证明。
整体最高L4，不改现有L5/旧FS，board_release_allowed=false；本源码/范围详看M2报告。
