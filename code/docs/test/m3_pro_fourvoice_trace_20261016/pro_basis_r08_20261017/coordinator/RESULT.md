# M3 task-day2 R08 集中交付

整体 PARTIAL：软件限定结果如下；真实 Pro 链、G0–G3 与板卡放行均未完成。36 是原12包加新24项的库存，不是36项整体通过。

基线 `ef4fbc74b9d24e08de1e09d0be0eb3163118f258`。新24项中 20 项完成所列必要软件断言；每项真实分支仍 PENDING_REAL_INPUT。原 R7-C 仍有6项未执行，旧额度不恢复。

## 五组实际执行

| 组 | 轮次 | 匹配/已执行/计划 | 秒/上限 | 退出码 | 结果 |
|---|---|---:|---:|---:|---|
| R | initial | 29/29/29 | 0.594/90 | 0 | PASS_LIMITED_SOFTWARE |
| S | initial | 41/50/50 | 4.468/90 | 1 | FAIL_PARTIAL |
| S | repair | 9/9/9 | 2.375/60 | 0 | PASS_LIMITED_SOFTWARE |
| C | initial | 42/42/42 | 0.297/90 | 0 | PASS_LIMITED_SOFTWARE |
| T | initial | 20/21/56 | 0.672/90 | 1 | FAIL_PARTIAL |
| T | repair | 9/9/9 | 0.531/60 | 0 | PASS_LIMITED_SOFTWARE |
| H | initial | 54/54/54 | 1.734/90 | 0 | PASS_LIMITED_SOFTWARE |

MATCHED 代表与该例冻结期望相符，包含正常、拒收及 PENDING/UNKNOWN；不把负例拒收或未知判据升级为真实功能通过。首失败、原输入/源码快照、双流和各例实际结果保留在 FREEZE_* 与 RUNS；修复只消费对应增量，不复跑已通过例。

## 新24项

| 项 | 组件 | 最终断言计数 | 限定状态 |
|---|---|---|---|
| R8-01 | recursive_include_audit | {"MATCHED": 8} | SOFTWARE_READY_PENDING_REAL_INPUT |
| R8-02 | public_port_map | {"MATCHED": 12} | SOFTWARE_READY_PENDING_REAL_INPUT |
| R8-03 | plan_consumption_guard | {"MATCHED": 7} | SOFTWARE_READY_PENDING_REAL_INPUT |
| R8-04 | output_reservation | {"MATCHED": 7} | SOFTWARE_READY_PENDING_REAL_INPUT |
| R8-05 | tool_dependency_identity | {"MATCHED": 7} | SOFTWARE_READY_PENDING_REAL_INPUT |
| R8-06 | build_admission_bundle | {"MATCHED": 9} | SOFTWARE_READY_PENDING_REAL_INPUT |
| R8-07 | capture_csv_codec | {"MATCHED": 5} | SOFTWARE_READY_PENDING_REAL_INPUT |
| R8-08 | async_reset_events | {"MATCHED": 7} | SOFTWARE_READY_PENDING_REAL_INPUT |
| R8-09 | frame_coverage_diff | {"MATCHED": 8} | SOFTWARE_READY_PENDING_REAL_INPUT |
| R8-10 | frame_accept_provenance | {"MATCHED": 7} | SOFTWARE_READY_PENDING_REAL_INPUT |
| R8-11 | finish_protocol_recorder | {"MATCHED": 10} | SOFTWARE_READY_PENDING_REAL_INPUT |
| R8-12 | real_authority_graph | {"MATCHED": 5} | SOFTWARE_READY_PENDING_REAL_INPUT |
| R8-13 | i2s_serial_compare | {"MATCHED": 9} | SOFTWARE_READY_PENDING_REAL_INPUT |
| R8-14 | tx_hold_sequences | {"NOT_RUN": 6} | PARTIAL_SOFTWARE_PENDING_REAL_INPUT |
| R8-15 | clip_lineage | {"MATCHED": 20} | SOFTWARE_READY_PENDING_REAL_INPUT |
| R8-16 | midi_ingress_arrival | {"NOT_RUN": 9} | PARTIAL_SOFTWARE_PENDING_REAL_INPUT |
| R8-17 | midi_recovery_schedule | {"NOT_RUN": 6} | PARTIAL_SOFTWARE_PENDING_REAL_INPUT |
| R8-18 | public_diff_diagnostics | {"NOT_RUN": 6} | PARTIAL_SOFTWARE_PENDING_REAL_INPUT |
| R8-19 | physical_photo_index | {"MATCHED": 6} | SOFTWARE_READY_PENDING_REAL_INPUT |
| R8-20 | io_voltage_budget | {"MATCHED": 9} | SOFTWARE_READY_PENDING_REAL_INPUT |
| R8-21 | measurement_profile | {"MATCHED": 9} | SOFTWARE_READY_PENDING_REAL_INPUT |
| R8-22 | latency_alignment | {"MATCHED": 13} | SOFTWARE_READY_PENDING_REAL_INPUT |
| R8-23 | board_session_capture | {"MATCHED": 8} | SOFTWARE_READY_PENDING_REAL_INPUT |
| R8-24 | recovery_manifest | {"MATCHED": 9} | SOFTWARE_READY_PENDING_REAL_INPUT |

## 保留的边界及下一责任

- 新 R08 尚有 27 例未通过必要执行；具体用例、源SHA与原SPEC见 M2_DECISION_REQUESTS.json。不得把T13增量9/9升级为T整组56/56。
- S首组9例因 Windows 277–293字符的claim路径失败；仅缩短总控用例目录为三位序号，完整64位身份与候选语义不变，原41例未重跑。T首组20例后因SourceFileLoader尝试未冻结旧pyc停组；T13改从固定SHA源码字节加载后只核对应9例。
- R7-A 采样器、R7-B 双路框架与新复位边沿 HDL 均未编译。B 最后 <=stop 改动只有静态等级；C6 静态闭包/装配核同不等于可编译或等价。
- R7-C 首失败及一次定向正例修复保留，余6例 NOT_RUN；需要 M2 对精确新组另给许可。
- R8-13 只按冻结 PT8211 LSBJ16 协议复用 PinDecoder。完整帧与不完整尾段分开，后者 UNKNOWN；没有新增 DSP 黄金或真实串行捕获。
- M1：提供缺失的真实语义与逐样本 PCM/ID/双clip 黄金、算法确认和独立 TX 选择期望。
- M2：决定纯软件结果登记；按 source/include/ROM/TB/工具依赖及安全执行器的精确组合另签首次 HDL 执行。进程树/双流收敛尚未获本轮执行许可，不因纯 guard 或文件哈希通过而放行。
- M2/用户：实物 Part/version/核心板与 Dock 修订、Bank 与电气原件、仪器配置校准及同会话原始捕获、正确新.fs/完整STA与Recovery/Removal/CDC/恢复身份、精确一次SRAM许可仍待到件。本轮没有板卡/仪器/Flash/SRAM操作，没有 E/N32 新工作。

## 原件、额度和发布

PACKAGE_STATUS.json 列36项、各组件源码SHA、每例原始期望/结果和收据；CONSUMPTION.json 列唯一共享消费。各角色READY是执行前静态就绪原件；执行结果以本报告关联的实际收据为准。SOURCE/EXE/DLL仅文件读取，未启动工具或加载DLL；本机外部文件只交身份，不重分发安装文件。

R08 五组及修复实际累计 10.671000 秒；此前本任务 R07/V0396 累计 22.081234 秒另列，未重复计算为R08。模型 token/金额无法从本次执行证据取得，标为未知。

DELIVERY/ORIGINALS_INDEX.json 索引每份原件与分卷 ZIP 的大小/SHA，分卷各自可读取，无需拼接。已签旧源码、首失败与合成/真实来源标记保留。安装工具身份不证明执行安全。

本报告形成时尚未提交/推送；最终精确树九门禁、提交号和远端核验见后续 HANDOFF_FINAL。M2登记/最终复核：待用户转发，尚未送达。

发布前已快进接入 M2 R09/V0398，发布父基线为 `cf370156fb882df3e8fe8bf04b45d3e12ad4c08b`；测试仍绑定原 `ef4fbc74`。17份远端变动已核Git原字节，M3源码未改。R09保留M3原R08范围和消费，M2的编译访问冲突/执行器证据不转化为M3执行许可；详见M2_R09_PUBLICATION_ADVANCE.json。

## C9 到件后的最终边界

已接入16ac226的M1 R07/C9；R7-A/B、R8-02及R7-C新增c9_binding静态后继，详见C9_INTEGRATION.md。上述R08实际测试绑定原冻结字节，C9功能执行0、仅L0；原T27和R7-C旧6未运行仍保留。M1十九项静态来源现已到件，原文缺件清单相应收窄为勘误、独立映射/audio_stable/真实黄金与采集；首次新HDL准入改以最新C9精确组合为目标。
