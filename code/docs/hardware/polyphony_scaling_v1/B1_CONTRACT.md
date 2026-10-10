# T061 B0 → B1 单一主候选合同

本阶段执行 M3 / T061 / D043 新增 B 范围，D044 收缩优先。
当前只交源码审计、可运行预算、Python 协议 oracle；没有独立 RTL 模块或声音 engine 完成。
验证等级：L0 源码清单/预算，加 Python 语法检查和软件自检；不能标新 RTL L2／综合／L5。

## 选定路线与状态布局

选单套分时完整上下文 engine，N4→8→16→32 是同一实现参数链。
全并行复制增加 ROM／运算器与布线；混合多 engine 另增端口，暂不实现第二套。
正式采用和首个接入档位由 M2 评定，不以软件条件余量自签 32 复音。

存储清单明确分 voice_context、voice_work、snapshot、256 identity、global。
ADSR 私有状态 4bit，phase32，source4/channel4/generation32、bend12/mod12/range5 不缩减。
allocator 的相对 age 扩为 ceil(log2N)，扫描索引还要能表示 N；这只是 N>4 提案。
router／allocator／sustain 的重复身份存储保留，不未经等价证明去重。
635bit/voice 的连续工作状态暂全入上下文，另计一套 635bit engine 工作副本，宁可保守。
这些 bits 包含 RAM payload，不能与工具 FF 容量直接作可行性判断；所有译码、mux、
资源推断和物理端口开销仍未知。板级 FIFO／I2S／HDMI／PLL 不在本音频核清单中。

## 日历合同（未实现、未实测）

固定 admission settle8；原子控制快照 N+1；每槽串行：
context read1 → pitch消费7 → DDS advance1 → wave读1 → envelope settle6 →
gain1 → stereo累加2 → tag校验1 → context write1；共21拍/voice。
末尾 drain2、commit2、guard16。假设同步 ROM 一拍，每张激活表各一读口；
五张表是不同存储，不是五次读取共用一个物理端口。N 槽全部执行，包括静音／Release。

条件合计 29+22N：117／205／381／733 拍。32 的条件余量100拍，**不是实测余量**。
dispatch／CC64 扫描／外部 backpressure 未给有限上界时端到端 UNKNOWN。
框架会拒收未知/非正耗时、缺工作步骤、不匹配端口/读延迟；慢算子会明确超833拍。
实际共享 engine II／latency 为 null；21拍只是下一步设计约束，不能以 budget PASS 代替 TB。
原 PitchMod 算术 II1、消费7拍，四槽包装最小发起 II8，不能混用。
ADSR note-on 初始化4拍、note-off2拍；后续连续流水与跨槽虚拟时刻的等价尚待证明，
不能简单认为插入6拍就自动等价。此项若需要更多拍，必须改候选合同并重新预算。

ROM 保存全部七份身份，piano 实际五表共70632bit/份；两个 sine 是替代模式。
L fraction-ROM XOR 地址置换须保持，sub_source 是初始化图像，不额外计活跃查询端口。
串行 signed32 左右独立累加，最后一次 signed24 饱和；保留 Q15 floor 与 PCM 左移8。
velocity 已在 envelope gain ROM 中，不另加一遍力度乘法。八个逻辑乘法运算不等于八个 DSP。

## B1 接口提案及安全条件

新候选内部 tag：slot ceil(log2N) + source4 + channel4 + generation32 + request32。
request／result 都使用 valid/ready，payload 稳定至握手；statebank 一读一写的实际实现待验证。
发起掩码／完成掩码记录所有 N；无结果、重复、未发起、错代次、旧请求均不得改本轮 scratch。
乱序合法返回可接受，但每槽只能完成一次；N 槽齐后才提交 PCM。
事件、控制更新与音频快照互斥。Release pending 的身份与 ACK 生命周期按原冻结源保持。
frame cancel 清 token／scratch，但已被真实 DSP 接受的 LFO/phase 进展不回滚。
Python oracle 不计算这些声音状态，故未证明非回滚语义；不能用 scratch 清空代替 DSP 证明。
request/generation 回绕与完整 tag 复用必须先完成下述排空 fence；不能仅凭位宽或清 scratch。

### M2 B0 回执后补充：软件可执行排空合同（不是 RTL 证明）

所有 source/channel/generation/request/slot/N 均先严格 Python 整数类型和范围检查，
拒绝 bool、float（包括数值相等的 True/1.0）。非法 result 返回 False，不靠异常拒收。
配置、replace、pedal 的非法身份返回明确 ValueError，且不修改状态。

oracle 的 `drain_limit` 必须由调用者显式给出正整数；自检取8或2仅为软件测试参数，
不是冻结 ROM/engine 的实测排空上界。B1 选择实际上界后必须用 RTL 公开接口证明。
发起过工作后 cancel、reset，以及成功 commit 后，都进入 draining，禁止新 begin、
身份 replace 和 pedal 更新；旧 result 一律不能写 scratch。尚未 issue 的取消没有外部工作，
无需 fence。该保守策略不新增 epoch、不保留无限历史 tag 集合。

每次 `drain_step` 表示一拍，只在 rom_empty、engine_empty、result_empty 三个严格布尔
确认同时成立时解除隔离。确认的含义必须是**该 fence 以前所有工作及重复结果此后不会重现**，
不是某一拍输出 valid=0，也不是只清本地掩码。B1 要阻止新 issue，排掉/丢弃旧 ROM、engine
及返回队列（含 backpressure）；握手传播和内部状态均纳入 empty 证明。
有限上界末拍仍不全空则锁定 DRAIN_TIMEOUT，不因计数到期放行；重复 cancel/reset 不延长计数，
局部 reset 也不能绕过 timeout。实际恢复需另证明整个旧工作域被复位/排空，本 oracle 不提供
无条件“清错误继续”捷径。

同 request/generation 复用及32位回绕均使用同一 fence。若外部谎报全部 empty 后仍发完全相同
旧 tag，软件无法与新 tag 区分；自检显式演示此限制，**不宣称软件无条件消除了 ABA**。
Python 行为反例不代替 B1 的公开 RTL TB 和至少两个可编译 RTL 行为变异。

上文固定 drain2 仍是原未实现日历假设，未因新增软件握手变成实测值；真实 fence 最大延迟、
CC64 最坏扫描/排队/事件服务上界均 UNKNOWN。117/205/381/733 只在旧条件下复算保持，
不能把测试8拍填进生产预算，不能将 timeout 锁定当作有限 MIDI 服务保证或允许丢事件。
新增 fence 的控制、状态、端口和周期成本待 B1 实现后重计，整体 end-to-end 继续 UNKNOWN。

## 下一阶段验收

只在 D043 B 新路径写独立可综合 scheduler/statebank/tagged ROM，配公开端口 TB。
实测一拍/多拍 ROM、端口冲突、II/latency、慢算子、写冲突、cancel/各阶段 reset/recovery。
至少两个**可编译 RTL 行为变异**由指定 checker 拒收；本轮 Python 错 tag 用例不能替代。
之后 B2 用冻结 L 的时间/数学 reference：先 N4 逐样本等价再8/16/32。
ADSR 连续 pipeline、ROM prefetch、事件准备与虚拟 core-cycle 保持是主要风险。
不得迁就候选改黄金模型，不改原 L/ROM/生产 RTL/公共包/CST/PLL/top/共享表。
本轮未使用一次 Gowin 综合额度；只有软件和新 RTL 条件满足后才考虑授权的一次资源预检。
正式接入／新整机 STA／设备动作仍归 M2 与后续用户授权。
