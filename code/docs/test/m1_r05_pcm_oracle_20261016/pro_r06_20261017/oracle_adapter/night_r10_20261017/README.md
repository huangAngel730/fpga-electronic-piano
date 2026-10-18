# M1 R10：C9 独立数学验收引擎

本单交付一个可运行的 C9 数学适配器，复用原封不动的 DDS、ADSR、allocator、混音和 delay 模型。当前结论 **SOFTWARE_READY / L1 软件**；真实 C9 输入未到，`MATH_RESULT.json` 为 **PENDING_REAL_INPUT**，`board_release_allowed=false`。

## 运行入口

模型目录为 `code/model/m1_r05_pcm_oracle_20261016/pro_r06_20261017/oracle_adapter/night_r10_20261017/`。

```powershell
python -B -X utf8 code/model/m1_r05_pcm_oracle_20261016/pro_r06_20261017/oracle_adapter/night_r10_20261017/run_math.py --job <MATH_INPUT_JOB.json> --output <new-path>/MATH_RESULT.json
```

输出路径必须不存在，防止覆盖旧结果。退出码：0 为软件匹配或已准入的真实数学匹配，1 为数学/身份差异，2 为不支持或合同拒收，3 为缺件/待准入。真实数学匹配仍需 M2 最终签收；不代表时钟、串行、物理或上板通过。

`MATH_INPUT_JOB_TEMPLATE.json` 仅是描述符模板，不伪造现有采集。每个 artifact 填 `{path,bytes,sha256}`，路径相对 job 所在目录；当 M3 原路径与本地交付路径不同，可另填 `source_path` 保存原名。7 件原件为：

| role | 原件与用途 |
| --- | --- |
| mechanical_index | M3 `M3_R7C_C9_MECHANICAL_INDEX_V1` 原 INDEX，保留所有74字段及原行 |
| public_rows | M3 R7-C/R7-A C9 原 JSONL；每行含原换行的 SHA 与 INDEX 核同 |
| raw_capture | 源 raw trace 本体，不能拿公开 JSONL 代替其 SHA |
| independent_plan | M3 独立事件/字节计划，含 `events`、`independent_of_trace=true`，可含 `config_events` |
| frame_plan | M3 独立 `epochs[].frame_cycles`、唯一 `finish{epoch,cycle}` |
| reset_edges | 原异步边沿及明确采样范围；本版支持下述严格 reset profile |
| provenance | 同 capture/source/ROM/TB/driver/observer/tool/argv/双流/退出/finish 来源收据及 M2 准入 |

这份 job 只引用原件，不另建 M3 桥、不修改其 INDEX。字段插入顺序无意义；原字段值、行顺序与 SHA 必须一致。旧61字段BUNDLE、旧B0 settled profile不能冒充C9。

## 已实现的数学范围

支持 Piano/Triangle、Program 0/1 下一 NoteOn 锁存、四独奏/四音保持、力度、普通 NoteOff/NoteOn0、重触发、第五音抢占、显式退休、reset及立体声 delay。未支持 CC64、panic、Pitch Bend/Mod 或未知音色时严格返回 `UNSUPPORTED_PROFILE`；不改原算法/ROM补齐。

- 先用独立计划的完整64位 payload、epoch、顺序和接受窗口绑定实际 `event_valid && event_ready`；独立 plan seq 与由实际接受次序证明的 router seq 分开。
- 同一 router seq 的 allocation 和 consume 分别处理；不去重。NoteOn 消费 C 最早为 allocation E+2，实际背压可继续延后。74字段没有 CTRL_ON/cmd_ready，因此本引擎不声称独立验证了 H 沿。
- pre-NBA 先核旧状态，再应用本沿更新。释放、off消费和退休分开；退休后保留 FCW/velocity/identity残值与相位，空槽同样推进。
- 每次真正的 `advance_mask=1111` 推进四lane；其他非零mask不合并。bank snapshot 为 A+5 pre-NBA；Piano取A更新后相位/表，Triangle取A更新前相位。
- FX仅在实际valid/ready接受时，用独立算出的混音输入更新历史；公开FX输入只是比较对象。已经接受但随后取消的FX历史保留，bypass不推进历史；enable/length切换清历史，gain-only保留。
- result/commit分别核PCM24、ID与双clip；upstream/effect/feedback各自核对。首差异输出cycle/epoch/ID、字段、层和期望/实际，不用DUT phase/env/wave反填期望。

本版输入要求从cycle0起完整连续posedge记录；缺行严格不支持。事件 `arrival_window` 必须覆盖实际接受时刻，不能拿只描述字节发送时刻的窄窗口代替。reset profile 为 `ASSERT_OBSERVED_LOW_BEFORE_RELEASE_V1`：`sampling_phase=POSEDGE_PRE_NBA`、独立 `low_ranges[{epoch,first_cycle,last_cycle}]` 及原 `raw_edges[{epoch,time_ps,value,first_sampled_cycle}]`；每段有拉低和释放两条边沿且至少一条被采样为低。未覆盖“两个posedge之间完整脉冲且无低样本”时拒收，不据公开trace补造边沿。

REAL模式还需 `SOURCE_BINDINGS.json` 中已审查的精确 provenance SHA；当前列表为空，收到新 M2 准入后由 M1 在安全检查点核原件并绑定，不接受调用方自行填 `approved=true`。

## 实际验证与原件

首次 R6-2 新软件组：71方法/70通过/1失败，38.843秒、exit1；唯一失败是合成场景没有触发真实削波。保留首件后，唯一≤60秒修复组只跑修正后的这一例：1方法通过，30.297秒、exit0。生产引擎代码未改；没有声称最终版71方法单次全跑。

新测试包括实际增益/削波与0LSB差异、错ID、错世代、缺/局部/未知推进、跨epoch reset、退休、背压、多阶段seq、无效因果、原件SHA/路径/原行与74字段、REAL拒收及CLI 0/1/2/3返回。测试CLI在同进程调用，没有启动子进程夹具。旧十九项、303/512/1280黄金及M3已签组没有重跑。

`RAW_EXECUTION_ORIGINALS.zip` 保存两组原始双流、退出回执、RUN_SPEC、全部对应源码快照；分散文本遵LF，原始双流以ZIP内字节为权威。源、ROM和接收合同25件已绑定；`INPUTS/`为接收原件快照，`SOURCE_BINDINGS.json`在模型目录。生成脚本、本地路径和历史R01失败均可追溯。

真实 `N10-M1-MATH` 尚未消费。M2/M3需要补齐的具体原件见 `MATH_RESULT.json`；没有实际 C9 编译/仿真、完整串行或新物理/板测结果。NoteOn勘误已采用M2的原/后继绑定，本单不再生成重复勘误。

## 2026-10-18 发布恢复

40 件原软件载荷已形成成果提交 `238b4812a8b8a0238729935730fff7675effe32e`，并安全同步远端。按本机实际系统代理与 HTTP/1.1 恢复了全部 Git 缺失对象，3037 件缺失/截断基线文件按原 blob 核同恢复；未提交基线删除。先前失败和本次原始日志在 `PUBLICATION_RECOVERY_ORIGINALS_20261018.zip`，恢复收据见 `PUBLICATION_RECOVERY_20261018.json`。最终仓库门禁与远端发布状态见后继交接/发布收据；此处不预签通过。原软件测试不重跑，真实 C9 输入和精确 M2 准入仍待。

首次仓库门禁为8/9：T007在中文发布根路径生成ASCII批处理时抛出UnicodeEncodeError，未进入相关仿真。原始日志在`GATE_PATH_FAILURE_ORIGINALS_20261018.zip`。同一工作树迁入纯英文工作区后重新执行原版完整门禁；不修改任何业务代码、门禁脚本、测试或时间限制，不重置C9软件消费。最终状态以发布后的独立验证记录和远端包含核验为准。
