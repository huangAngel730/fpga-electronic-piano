# MIDI有界调度与Program Change：M2独立复核（2026-10-03）

## 结论及版本

A `2fdc3136f22a9a110f54ed47adbd08bdb8fe03dd` 和 B `3d6430edcd03f78dd47c5db1f3a6415153cbc20f` **输入侧L2复核通过**。
复核开始HEAD为52106a2，两个提交已在线性历史中，无需重复拉取或覆盖。
正式修改范围为M3输入模块、README、专项脚本及对应TB；未改公共包、正式顶层、CST/SDC、音频算法、可视化和STAT。
本轮M2没有修改任何正式RTL/TB。记录不扩大为音色切换、实际Pitch/Mod音效、综合、PnR、整机时序或实物通过。

## 源码判断

A计数只由实际离散握手推进；控制待发送且1kHz冷却已结束时，默认8个离散握手后锁定一次连续控制机会。
已展示且被反压的离散/控制事件不被抢占或改写；锁定控制同项的新值留在待发送槽。
同拍更新选中槽时采用最新值，CC1去重与32槽round-robin保留。
该上界是满足冷却、存在待发送控制、持续有成功握手时的事件数量上界，不能无条件宣传成固定微秒响应；无限背压与有限FIFO容量边界仍保留。
Program Change增加后也属于离散流，可能参与8事件计数，但离散FIFO内部Note/CC64/Program顺序不变。

B在Cn的一数据字节完成时产生全零默认事件，再设置EVENT_CONTROL_CHANGE、SOURCE_ID、channel、CTRL_VOICE_SELECT与原始0～127零扩展值。
重复程序号仍逐条进FIFO，不缩放、不加1；Dn仅消费。Running Status、实时字节、系统消息取消上下文、满FIFO同拍出入与诊断计数均通过真实TB。
CTRL_VOICE_SELECT公共编号已存在，本次没有新增包依赖或擅自映射到0/1音色。
现有performance_control_state只处理Pitch/Mod，Program到正式音色选择的状态/快照/NoteOn锁存仍须M2单独完成。

## 实际独立执行

本机没有脚本默认E盘ModelSim位置，使用已安装Icarus执行实际DUT。
三个新TB在直接访问结构体数组字段时触发Icarus内部断言，未将编译失败误算成行为性反例通过。
M2仅在output复制TB，把对应字段访问改成纯函数访问，字段宽度及事件内容不变，正式DUT原字节不动。
兼容适配覆盖tb_midi_control_fairness、tb_midi_program_change和tb_midi_control_fairness_uart；精确补丁、原/适配哈希与日志保留。
M3原ModelSim通过陈述不因本工具兼容限制而撤销，也不冒称本机运行过原ModelSim脚本。

| 正向用例 | 实際结果 |
|---|---|
| Pitch/CC1全映射 | 16384 Pitch原值、128 CC1、16通道/2来源、36904检查PASS |
| 队列快速配置 | 1291检查、43控制握手PASS |
| 队列真实50MHz | 51227检查、最小50000拍间隔、43控制握手PASS |
| Pitch/CC1真实UART | 50MHz/31250、8事件14检查PASS |
| Note原回归 | 44检查PASS |
| CC64原回归 | 2058事件/4134检查PASS |
| 有界调度快速配置 | 180检查PASS |
| 有界调度真实50MHz | 180检查PASS |
| Program映射及FIFO | 16×128程序号、2来源、4143检查PASS |
| Program真实UART | 7事件/10检查PASS |
| A+B混合UART | 15事件/8检查PASS |

三种可编译的错误实现实际被行为断言拒绝，退出码均非零：
1. 恢复仅空离散FIFO才能发控制：检出超过8次离散握手的饥饿。
2. 控制反压期间改写payload：检出被阻塞事件变化。
3. 去掉1kHz冷却：检出连续控制握手速率超限。

仓库9项门禁全部PASS，含135文件Python语法、T007顶层仿真、T019公共包仿真与参考摘要。
`git diff --check`通过。实际输出在 `code/output/midi_AB_M2_review_20261003/`。
证据清单见 `code/docs/evidence/midi_scheduler_program_M2_review_20261003.json`。

## 后续范围

M3两项输入算法任务可按L2签收，无需重复开发或重新采集USB CSV。
可选将三个TB的纯函数访问兼容写法收回正式TB，范围只限这三份TB；这不阻塞输入功能签收，不要求重写解析器。
M3计数末端选择正式补丁继续原范围，不被本轮或Hold隔离试验暂停。
M2后续负责成功握手tap、采样快照、音色编号政策及正式音频接入；最新解析器必须纳入下一次完整组合PnR/STA。
旧ADSR/严格闪光/计数候选的+1.102ns不外推到新解析器或最终Pitch/Mod/效果器组合。
T036整体保持进行中，实际音效与同版实物证据另验。

**反馈待用户转发，尚未送达。**
