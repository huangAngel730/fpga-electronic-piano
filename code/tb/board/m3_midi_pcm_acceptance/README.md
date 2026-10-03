# F真实MIDI输入到PCM联合验收

仅候选L2/L3，M3测试辅助。不会修改正式音频/公共包/顶层/工程/约束/可视化/STAT，
不插入T028，不定义Program音色政策，不做Gowin/PnR/烧录或实物音效结论。

## 入口

从仓库根运行（每次使用新的output目录，旧证据不可覆盖）：

```powershell
python -X utf8 code/scripts/run_m3_midi_pcm_acceptance.py --output code/output/m3_F_review
.\code\scripts\check_repo.ps1
```

默认ModelSim路径`E:/FPGA/Bpan/modelsim/modelsim1/win64`，可用`--modelsim-bin`或
MODELSIM_BIN覆盖；不要求Icarus降低分配器。ModelSim实际编译生产
voice_allocator_4.sv，不用手工槽位生成器。
`--check-capture <path>`只重算原证据，不声称新RTL运行；`--positive-only`只供开发诊断，
不是完整验收。Python依赖仅标准库。原执行Python3.12.4、ModelSim SE-64 2020.4。

## 链路与来源

两路50MHz/31250/8N1真实midi_input（来源1/9，空闲高，1600clk/bit），进入
32项performance_event_fifo；只在其输出valid&&ready时记录accepted控制更新。
只读M2候选router/bank、真实allocator/sustain/V1 DDS与PitchMod流水，连接生产
polyphonic_audio_core、Q15增益、四路混音及PCM提交/帧缓冲。
48kHz合法请求节奏为1041/1042/1042拍循环，记录frame id，不作模拟输出延迟声明。

ADSR仅调用既有run_adsr_pipeline_isolated.patch_copies生成经过批准的output副本。
中心/Mod0阶段以同一生成器的旧V1/CC64 bank为参考，接受同一公共FIFO握手事件、
同一采样请求；参考只改模块名。没有新ADSR算法或新数学网格。

依赖身份由36c7197任务单的SHA清单固定。parser明确使用de68038优化版SHA
`834887a990a4866d54669c5f18588a0b799aa4c08ccb27c91a2f9e5609f331c6`。
三小ROM在本机与M2清单仅LF/CRLF原始字节不同，入口只允许可证明的换行差异；
原始expected/actual SHA仍分别记录，绝不把raw SHA称相同，也不覆盖任何原文件。
其余冻结依赖变化直接拒收；编译的附加生产模块按3ad0650 Git原始字节核对。
全部原件、生成版、include、工具版本、实际命令、退出码、日志与capture SHA封存，
运行前后输入身份再次比较。

## 自检与独立参考

- UART正常消息：四声部/不同来源通道、第五抢占/松旧键隔离、Velocity0、Release重触发、
  CC64持键/已松键/松踏板、延音暂存代次被抢占、持键及尾音Pitch/CC1、Program127运输。
- 最末UART数据字节按物理位时序在帧边缘完成；记录字节和实际接受时刻，采样快照按
  真实owner仲裁，不人为强制同拍ready，不force parser状态。
- 显式测试夹具暂停下游，用第二FIFO输入填满32项，恢复后断言满pop/push及payload
  稳定；再把一个控制放到实际PCM owner忙时。34条synthetic输入与真实DIN分开统计，
  不是承诺无限输入零溢出，也不把fixture输入冒称真实键盘字节。
- UART半帧/残缺消息、FCW实际busy且age2、PCM pending复位与恢复；异步清音与同步
  FIFO清空断言。复位取消1个已请求帧，未将其计入成功提交。
- 逐次accepted事件的来源/通道控制表配合M1 PitchModVoice独立FCW参考；NoteOn重置
  每槽LFO，冻结来源/通道/代次/基础FCW逐项核对。note_pitch基值按半音公式独立生成
  再按原定整数八度移位核对，不用DUT新值作期望FCW。
- DDS相位由独立调整FCW累计，原V1 ROM逐样本核对；table选择及ADSR包络取实际bank
  观测值，不冒称第二份完整音色/ADSR模型。按signed16×unsigned Q15的floor>>15、
  PCM24左移8、四槽32位累加/24位饱和独立整数核对，提交ID及实际play_left/right一致。
- 空/截断/畸形/缺END/假END/数量缺失/未知值/场景缺失必须拒收；缺源/ROM preflight
  在scratch副本验证，绝不移除或修改生产文件。超时退出124不能算行为反例通过。

## 三种真实可编译反例

只修改output副本，唯一锚点变化时停止；不修改原bank或算法。

1. DDS错误使用base：RTL可运行到END，但独立FCW/DDS参考明确拒收，不能仅看RTL PASS。
2. PCM结果ID异或1：RTL断言`PCM frame tag mismatch`拒收，不以等待超时替代。
3. control tap移除router_ready门控：RTL断言`control updated before public FIFO acceptance`
   拒收，不将event_valid当accepted事件。

ModelSim使用-onfinish stop并显式检查test_passed，避免$fatal返回0造成假绿。
默认必须正向和三个反例均通过对应验收才返回0；compile失败不能计行为反例通过。

## 2026-10-03实际结果

正向、三个反例及12项capture/preflight负例通过；最新正式运行结果以交接包
evidence.json为准。F早期开发失败保留在各自output目录，不算最终PASS。
最终正向2486提交，2484正常PCM帧/2显式fixture阶段帧，2301非零PCM、3734非零
控制声部结果、697中心bank对照、103真实UART字节/34真实输入事件、34夹具事件；
满pop/push1次、控制反压59拍、帧边缘实际接受6次，8种来源通道身份、17必需场景。
正常DIN无溢出/帧错误，正常PCM无欠载；FCW中段复位取消1请求，其余请求逐次提交。
最终入口再次真实复跑，证据为`code/output/m3_F_release_final_20261003/`；
十个损坏capture还实际调用公开CLI，各退出1；缺源/ROM两例由同一preflight明确拒收。
本测试不证明键盘已变调/颤音、不证明最新音画Setup/Hold/Recovery收敛；仍由M2
复核、登记编号及进行最新正式接入/STA。A/B/C/D既有签收不重复。
