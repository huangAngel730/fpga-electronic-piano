# B2k 在途取消、复位与非回滚相位

2026-10-11，M3 按 D043/D044 补 B2j 明列的早期在途取消缺口。
仍是同一混合候选，不修改任何功能 RTL、旧 TB、ROM 或封存。

## 公开接口与独立期望

新 `tb_b2k_cancel.sv` 以 25ns 时钟逐拍输出 PRE-NBA T，包含 reset/cancel、
样本/结果握手、idle/publish、backend launch/advance、实际事件及 lane 相位；
每个真实 lane pulse 另有同沿 FCW。无层级窥探、force 或内部状态填期望。
场景开始前实际接受一条 A4 NoteOn（source1/channel2/velocity1023），随后路由静止。
N32 表示全部32槽渲染，但本次只有一个占用槽；不称32路同时发声或完整演奏证明。

checker 独立更新 wrapper/B1/backend 的旧状态，不用捕获 ready/valid 反推时刻：

- J 为公开样本握手。静止路由下 E=J+9 接受控制快照，E+1..E+N 串行读，
  E+N+1 的 PRE-NBA valid 被消费，E+N+2 才能观察到控制输出已排空。
- B1 begin=J+3N+11，首个 OFFER=J+3N+14，后续每3拍一槽。
  首 OFFER 同沿取消不发出；已发出则必须经过 B1 DRAIN。
- backend 接受 C=J+6N+12。占用槽 Pitch counter/valid 到 C+8 的 PRE-NBA
  才消失；ADVANCE=C+8，同沿 cancel 禁止该 advance，但此前已发生的推进不回滚。
- 每槽 ROM_START=C+14+s(R+3)，response counter 首次为0的观察沿是 start+R+1。
  取消 suppress 同沿新 start，不能抹掉旧 response ownership。
- GAIN=C+15+R+s(R+3) 注册 lane；PRE-NBA lane 在下一沿可见，即使那一沿 cancel
  仍须保留旧 pulse，随后停止新结果。源码日历计算首次 valid，握手可因反压后移。
- backend DRAIN、B1 DRAIN 和 wrapper DRAIN 分别看旧 empty 状态，不把它们并成一个标志。
  输出在取消前已 valid 时仍按旧值检查，但取消当沿禁止 publish。

DDS 期望只用已接受的 A4 输入及只读 `dds_model.note_fcw`：每次独立预测的 advance
使 slot0 phase +=39370534 mod 2^32；取消不回滚，整个域 reset 清零。
后续恢复帧逐 lane 检查 phase/FCW，闲槽期望0。没有用 lane_phase/FCW 回填期望。
没有在本轮独立证明 LFO/ADSR 的所有非回滚细节，也没有重新计算 PCM 数学；
左右PCM只核范围、结果身份和 HOLD 稳定性，既有数学签收保持原边界。

## 覆盖与可复现结果

每配置21组“被取消/复位帧→完整恢复帧”：17次取消（含3沿重复）、4次在途全域复位。
取消涵盖 WAIT_ROUTER、控制接受前/读取中/输出消费、首槽发出前后、backend接受前后、
Pitch尾部、ADVANCE前后、首/后续ROM等待、GAIN和旧lane pulse边界。
复位位于控制读取、首槽已发出、Pitch、ROM等待。正常组取消后立即拉高 sample_valid，
必须在推导的第一个可接收沿握手，提前或推迟一拍都拒收。

N4/R1、N32/R1、N32/R64 共126请求、51取消、12在途复位、63发布、99 backend launch、
87 advance、1437 lane、15实际 NoteOn。连续观察沿分别2616/10988/53763。
R是已有 downstream response holding 参数，不是 Gowin RAM 物理延迟。
R64用来验证长响应排空，正常完整帧超过833，绝不作为48kHz deadline准入配置。

几个实际边界：N32控制读取首沿取消后34拍再接收；Pitch接受后一拍取消需10拍；
N32/R64的首/后续ROM等待取消需67拍，重复取消3沿时从最后取消算65拍。
这些是所列具体场景，不是任意 MIDI/身份失效/注入下的通用上界。

8个完整坏capture：控制在途提前ready、恢复ready推迟、cancel仍advance、
恢复phase回滚、错误slot、旧lane丢失、假publish、END错。保持全量记录与正常END，
每个按指定诊断拒收，不用截断代替语义错误。
两个真实可编译功能副本变异只写 output：忽略控制快照排空、忽略后端/B1排空。
均compile0/sim0、完整END后 checker1/CANCEL_IDLE。
坏保护会永久留下控制结果，因此负例专用宏在定长观察窗口后全域reset再继续全部场景；
正例没有该宏，保持取消后立即请求。该差异显式绑定编译命令，不混作正例排空证明。
10项软件自检覆盖控制请求同沿抑制、控制pending延迟/提前拒收、首OFFER前后、
占用槽Pitch排空、reset、场景清单、严格参数类型、缺件/未知记录。

## 未验及下一准入

新结果限定独立功能 L2/源码周期参考核验，不是新的完整声音数学L3或物理L5。
本轮不证明任意事件同时发生、身份失效全部交错、无限注入下可用性、LFO完整非回滚、
冻结L整个top逐时钟等价、资源映射或40MHz STA。原128拍故障锁闭不变。
未运行长程旧RTL/Gowin/综合/PnR，也未生成码流或操作设备；原RAM阶段不重启。
下一准入仍由M2选择同一候选的代表综合配置/资源准入及正式接入、新整机STA。
完整T060/T061保持未关闭；本阶段状态交M2统一登记，不写8处共享文件。
