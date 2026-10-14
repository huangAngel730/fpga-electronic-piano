# N32-C TB/observer 接口合同（按 B 草案对齐，等待精确 PASS）

本子目录归 N32-C。不得编辑相邻 B 文件，不得为测试增加或改变业务接口。

当前状态：`PREPARED_SOFTWARE_CONTRACT_ONLY / RTL_NOT_RUN_WAIT_B`。

精确 B 解锁后，C 必须直接实例化
`b_n32_r1_wrapper #(.N(32), .RESPONSE(1))`；不得依赖或伪造
`B2C_N/B2C_RESPONSE` 宏。编译顺序、GSR、`prim_sim.v` 与 include 目录只接受
B 精确 manifest 的冻结值。

进入实际 C 组合测试前，B 必须提供精确 Review-Key/Fingerprint、文件清单及 SHA、
可实例化模块和参数、编译源顺序，以及 B 的实际 PASS 证据。尤其必须证明 wrapper
绑定的是新平衡 allocator，而不是同名旧 `b2c_voice_allocator`。

C 只驱动 B 草案列出的业务输入：`clk/rst_n/cancel`、真实 64 位
`event_valid/event_data`、`sample_valid/sample_id/result_ready`、固定关闭的注入端口，
以及公开 `read_valid/read_slot`。音符、CC64、pitch bend、modulation、pitch range
都必须经真实 event 握手进入；不得添加或驱动独立 control/release_done 测试入口。

C 只观察公开合同；B 专用测试 wrapper 可以汇集这些已公开状态，但不得层级读取
内部寄存器，也不得为测试改变业务路径：

- event `valid/ready/data[63:0]`；
- sample `valid/ready/id[31:0]`；
- result `valid/ready/id/left[23:0]/right[23:0]/clipped/publish`；
- `cancel/aborted/abort_reason/idle/fault`；
- control snapshot `valid/ready/id/value/occupied/sources/channels/generations`
  （全部为观察输出）；
- control release batch 和 backend release_done
  `valid/ready/mask/slot/generation`（全部为观察输出）；
- public read `valid/ready/out_valid/slot/context`；
- 公开槽身份/状态输出（occupied/releasing/source/channel/note/generation）；
- `audio_state/router_state/publish` 生命周期观察输出。

若 source/channel/note 或 epoch 不是业务结果端口，C observer 仅从输入侧握手维护
`reset_lifetime + accept_serial` 账本，不要求 B 新增业务字段，也不通过层级路径读取
内部寄存器。正常测试必须固定 `inject_valid=0`。

所有 capture 在每个时钟沿的 `PRE_NBA_PUBLIC_PORTS` 相位记录一条完整 `CYCLE`，
格式版本为 `t061-n32c-capture-v3`，
并保留单一全局 edge 顺序；不得分别保存后再拼接 EVENT/ACCEPT/RESULT。检查器由
valid/ready 现场重建接受、读回、HOLD、发布与围栏：RESULT 不能早于 ACCEPT，HOLD
必须位于 result_ready=0 的连续真实沿且 payload 稳定，READ 响应必须对应先前真实
请求，cancel/reset 以前的已取消事务不得在围栏后发布。每沿同时记录 32 槽公开
快照，用输入独立 oracle 核对 33号窃取、source/channel/note/generation 和回收复用。

事件握手不等于槽状态同拍完成。C 必须按 `router_state` 观察真实多拍 FSM，并在一次
事件被接受后保持下一项计划不前推，直至路由器返回稳定 `IDLE`；槽状态的完整语义
比较在该稳定边界进行，中间沿只检查合法状态、握手和公开观察一致性。`cancel` 后
允许进入 `DRAIN`，账本清空不等于硬件已经 `idle`。`rst_n=0` 是异步复位，不要求
也不允许伪造 `aborted=1/abort_reason=2`；reset lifetime 从实际复位断言边界递增。

公开 read 必须是先前沿已接受的请求对应的响应，R1 要求恰好下一沿返回；同沿请求
与响应必须作为专向错误实现拒收。sample/read 的互斥和重叠夹具按 B 精确合同执行，
不能为了让软件模型通过而屏蔽真实 ready 关系。

正式 expected PCM/clipped 必须由冻结独立数学和 ROM 生成，不能读取 DUT 输出固化。
正式 checker 除 plan/expected/capture 外还必须核外部钉住的 execution manifest、
双审 approval 和 run receipt；META 自述不能自行把软件夹具升级为 RTL 证据。
manifest 必须同时绑定 B 的 Review-Key、Fingerprint、精确 PASS 收据、冻结源码快照
及完整编译顺序；approval 是独立文件并由 checker 读入、验 SHA 和两位 reviewer，
不能只把 approval SHA 写进 manifest 自述。正式运行收据必须记录机器、绝对工具
路径及 SHA、逐步 argv/cwd/起止时间/耗时/退出码/timeout/stdout/stderr、前后源码
闭包，并绑定独立 expected 生成收据。任何缺字段、零比较、超时或 WAIT_B 输入均 FAIL。
