# E4 N32 来源与复用审计（2026-10-17）

本子任务仅静态读取和原字节 SHA 核验（L0）；未运行 Python、Icarus、ModelSim、Gowin、旧1300重放、Git写入或硬件操作。新任务单覆盖旧N32离线禁令，但不改变冻结算法与物理/下载条件。完整E4/T061仍PARTIAL，`board_release_allowed=false`。

## 最短可复用真实链

直接实例化 `code/rtl/common/m3_n32_allocator_candidate_20261013/B/b_n32_event_audio_prom.sv` 的 `b_n32_event_audio_prom #(.N(N),.RESPONSE(1))`，N依次为4/8/16/32。它已经连接平衡分配器→router/sustain→control snapshot→B1 scheduler→原pROM后端→signed24左右PCM与准确clipped。不要重写分配器、ROM、ADSR或声音算法。旧 `b_n32_r1_wrapper` 内有 `N!=32 || RESPONSE!=1` fatal，四档新TB不能误用这个固定32壳。

编译顺序从 `B/b_n32_c_interface.json` 的有序列表取得，省去固定N32壳，加入新隔离组合/TB。只读依赖为原音频定义/音高/踏板合同、b1_statebank/b1_scheduler、平衡分配器、B router、b2d_control_snapshot及m2_n32_prom_candidate八个模块。不要链接旧 `b2c_voice_allocator` 代替平衡分配器。旧interface JSON仍标DRAFT、旧README仍标WAIT_B，不可据它们忽略已存在B/C真实后继，亦不以其历史双审条款自动启用新审核。

可只读连接 `m2_n32_output_transport` 的公开candidate接口，在新隔离top内把本次新组合音频输出接到原运输链。它使用原 `premixed_frame_adapter`、i2s_tx和observer bridge。frame credit、实际sample接受、结果首次valid、publish/commit、实际播放frame必须分别留账，READ延迟不能从起点中扣掉。800多拍帧内deadline须按本轮逐请求原轨迹检验，旧347拍数据不是本轮结论。

## 实际字节与原件

所有本机候选、独立数学、五ROM、原封包、报告身份列在 `SOURCE_IDENTITIES.json`；这是本次读取时身份，不冒称旧运行前身份。

| 关键输入 | 本次SHA256 |
| --- | --- |
| 平衡分配器，5449B | `51472b796c9cd883e0fd07ec304559c249fd055929b64a96d53aad5af5b2ce99` |
| B event_audio_prom，17815B | `3012fc17def3f431f34061355ea172b7ecd17ac6f6a8913d2c8d518e32f647d3` |
| B event_router，10671B | `10f1fef4cb133a831081e6a14acb7292d47f491e65ed164fe65720acbea0936f` |
| 原 accurate-clipped event_audio | `4339784901857cab00ce856dc23ce993a59783398d37aca02648c3123b533e84` |
| pROM工程resource_receipt，12470B | `f77a526318cd213b164e9bed5d0d1d0f2ca19aad89a61813f082d7d5971151bf` |
| 原output transport，3490B | `d2b6d311fd990072f399d4e42413c47ef70f2f6f2473b1308b085d9aa49ad154` |
| 旧运输RAW_EVIDENCE.zip，553096B | `b37d2084fada1cd595f207ec91c99125f28488cad4d07a1576b1e6c6da0c195c` |
| 旧综合RAW_EVIDENCE.zip，181796B | `faf63a507d2d06100e47a8b07d28d40b13f0fb4bf14ddf1340498458c3823e8c` |
| C FULL R02 snapshot.zip，9906219B | `15372b95e41463ce6dc459269cf5a60134bda1f7434f41ffc50f9ac2e74d0c9e` |

.NET只读解压流逐成员核验：运输原包108/108成员bytes/SHA全同其MANIFEST，综合原包67/67全同；没有运行包内脚本。原运输ZIP中 `code/output/M2_N32_output_transport_final_20261013_01/vendor_GSR_pROM.v` 为10685B，SHA `d489268e2fbf4b86f5154edb6226205ed21481a958ea3e047916c76ad49470c5`，可由母窗口在新执行快照中复用其原字节（须明确模型来源，不能冒称完整vendor prim_sim）。其full32原receipt确为compile0/sim0、1.172s/11.219s、工具/source前后同；旧工具路径是另一机器D盘，不能继承为本夜工具身份。

原prepared/N32_R1路径在旧manifest有明确MISSING与same-byte别名说明。pROM模块numeric INIT_RAM已嵌入RTL；backend WAVE/OCT/SUB/LFO参数仍带旧电脑路径，实际wave instance未用WAVE_FILE且pROM模块使用嵌入字，不应仅看参数字符串判定缺ROM或任意替换ROM。必要路径映射必须独立记录，旧原件保持。

## 公开观察与静态语义

- N支持4/8/16/32，SW=clog2(N)，TW=72+SW；相应packed总线不能固定成N32宽度。74位context=`{PCM24,note8,velocity10,baseFCW32}`，控制29位=`{range5,mod12,bend12}`；control_snapshot全总线按range-bank/mod-bank/bend-bank拼接，不是lane29连续布局。
- `occupied/releasing/sources/channels/notes/generations`、frame身份/控制、issue/write/publish、lane_valid/slot/phase/fcw/wave/env/pcm/table、live_env/state都是现成公开观察口。backend内部有 `phase_acc[0:N-1]`、逐lane ADSR和pitch/LFO实例；共享wave ROM和串行增益/累加不等于只一个振荡器。
- 每lane phase在共同 `advance_pulse` 才增长；NoteOn重触发不把phase_acc归零。source/channel/note/generation身份和沿前状态需独立参考决定，不据DUT最终slot反推黄金。
- allocator优先同身份→首个IDLE→最小年龄（同龄低index）；NoteOff公开目标取最高匹配index。写优先级release_done→note_on→note_off保留。
- backend cancel丢token/output，不回滚已经发生的DDS/ADSR/LFO advance。主checker须区分advance前取消和advance后取消，不一概认为取消等于无状态变化。
- release_done公开ready常1；mask权威，slot仅最低assert lane；持续直到router退休可能重复观察，按slot/generation去重。CC64批次mask/generation受valid/ready保持，不能把done作为TB驱动输入force退休。
- PCM为各lane已定点结果求和signed32饱和至signed24；clip仅越界，恰好-8388608不clip。冻结backend左右相等，不能把交换相等L/R作为有效反例。运输可用另一个明确夹具覆盖不等L/R接线，不能冒称本声音输出覆盖。

## 旧真实覆盖与失败历史（只引用，不重跑）

B `RESULT_20261014.md`：原N32/R1 10365发布/331745逐槽，347..439拍、32槽贡献、32真实退休、17 HOLD、10取消、187 clipped。三实际输出行为变异ID/PCM/clip拒收。初300s超时及延长后checker超时原件均保留；旧批准延长不扩大本夜600s单工具限制。

C分段R07：R02/03/04 Icarus 0xC0000005；R05关闭ready早于尾帧发布使OP挂住；R06 C09 reset吞C08尾帧而正确报MISSING_PUBLICATION；v6补wait_idle/每OP上限。FULL后继同一进程C00–C09完成10376操作、230事件、4945接受/4942发布、158144 lane、261 READ、4退休/69偷音/2重触发/13踏板延迟；compile1.094s/sim1034.828s。后者超过本夜600s单仿真预算，不可重跑旧FULL凑覆盖。FULL R01第24软件反例case名不存在失败，R02只修软件检查并复用原成功capture，不是新增RTL行为反例。正常FULL clip全0且左右相等。

旧运输12frame新接线短例与bad-left/bad-clip实际RTL已签；它比较同一冻结sender的位流，不是新增独立LSBJ解码。本夜新平衡分配器＋运输组合必须新证，旧12frame不用重复。

旧1300重放 `m3_n32_delay_replay_20261015_r04/RESULT.json`：1300源ID、1299结果/commit、1取消、4重复/欠载、83456 BCLK上升沿；原C_FULL的equal stereo/clip0边界、从已有M2胶囊取M1源的来源限制保留。它是隔离发布重放，不是生产实时N32。本夜未执行它。

旧唯一综合L4成功，但Logic72583/Reg42321/BSRAM162、178级、6.109MHz均是PG484旧allocator工程预布局；原生成工程默认100MHz，准备SDC25ns未进入该综合FileList。PnR/完整STA NOT_RUN、资源准入false；旧gate超时/T007失败及后继runner修复历史不抹去。这些数字不能用于新Pro/平衡分配器准入。

## 本夜最小实现与仍需M1/M2的精确项

1. 新top只连接原参数化B主模块与原transport；N四档同类新输入，在每个档位填满后追加第N+1音、重触发、踏板/NoteOff、背压、取消、reset。固定SOURCE SHA，读取原公开lane输出，独立lane模型和日历导出预期。
2. `audio_oracle.FrozenAudioOracle.__init__`硬拒n!=32，不能无说明调用N4/8/16。新隔离参考适配可以复用原Router/Envelope/PianoDDS/pitch_mod/五ROM数学，在新写集明确参数化适配与N32旧口径相同的边界；不能覆盖旧oracle。它按完成operation结算，不提供精确cycle日历，逐请求833拍必须另由真实沿账本检验。
3. 冻结wave为piano多band/attack-body ROM，不是纯正弦。本夜可以证明N个独立phase/FCW/ADSR与不同音符真实贡献，不能宣称32纯正弦/32独立谱峰/可闻板测。若验收要求硬件纯正弦，M1需签具体测试模式、phase→sine ROM口径、音量/混音/clip及与既有piano模式隔离；本夜不自行换ROM。
4. 新Pro器件完整FPG676型号/修订、商业许可原件、同版正式Pro源码/ROM/top/CST-SDC/完整STA、M2准入.fs和设备均缺。E4物理只能精确预检NOT_RUN，不能沿PG484 GPRJ猜目标或跑教育版。

母窗口统一执行功能轮数/时限/工具预检与收据；本报告不消费功能轮次，不代签本轮RTL PASS，不触发Git发布或审核员制度。
