# T061 B2b：N4 事件到真实 PCM 接入

本轮是同一 B2 混合候选的下一子阶段，非第二套声音引擎。仍只允许 D043/D044 B 五路径。
固定40MHz、最短833拍采样合同、原 signed24 PCM/phase32/Q15数学；无生产接入。
复用 develop `1c73e8d` 的 B1/B2a 原源，运行前后和Git双重核身份，不编辑其算法。

## 接口和持久状态

`b2b_event_audio.sv` 的输入为已归一化的统一64bit演奏事件 valid/ready，**不是原始UART/MIDI字节解析器**。
采样输入 sample_valid/ready/id32，输出 result_valid/ready/id32/左右signed24/late。
独立 clk，低有效异步整域复位，释放须由上游同步；没有新时钟/引脚/CDC。
sample在Idle优先于event；输入被反压时须保持。pending事件在原router完成分配/CC64扫描后
才允许声音快照；frame期间不接受新外部event，内部退场仍可发生，身份变化则自动丢弃该token。

| 状态归属 | 本轮实现 | 取消行为 |
|---|---|---|
| 四槽 source/channel/note/gen、LRU、key/deferred/releasing、256身份pedal | 只读冻结router/allocator/sustain实例 | 不回滚 |
| 256身份 bend12/mod12/range5 | 只读冻结performance_control_snapshot | 不回滚 |
| 每槽 continuous ADSR/Pitch、DDS/亮度/LFO | 既有B2a，原数学只读复用 | 已推进的状态不回滚 |
| B1双bank、请求/完成mask/full tag | 既有B1，CW本轮明确为74 | 未发布的token/结果可丢弃 |

B1 context = `{PCM24,note8,velocity10,baseFCW32}`，不是原B0的635bit全DSP上下文。
tag = `{request32,source4,channel4,generation32,slot2}`。每帧先写4槽配置和所需身份控制，
再完整读4个描述符；所有4个真实PCM结果以原tag回写inactive bank后才提交。
public read口验证发布后结果；错误generation注入经过真实B1 res端口，不替换声音算子。
普通使用须将inject_valid固定0。pedal_shadow仅镜像已接受CC64/PANIC供B1描述符，
实际NoteOff延迟/扫描/ACK由原sustain实例处理，不以shadow代替生命周期。

资源不能沿旧B0预算倒填：本轮原control snapshot与B1各保留一份256×29控制payload，
共14848 logical bits，两个valid掩码512bit；原sustain/B1/wrapper各256bit pedal共768bit。
另B1双74bit×4 context为592bit、槽身份160bit、flags8bit，以上只是16888bit的明确**部分下界**，
尚未计完整DSP/事件/lifecycle/流水/FSM/快照/descriptor/tag及ROM；不是FF实占或整机容量估计。
共享钢琴ROM只有一个同步读口，持续ADSR/Pitch的ROM复制仍保留，不因B1接入冒称全算子共享。
runner既有 `budget/` 仍是B0解析提案，不能当本B2b实际结构资源报告；新资源映射待授权综合。

## 明确的时钟合同，不倒填旧日历

在采样J后，第一个router静止且无on/off脉冲的边沿记W。
Q=W+8接受原控制快照；snapshot在Q+4产生，wrapper在Q+5读取。
4次控制/描述符装载后B1发出G：Q+17/+20/+23/+26；真实后端C=Q+27。
所有槽统一DSP推进A=C+8。实际ROM响应保持R=1或3时，lane(i)=C+15+R+(3+R)i；
结果首次公开F为最后lane之后4拍。quiescent时W=J+1，F-J=68（R1）/76（R3）。
收据周期用首次valid实际生成沿，即F-J-1，不把外部ready等待算成计算周期。
公开valid反压保持不变；取消/整域复位可撤销。长期外部背压/连续sample优先可饿死event，
**没有承诺无条件外部事件服务时限**，正式系统需FIFO/仲裁由M2另定。

Release_done由每槽真实ADSR public state=Idle且occupied/releasing生成；冻结router按generation
锁存并ACK退场。若在frame期间改变身份，wrapper对整个结果失效；不回滚其它已经推进的声音状态。
B1只在后端实际pitch/ROM计数与valid全空后离开drain；128拍是本N4适配fence上限，
非整机STA/通用延迟参数。不得谎报empty或将同tag复用解释为无条件ABA安全。
前端cancel同沿若有已接受事件产生的NoteOn/Off且后端为空，必须仍交给真实DSP。
因此只有 `stop && !be_empty` 取消后端token，前端/B1照常作废；整域rst_n仍清全部状态。
新增同沿on/off自检在取消后继续计算8/4个PCM，防止丢事件被随后reset掩盖。

## 独立期望与验证输入

checker只将R/I/J/X视为输入，时钟级复用只读T060 Router/Envelope/PianoDDS/Pitch整数定义，
从accepted I独立推分配、重触发、LRU窃取、CC64隔离/延迟释放、retire以及256身份控制。
由J、已推导router静止边沿和上述固定日历自行推Q/G/C/A，检查遗漏/错拍；
observed U/G/C/A/L/W/F/P/Y不用于选槽、算envelope/FCW/PCM或生成后续期望。
数据宽度、行长、排序、全END计数/fixture必需结果、reset、完整4槽和原子提交均严格核验。
结果PCM从独立phase/table索引原钢琴ROM，signed16×unsignedenv16，>>>15向负无穷取整，
原signed16结果扩展为24，四槽signed32累加后一次signed24饱和，左右相同。

长例覆盖真实attack/decay/sustain、CC64与Release最终退场，短例R3验证真实多拍ROM适配；
两可编译行为反例分别使B1忽略generation、gain向零取整。前者须仿真指定非零，
后者须完成含END的仿真退出0，再由独立数学checker指定非零；不以编译失败/截断/超时当成功。
另6份完整capture边界错误只改新接入字段（路由身份/tag/控制/回写context/原子PCM/bank），
不是追加大量历史坏capture或重跑旧夜间压力。

## 编译副本与原始依赖

冻结L中allocator结构体数组字段是Icarus14不支持的语法；新output构建carrier仅将20bit
packed struct数组展开成同位宽bit slice（active19/release18/source17:14/channel13:10/note9:2/age1:0）。
另将sustain_controller的单条绝对include路径迁移为原header搜索路径。没有其它语句/算法变化。
runner逐项反向替换，严格证明恢复原文件bytes，封存原源和compiled carrier两套SHA/映射/命令。
原源始终未改。这里的“编译等价”依赖显式位映射和独立生命周期对照，不声称未转换原文件
已在Icarus直接通过。package/router/control/note_pitch/math其它模块直接编译原件。
开发曾在沙箱中连续访问异常；沙箱外原note_pitch编译退出0。额外试验副本不是最终编译输入。

## 验证边界与下一步

本轮N4候选按自己的明确时钟合同匹配独立黄金，不冒称不同延迟的冻结L整个top逐时钟等价。
没有Gowin综合、资源映射、PnR/40MHz物理STA、实际I2S或设备验证；单次独立综合额度未用。
N8/16/32当前仅既有B1协议与B2a数学分别通过，本轮未实现高N统一事件路由/退场。
下一步沿同一混合候选推广N8，再按实际结果推进16/32；正式架构/档位/生产STA留M2决定。
T061、完整T059不因本轮关闭。原L/v3回退、旧证据、ROM、八共享文件保持不变；状态登记留M2。

复现（已有工具，仓库根目录，输出必须新目录）：

```powershell
& E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe -B -X utf8 code/scripts/run_m3_polyphony_scaling_acceptance.py --stage b2b --output code/output/m3_t061_b2b_reproduce_NEW --repo-gates
```

工具执行需要能正常运行现有Icarus/VVP；受限环境访问异常不能记为通过。总限1800秒/单步900秒，
工具版本/二进制SHA/命令/cwd/原stdout-stderr/退出码/实际耗时均由收据保留。
