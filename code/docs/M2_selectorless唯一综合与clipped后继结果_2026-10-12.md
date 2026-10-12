# M2 selectorless唯一综合与clipped隔离后继结果

2026-10-12，M2自审。用户本次明确授权一次selectorless仅综合900秒及新增准确clipped隔离接口；不含PnR/STA/设备/生产接入。起始804222c与origin/develop一致。原冻结源码、ROM、正式top/公共包/CST/SDC和旧失败不改。本轮两条工作分别保留精确身份，**clipped后继不在本次资源工程里**。

## 一、唯一一次selectorless仅综合：超时失败，资源仍UNKNOWN

新增入口code/scripts/run_138k_selectorless_authorized_20261012.py固定原N32/R1/audio_and_public_read_no_injection、GW5AST-LV138PG484AC1/I0、Gowin V1.9.11.03 Education实际工具身份。原freeze SHA883297182d9705788d5d04855b597ad8620ab2b1b8ca38727a8b06492a0454e9，selectorless repair90f41bba512a3b7b4e4033e37bdce20e53b0347acf188d76c4286574cad8f576，Tcl c1747c36bf4cc16f35e578e8fb6b8712a4507313d017d825465c932d0e724f2b，shell4c172d4c0d2a4c7ef5c764d091a315cbcde2127573554bfd7d09ac6f2e5ea535。

用户原话、入口SHA及已签预算/Job Object源码身份写入新selectorless_authorization_20261012/consumed.json，原false receipt和旧consumed历史不改。只原子占用一次，失败也消耗；入口无可替换project/tool/timeout参数。预检正常0及三新范围坏例拒收（run all/错top/额外PnR），不重复旧15假工具套件。只有明确--execute才启动。

实际命令：

```powershell
python -B -X utf8 code/scripts/run_138k_selectorless_authorized_20261012.py --execute
```

新输出code/output/M2_N32R1_selectorless_authorized_20261012_01/，GPRJ原字节复制、Tcl只有cd/open路径可逆变化，源/include/ROM/SDC指向原只读输入。总900秒从入口开始，包含预检/工具/报告/后验/成功收尾。Windows子进程先suspended、加入本次Job再恢复；900秒超时TerminateJobObject只停止本次树，失败收尾保存partial元数据，不重试。

**真实tool_runs=1、timed_out=true、runner exit1、FAIL_PARTIAL，记录耗时900.368秒。** 900秒到达后终止和写失败收据产生约0.368秒尾部，不延长工具运行或冒成功。日志完成解析/优化/推断并到Running technical mapping；原unknown synthesis tool配置错误没有重现。没有新的.vg、*_syn_rsc.xml、.fs/.bit。仅残留本次生成.log/.prj，不能把它们当资源报告或完成网表，资源UNKNOWN、resource_admission=false、STA NOT_RUN。

预算到达后运行内source_after/完整artifact collection没完成，receipt明确为空/false，不倒填。随后单独READONLY_POST_FAILURE_ARCHIVAL_AUDIT核32份原/准备输入SHA与启动前相同，工具SHA同；这是失败后的归档审计，**不是继续执行900秒尝试或宣称运行内后验通过**。重复预检拒ONE_ATTEMPT_OUTPUT_OR_AUTH_ALREADY_EXISTS_NO_RETRY，没有再次启动gw_sh。

原日志中的表达式截断/未用字段/RAM提取告警保留，未为通过关闭或改算法。超时发生技术映射，不足以判断32音容量或40MHz时序；本轮不追加额度、不提高超时、不切N8重新综合、不PnR/STA。后续若要再做物理工作须单独确认精确范围，不能复用本次已消费许可。

## 二、clipped后继：元数据增量L2通过，不接生产

新增code/rtl/common/m2_n32_clipped_candidate_20261012/b2d_event_audio_clipped.sv从原b2d复制，原源SHA5f1a0d2e89fcb6f2d6ff97964e96953c2e9247e828536b521a43327d80c0a0ce保持。只变module名、增加clipped端口、reset/cancel清除、在原RUN发布result_id/left/right同沿锁存既有be_clipped。HOLD不重算/不从PCM极值推测；result_valid限定metadata有效，握手后无效期可保留旧值，下一结果覆盖，取消/复位清零。

新增runner反向替换这六处明确变化后与原源逐字节相同，验证无其它算法/控制修改。测试宏只在变异编译时将clip强制0或去掉取消清零，用于行为拒收；正常编译不激活。原b2d/backend/B1/router/ADSR/Pitch/所有ROM只读，正式top/接口组不改。

新增文件：

- code/rtl/common/m2_n32_clipped_candidate_20261012/b2d_event_audio_clipped.sv
- code/tb/audio_out/m2_polyphony_frame_candidate_20261012/tb_n32_clipped_successor.sv
- code/scripts/run_m2_n32_clipped_incremental.py

实际命令：

```powershell
python -B -X utf8 code/scripts/run_m2_n32_clipped_incremental.py --output code/output/M2_N32_clipped_increment_20261012_01
```

新TB对原b2d和后继使用完全相同公开输入，N32/R1、32不同source/channel同note81/velocity1023、96个指定输出窗口；clk40MHz仿真节奏。并联只读原件逐沿比较event/sample/result ready/valid、ID、左右PCM、late、idle、占用、lane、advance和publish，全部一致，不重跑旧B2G/B2H或独立DDS/ADSR数学模型。新测试针对metadata路径而非旧生命周期签收。

正常compile0/sim0；总runner100.112秒/总300秒/每步90秒，6步实际退出：

| 步骤 | 退出 | 秒 |
|---|---:|---:|
| 正常compile/sim | 0/0 | 0.778/50.365 |
| 错clip强制0 compile/sim | 0/1 | 0.532/21.925 |
| 错取消不清clip compile/sim | 0/1 | 0.410/23.504 |

正常结果：32事件、97实际请求，其中1个已产生准确clipped的HOLD结果被frame取消，96个结果/96个成功buffer提交；14次真实正饱和、14次真实负饱和，clip_count=28。389个HOLD观察沿保持ID/PCM/clip稳定；取消结果不提交不计clip；共享复位清clip和计数。

TB只从公开lane结果在signed32累加，检查实际混音clip阈值与PCM24限幅。M2另外从96条原P日志用标准整数逐项核：clipped恰为wide>8388607或wide< -8388608，左右输出恰为限幅值，14/14覆盖同。没有重算FCW、波表、ADSR或更改声音语义，这不是新的声音黄金链L3结论。

新后继clipped接原premixed_frame_adapter，只成功commit推动原pcm_clip_counter一次；取消/held重复不计。两可编译错误实现分别被PUBLIC_CLIPPED_NOT_EXACT_WIDE_SUM、CLIPPED_NOT_CLEARED_ON_CANCEL指定断言sim1拒收，不拿工具/格式失败冒行为反例。源前后SHA一致。

## 三、未完成与下一步

准确clipped端口在这个隔离后继的指定功能组合已可用，V0300里“无公开准确clip”的缺口在**本后继**中补齐；不回填原冻结b2d或旧bind0报告。新后继没有综合/PnR/STA，原selectorless超时不包含它，不能给新组合签资源准入。暂不接生产、不改播放算法/正式参数、原4音/60K和newRAM5e1d13c回退保持。

未验真正32bit ID回绕、无限持续事件竞争、所有取消阶段或负载、整机I2S/CDC/HDMI观测接入、长期实演奏/设备。原96帧夹具只是metadata功能验证，不能签通用833拍截止/32音实体演奏。完整T052/T060/T061 PARTIAL。没有安装/串口/烧录/接线。

M2完成必要规定九门禁后，最后fetch取号/独立登记/普通提交push/远端核验，以后置收据为准。若远端期间有新M1/M3交付，只接收并标待专项，不套本结论或重复已签测试。

## 可转发M3/M1

M3/M1，用户已明确授权M2本轮工作，selectorless原N32/R1仅综合一次已实际执行并在900秒超时，技术映射未完成、无网表/资源报告，资源仍UNKNOWN，已停止自己树，不重试/提高超时/追加PnR或设备。原源/ROM/false收据/旧失败不改；归档后原32输入/工具SHA保持。

M2另完成独立b2d_event_audio_clipped后继：只公开既有be_clipped，与ID/左右PCM同沿注册，reset/cancel清除、HOLD稳定；原N32公开行为逐沿等价，96提交含14正/14负饱和、clip28，一已clip结果取消不计，389 held沿和reset通过，两实际编译行为坏例指定拒收。只新隔离L2、未综合/生产/STA。原源码、算法、ROM、正式top和共享接口组字节保持，不能把本次资源失败或旧STA外推新组合。

M3继续已派独立任务和另行批准的T060 A/B范围，当前不让你追加Gowin/修改N参数/重做旧声音测试。准确clip字段可在后续pin_projection说明中引用本新端口身份，但实际公共接口接入仍由M2主控，M1不修改原DUT追随。完整任务不关闭。待用户转发，尚未送达。
