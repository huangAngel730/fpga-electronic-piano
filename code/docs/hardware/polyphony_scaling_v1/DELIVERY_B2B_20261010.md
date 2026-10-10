# T061 B2b 四声部事件到 PCM 子阶段交付

结论：`B2B_N4_EVENT_AUDIO_PASS_T061_PARTIAL`，`task_complete=false`。
实际等级为独立候选编译/自检仿真及独立Python全事件整数复算L2/L3，非整机或完整T061签收。
前阶段基线develop `1c73e8d`；本轮最终提交/远端/暂存树身份另见转发包 `GIT_DELIVERY.json`。

## 本次成品与实际验证

新 `b2b_event_audio.sv` 将只读冻结统一64bit事件router/allocator/CC64/control snapshot，
接既有B1完整tag/双bank原子提交及B2a真实声音。不是原始UART/MIDI解析器，也不是新音色算法。
只写本单B五路径；没有修改原算法、ROM、production、旧L/v3、T060或八共享文件。
共享状态/看板明确按任务禁区留M2统一登记，不自行取号。

合格运行：`code/output/m3_t061_b2b_final_20261010_02/receipt.json`。
流程总1800秒/单步900秒有界，原命令/cwd/elapsed/退出/stdout-stderr完整保留；
具体实际总耗时与门禁耗时以原收据为准，不从终端截图或预计数字倒填。
新代码/runner/4份只读数学参考运行前后SHA绑定；原L56输入/7ROM按Git `6f3e813` 和manifest双核；
旧B0/B1/B2a封存、B1/B2a复用源及八共享文件前后不变，复用源另核Git `1c73e8d`。

| 同一候选N4配置 | 接受事件 I | 接受采样 J | 完整发布 P | 声部 L | 首次结果计算周期 |
|---|---:|---:|---:|---:|---:|
| 实际ROM响应保持1，长程 | 1,553 | 10,377 | 10,366 | 41,473 | 67–77 |
| 实际ROM响应保持3，短程 | 1,553 | 109 | 100 | 408 | 75–85 |

周期定义F−J−1，与RTL age生成沿一致；包含本wrapper等待原路由、控制读、4槽配置/发起、
真实DSP/ROM/gain/mix及B1写回齐套，不包含外部result_ready长期等待。
以上均未超833拍，但不等于40MHz物理STA或无条件事件服务时限；ROM响应保持不是厂商RAM物理延迟。
合计10,466个完整结果、41,881条声部记录；取消/复位导致部分工作与J/C/A/P数不同，不能删日志凑齐。

每配置7次显式取消，覆盖后端发起前、推进前/后、部分渲染、输出保持；取消不回滚DSP。
新增前端cancel与已接受NoteOn/Off同沿2例，取消后仍继续8/4帧数学复算，未用reset掩盖丢事件。
长例另外2次真实retire改变occupied导致整帧自动失效；独立oracle推导相同原因，未将其算成PCM发布。
各配置4次整域reset，覆盖在途前端和结果保持后恢复；request32经过回绕。
长例独立路由统计4次retirement、5次实际off脉冲、重触发1、窃取2、pedal-deferred1、未匹配off1。
原CC64 source/channel隔离、velocity-zero off、PANIC、immutable release代次及retire通过实际链路。
长例ADSR五公开状态全部命中：Idle11321/Attack586/Decay9600/Sustain769/Release19197条L。
全部256个source/channel地址收到控制/踏板刺激，非法range25共256次忽略；
**只对实际分配到的身份做声音快照读回，不声称256身份全部完成声音输出逐址覆盖**。
发布后的4槽结果descriptor通过public read口逐一核对，不读DUT内部数组当expected。

两份实际可编译行为反例：

- `B1_MUTANT_IGNORE_GENERATION` 编译0、仿真1，真实旧generation注入触发 `B2B_STALE_GENERATION_ACCEPTED`。
- `B2_MUTANT_GAIN_ZERO` 编译0、完整含END仿真0、独立checker1，指定 `MATH_GAIN_PCM`。

另6份新边界完整capture错误按指定原因拒收：router身份、B1全tag、控制快照、回写context、
原子PCM、已提交bank。原END保留，非导入失败/截断/超时；不重复旧56例或批量追加历史capture。
原40项B0软件单测仍通过。仓库9门禁在合格运行末尾及发布前最终暂存树分别执行，
最终确切命令/输入SHA/退出码保存在转发包 `publish_gate/`，不是借用此前B2a门禁。

## 编译身份、旧失败与封存

工具Python3.11.2、Icarus/VVP14；原版本stdout和二进制路径/SHA入收据。
有两份实际编译carrier：原allocator20bit结构体数组语法展开、sustain单条include路径迁移。
原源不改；位域映射、反向恢复原bytes、原源与实际carrier SHA见 `compile_carriers.json`。
其余冻结package/router/control/note_pitch/ADSR/Pitch直接编译原源。详见IMPLEMENTATION。

开发诊断 `m3_t061_b2b_dev_20261010_01` 至 `_07` 原样保留并随包：
沙箱中访问异常、最早结构体数组不支持与后续额外语法试验不作为最终编译PASS。
沙箱外原note_pitch编译0，最终仅保留必要的两份carrier； `_07`短程实际编译/仿真0后独立复算通过，
但这是开发结果，最终验收使用全新final目录。旧试验没有完整runner receipt，原stdout/stderr和
现存编译副本/像保留；不声称重建所有旧时点源字节或给旧失败回填PASS。

首次完整运行 `_final_20261010_01` 曾通过原有限fixture；复核新增同沿事件取消后，
`_dev_20261010_08`实际编译0、仿真指定1，复现 `B2B_LOST_NOTE_PULSE`。
根因是前端token取消无条件传给空闲B2a，使原路由已接受事件的NoteOn/Off被屏蔽。
修正为只对实际后端事务传 `stop && !be_empty`；原B1/B2a/冻结路由本体不改。
新fixture有同沿on/off后继续声音复算，并在全新 `_final_20261010_02`重跑全流程。
第一次结果的中间封存移至 `code/output/m3_t061_b2b_pre_repair_seal_20261010_01`保留，
不用于修后验收、旧PASS不回填修改。转发包仅从原封存提取4份旧源码/manifest并保留原日志，
不重复嵌套旧大ZIP；新旧源码与收据分开绑定。

新 `B2B_20261010/evidence.zip.b64` + manifest + seal_receipt包含本轮候选、只读依赖/ROM、
实际carrier/.vvp、全部日志/收据/报告/反例及开发诊断。封存器检查CRC/成员SHA、合格步骤
退出/时间界限/前后源不变，并再次独立重放2个正例；旧B2a大包不重复打包。
新交付文档及封存/发布脚本由最后暂存树门禁和Git树另绑定，不倒填已结束run的candidate清单。

## 明确保留的缺口与下一步

本轮完成N4 candidate按明确新日历的事件/状态/数学对黄金逐样本匹配。
未证明不同采样延迟的冻结L整个top逐时钟等价；无实际I2S/硬件、综合/PnR或物理STA。
N8/16/32事件分配/CC64/retire整链接入**尚未实现**；原B1高N协议/B2a高N数学不等于高N演奏。
本轮N4无高N削波实际路径，既有B2a正饱和RTL缺口未在此虚称闭合。
长期result背压和持续sample优先仍无无条件外部事件服务上界；所有cancel同沿排列也未穷举。
单次Gowin独立综合额度未用。下一阶段沿同一候选推广N8，再按实际稳定档推进16/32，
由M2决定正式架构/档位、生产接入和精确工程新STA；不得降48k/少算voice/放宽时序达标。
无APK安装、烧录、串口、接线或新采购；完整T059/T061保持未关闭。

复现命令和接口合同见 `B2B_IMPLEMENTATION_20261010.md`；M2交接见 `M2_HANDOFF_B2B_20261010.md`。
