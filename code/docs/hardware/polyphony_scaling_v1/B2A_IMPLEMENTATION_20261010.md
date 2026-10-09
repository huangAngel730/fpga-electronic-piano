# T061 B2a：真实声音后端的独立数学阶段

本阶段接续 B1/9f02adc，仍只写 D043/D044 的 B 五路径。**不是完整 B2 或 T061 收口**。
原冻结 L56 inputs/7ROM、原 T060/B0/B1 证据与八共享文件只读。正式架构/档位由 M2 决定。

## 一个主候选，选择混合而不是声称全部算子已分时

`b2_audio_backend.sv`：每声部保留原 L `adsr_piano_envelope` 和
`pitch_mod_fcw_pipeline`，原件直接只读编译、不改算法。ADSR 私有预备状态、乘法流水、
前一拍 sustain product 以及 LFO 仍逐 sys_clk 真实运行，不将这些存活状态塞进 B1 的
可丢弃 token bank。新 DDS 相位/亮度表状态按 voice 独立保留；一份实际钢琴波表
1024×16、一份 signed33 Q15 gain 乘法和一个 signed32 累加器按 voice 顺序共享。

这是**单一混合主候选的后端**，不是三套 engine，也不是已经证明共享全部 635bit context。
原 B0 全共享日历仅条件假设，不因新后端很快变为实测，也不据此把原 B0 资源表倒填。
保留连续前端的成本较高；当前选择先消除改变 ADSR/Pitch 状态语义的风险，是否用于正式工程由
M2 依据完整候选与资源/STA 决定。没有必要为目标32强行共享所有乘法器。

## 本地接口和时间语义

- 单 clk，测试40MHz；整域低有效异步复位，真实同步释放仍归上层。无新公共包/production port。
- 外部已有分配结果按 N 路向量提供 source4/channel4/generation32、occupied、base FCW32、
  velocity10、signed bend12/modulation12/range5。**不接 MIDI64，不实现分配器或 CC64 扫描。**
- `events_valid/ready` 一次接收各 lane 的 NoteOn/Off 脉冲，只在 IDLE；事件优先于同拍 request。
  request 被反压时调用者须保持，不能把输入脉冲丢失当处理完成。
- `request_valid/ready` 原子锁存 request32、全部 lane 身份/occupied/base；Pitch 原模块在该沿
  采输入 controls，后续 live 变化不能改它。occupied lane 才推进 LFO，未占 lane 使用 base FCW。
- 接收后第8沿统一推进**全部 N** DDS/ADSR，后续保留4拍等待加捕获边界，再逐个渲染。
  Q15 使用 signed16 wave × zero-extended unsigned16 envelope 的 signed33 乘积，算术右移15
  向负无穷取整、保留 signed16 后左移8为 PCM24；未占 lane 明确0，仍处理/记录全部 N。
- 每 lane PCM 符号扩展到 signed32 累加，最后一次饱和到 signed24，左右同值，clip 与此结果绑定。
  N<=32 的输入和不会溢出 signed32；没有每节点先限幅或新增除 N 的归一化。
- `result_valid/ready` 携完整 request/全部 source/channel/generation、PCM/clip/completed-mask；
  输出反压期间保持。`deadline_missed` 只说本后端生成结果的周期>=833，不丢 voice 凑预算。

ROM 是真正同步一读口，读沿更新 `wave_q`。`WAVE_RESPONSE_CYCLES=1/3/32` 是响应适配器
在读后保留数据的实际等待周期，**不是声称厂商 BSRAM 物理延迟有32拍**。只有一个 outstanding，
其计数和 Pitch 7拍存活计数在 cancel 时不清零，隔离态等二者归零且 pitch_valid 消失后再准入。
普通 render 的相邻 lane 间隔为 response+3；全部工作不是每拍一 voice 的理想 II。

## 取消、身份与 B1 的边界

cancel 丢弃 token/output，不回滚已经执行的 LFO、DDS、ADSR；在推进沿同拍 cancel 会抑制该次
推进。整域 reset 才复位全部这些状态。待输出/ROM阶段 cancel 也不发布部分 PCM。
本后端自己不收外部乱序返回，因此这里的完整身份输出是快照保持，**不是另一份 generation
隔离证明**。输入身份变化须由 owner 显式 cancel；接 B1 时要分开 token 原子提交与持久 DSP
副作用，不能直接交换 B1 635bit bank 来回滚真实声音状态。这一接线尚未实现。

## 验证方法与可复现入口

N4先进行长程真实仿真，然后独立整数复算全部公开 E/C/A/L/O/X/R：
只读调用 T060 的 `PianoDDS`/`Envelope`/`pitch_mod`/`voice_pcm`，来自接受的输入/事件计算
FCW/LFO/phase/table/envelope/wave/gain/PCM，不取 DUT wave/envelope/FCW 当 expected。
这不是把原 capture 输出拿来喂 checker。每个 clock-sensitive Envelope 间隔仅在全寄存器组
固定点成立时跳过安静沿；实际 RTL 的连续流水没有被跳过。

N4 TB 还只读例化原冻结 DDS/Pitch/gain，按公开输出比对；ADSR/Pitch 本身是复用原 RTL，
所以“新实现的 ADSR/Pitch 已等价”不是本阶段的独立结论，独立 Python 则核其真实数值。
N4通过才运行 N8/16/32，同一源码链，更多 voice 的独立整数 oracle 不靠两个同改实例。
比较源是冻结 **L** 的 DDS/ADSR/Pitch/ROM/gain 数学；事件源是新增 lane-level 测试，不是
原 MIDI router/capture2 的端到端事件时间重放，不能称完整冻结 L 整机等价。

普通连续 request 严格间隔833拍；事件插入/取消/reset单独列出，不冒称本 TB 是正式833/834
I2S采样器或真实48k输出实测。N4长例含10220个主体结果，覆盖Attack/Decay/Sustain/Release/IDLE、
0/480/960/1440亮度窗、pending换表、LFO回绕、源/通道完整快照、代次ffffffff→0。
更高N使用96个主体结果，是较短数学/容量规模回归，不宣称各N均做同长Release全生命周期。
慢N32响应32故意使完整后端超833，仍必须算全32并如实标超期。
两个可编译行为变异：gain负数除法朝零代替floor、漏最后voice；由指定断言拒收。
九种少量实质 capture 反例由实际 checker CLI 非零且指定语义拒收；六个边界单测。

原stdout保留Icarus14的最终 `$finish` 工具提示。解析器只允许**真实END之后、最后一行、
精确格式的单个该提示**；不跳过任意未知行/额外数据、坏END或缺结果。

```powershell
& E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe -B -X utf8 code/scripts/run_m3_polyphony_scaling_acceptance.py --stage b2a --output code/output/m3_t061_b2a_reproduce_NEW --repo-gates
```

总1800秒/单步900秒、拒旧输出；工具已安装，不自动安装。源码/输入/工具/原命令/exit/elapsed/
stdout/stderr/产物SHA入新receipt。当前执行结论见同阶段DELIVERY，不以预定用例冒实际通过。

## 保留的缺口，下一阶段不是上板

本阶段只交真实数学后端。MIDI事件分配、CC64 256身份扫描及Release/retire ACK、source/channel
控制存储和原子快照前端、同沿事件采样的整条时间适配、B1持久/临时状态接线、端到端服务上界
仍待一个后续独立接入阶段。不能把 lane mask 输入当成已有完整32声部演奏能力。
物理工具 Logic/Register/DSP/BSRAM/SSRAM、40MHz STA、正式顶层/CDC/引脚/48k串行输出/实物未验；
**一次新B候选Gowin综合额度仍保留未用**。原 v3/L 的 L5 不沿用，不安装、不烧录、不接线。
共享表按明确任务禁区未写，阶段记录交 M2 复核后统一登记。
