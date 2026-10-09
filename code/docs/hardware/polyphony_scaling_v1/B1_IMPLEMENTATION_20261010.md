# B1：单一复音候选的调度／存储／ROM 传输阶段

仅 D043/D044 B 五路径。业务基线 develop `5f3c67e`，冻结 L 仍按 `6f3e813` 的
56 输入、7 ROM 核身份；B0/返修原件、T060 和全部生产文件只读。
本文件描述**新独立接口候选**，不发布公共接口，不决定正式架构或首个接入档位。

## 实现与公开接口

三份 RTL：`b1_scheduler.sv`、`b1_statebank.sv`、`b1_tagged_rom.sv`。
仅一个 sys_clk；低有效异步整域 reset，真实接入时释放同步由上层另验。
`soft_reset` 是局部同步清状态，**不是外部旧工作域复位**。
N 只支持 4/8/16/32，同一源码参数链；context 固定默认 635bit，B1 将它视为不透明数据，
没有将原 ADSR/PitchMod 635bit 状态安全分时的数学证明。

| 通道 | 合同 |
|---|---|
| cfg_valid/ready | 置换单槽 source4/channel4/generation32、occupied/releasing 两标志及全 context；仅空闲接收 |
| ctl_valid/ready | 256 个 source/channel 独立 control29（bend12/mod12/range5）和 pedal1；仅空闲接收 |
| begin_valid/ready | request32，由调用者给定；全部 N 槽初始化后才能接收 |
| req_valid/ready | tag=`{request32,source4,channel4,generation32,slot}` + context635/control29/flags2/pedal；反压稳定 |
| res_valid/ready | 完整 tag + 新 context635；ready 常开以丢弃旧结果，res_accepted 单独表明有效回写 |
| commit_valid/ready | 仅提交帧身份 **不是 PCM**；所有 N 已发起且各返回一次后保持到接收 |
| read_valid/ready/read_out_valid | 空闲公开同步读回；1 拍延迟，可核原子提交／取消无串写 |
| rom/engine/result_empty | 同一 fence 前旧工作域完全空；不能接常量或用某拍 valid=0 代替 |

控制更新 > cfg > begin > read 优先；同时到达的其余请求反压，**不自动排队或丢弃已接收事件**。
运行期不接收 cfg/control/新帧/read，避免 live-bank 同址读写未定义行为。
发起顺序所有 N 槽（含静音和 Release），同步读取后保持请求。
issued/completed 掩码与完整 issued tag 独立核验；合法乱序可收，重复、未发起、旧请求、
错 source/channel/generation 均不写备用银行。

context 为两个各 N×635bit 的物理银行，当前银行只读，结果仅写另一银行；每银行至多一读一写。
只有完整帧 commit 握手才交换 live 指针，取消时不交换。没有 N 拍原地发布造成的半新半旧状态。
cfg/result 写不并发，cfg/read 也不并发；control memory 是另一个单独读口。
这是逻辑端口合同，不宣称已推断成特定 BSRAM、FF、DSP 或布线。

## 真实排空与 ABA

只要发生过 issue，cancel、局部 reset、成功 commit 后都进入隔离，禁止新 issue/cfg/control/begin。
全空确认前仍接收并丢弃旧结果。重复 cancel/reset 不重置计时，不解除 fault。
有限候选上限为 **N+12 拍（16/20/28/44）**；末拍全空可以放行，否则锁闭至整域复位。
这不是原冻结声学 engine 的实际排空上界，也不能填回 B0 的假设 drain2 日历。

TB mock engine 按真实 pending descriptor、ROM 完成位和延迟保有工作，cancel/soft_reset
不清它；返回队列和 ROM 输出占用也参与 empty。ROM 的 empty 来自真实 occupied，
等待多拍读时即使 out_valid=0 仍非空；drain 阻止新读，并在结果到达后忽略消费者反压消费。
相同完整 tag 复用、request/gen `ffffffff→0` 都在真实 fence 后测试。
整域 reset 测试同时复位 scheduler、ROM 和 mock 队列，绝不以局部 reset 冒充。

对**任意外部生产者**，empty 仍是必须遵守的接口义务；若谎报空后重发完全相同旧 tag，
无法凭当前 tag 辨别。B1 不提供对谎报 empty 的无条件 ABA 证明。
本测试域的 finite drain 不等于生产声音 DSP/LFO 不回滚、Release ACK 或 MIDI 服务已证。

## ROM 和计算占位的边界

新 ROM 是 256×16bit 的地址/标签传输 fixture，值 `(addr*257)^0x5a3c`，
一读口、一个 outstanding，LATENCY=1/3；不是冻结的五张钢琴表或两张 sine。
反压时输出数据和 tag 保持；冲突时 in_ready=0，下一请求保持，未利用异步“零拍读”。
TB 运算只对 **全部 635bit context 做 XOR fixture**，引入 tag/control/flags/pedal 以检出串槽。
Python 独立从 cfg/CTRL/BEGIN/ISSUE/ROM/RESULT/COMMIT/READ 重算，不取返回值作为运算期望。
这不是 DDS、envelope、ROM 波表、gain/mix 或左右 PCM，不能标 N4 音频等价／32 声部成立。

## 验证与复现

仓库根目录，已安装 Python3.11 和本机 Icarus14/vvp；不自动安装：

```powershell
& E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe -B -X utf8 code/scripts/run_m3_polyphony_scaling_acceptance.py --stage b1 --output code/output/m3_t061_b1_reproduce_NEW --repo-gates
```

必须新目录，总1800秒、单步900秒，墙钟超界即失败（exit0 也不能绕过）。
本机受限进程曾出现 Windows DLL access violation；当前原始日志保留，不把产出 vvp 当 compile0。
允许的独立进程运行不加载 environment.bat 的无关 gdk cache 写入，只配置运行库搜索路径。
runner 的 B0 默认入口仍保留；B1 分支才编译新候选。

正式回执以 `B1_PROTOCOL_RTL_PASS_T061_PARTIAL` / exit0 为本调度范围通过，task_complete=false。
8 个 N×ROM 档、1 个慢算子档，公开端口 TB 和独立 Python 回放；两个**实际编译**的 RTL
变异：省 generation 比较、漏末槽就提交，分别由指定检查非零拒收，不能以超时／编译失败代替。
另外从实际 capture 派生5个保持完整END的语义损坏及2个结构损坏（缺ROM可见记录／缺END）
用于核 checker，结构拒收不冒充数学错误检出，不扩大成大量同义损坏样本。
40 个 B0 既有软件自检及6个新 checker 单测；门禁仍包含旧 T007/T019 必需仿真，
不是重新开展旧专项、旧夜间或 Gowin。

## 尚未证明与后续主任务

1. **B2 首先 N4**：635bit 的字段映射、连续 ADSR 私有流水、ROM 预取、Pitch/LFO 相位推进及
   cancel 非回滚、事件/采样同沿语义；与冻结 L 数学逐样本等价后才扩到8/16/32。
2. CC64 这里只存/快照 256 身份 pedal/control；没有 MIDI dispatcher、CC64 最坏扫描、
   Release pending/ACK engine 或端到端事件队列服务实现。实际最大等待仍 UNKNOWN。
   未接收的 valid 必须由调用者保持；fault 后需显式整域恢复，不宣称无界故障期间能继续服务。
3. 任意外部 backpressure/算子延迟没有有限保证，故实际声音 deadline UNKNOWN。
   833 拍监测只标超期、不偷跳槽、不静默丢帧；mock 的快帧不是声学 21拍/voice 证明。
4. 未执行 Gowin 综合，**唯一一次新 B 候选综合额度未用**；资源 packing、Fmax、40MHz
   STA、正式整机与硬件均未验，旧 L/T058 L5 不能移用。
5. 本包仅 B1 传输/隔离子阶段完成，M2 复核未送达；T061 不关闭。共享状态/任务/编号表按
   本任务单禁区未改，由 M2 复核后统一登记。无安装、flash、串口、接线或生产工程修改。
