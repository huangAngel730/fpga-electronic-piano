# R11 包 C：finish 调度提案与完整 route 准入边界

本件只完成 L0 静态准备，交夜间任务1汇合、M2决定。未实施 TB/RTL 后继，未导入、编译或运行候选，未生成 FRAME。当前完整 route 为 NOT_RUN；execution_allowed、digital_verified、math_verified、real_verified、board_release_allowed 均为 false。原 1130660/1130661 候选、失败原件和已消费台账原样保留。源码身份及原件入口见 SOURCE_BINDINGS.json，申请与缺件见 EXECUTION_REQUEST.json。

## 1. 原因与两个候选

相对路径以下均从仓库根目录解析：

- `code/tb/board/m3_pro_fourvoice_trace_20261016/pro_basis_r07_20261017/public_capture_tb/c9_binding/tb_r7a_c9_public_capture.sv:248–251`：先等 D 个 driver posedge，再等 driver negedge，然后登记 core negedge 等待。driver 初值0、周期25ns（12、89行）。
- 原 C9 source ZIP 的 `inputs/sources/clock_plan_sim.v`：core 初值0、周期25ns。这个 nominal 模型不证明真实 PLL 相位/锁定/MTBF。
- `r7a_c9_public_observer.sv:89,135–143,216–226`：sample_cycle从0开始，在实际 core posedge PRE_NBA采样，先写行，后递增。driver NBA cycle_count 是另一计数，不直接拿来当 core cycle。

第 D 个 driver posedge对应 core cycle D−1；其后两个负沿名义上同一时刻。第二个事件等待可能赶上尚未传播的 core negedge，也可能错过它并等下一次。这是同时间槽事件排序差额，不是把 observer 改为 POST_NBA 的理由。

| 原候选（均未获批准） | finish cycle | finish time_ps | END row_count |
| --- | ---: | ---: | ---: |
| 同槽赶上第二负沿 | 1130660 | 28266512500 | 1130661 |
| 等下一 core 负沿 | 1130661 | 28266537500 | 1130662 |

上述 time/row_count 仅按旧候选 first_core_ps=12500、period_ps=25000 做坐标算术，不是测量值或 FRAME_PLAN。R10 WINDOW_PROPOSAL 选择1130661仅为未批准 argv，不能据此签相位。

## 2. 最小可逆后继提案（尚未实施）

建议 M2 决定是否采用显式 core 正沿屏障。仅在批准的新 TB 路径替换旧第251行；原 TB 保留。示意为：

```systemverilog
repeat (STOP_DRIVER_CYCLE) @(posedge driver_clk_40m);
@(negedge driver_clk_40m);
@(posedge obs_core_clk);  // Explicitly pass the coincident-negedge time slot.
@(negedge obs_core_clk);
finish_requested = 1'b1;
wait (capture_done);
#1; $finish;
```

在已绑定的同相、初值0、25ns模型前提下，显式 core posedge 是 cycle D，finish仍为0；随后 core negedge置位，下一个 PRE_NBA cycle D+1采到唯一finish。因此该提案确定对应1130661/28266537500/1130662，不依赖同槽两个负沿的处理顺序，也不改变 observer采样相位。不得对不同/未核时基套用此数值。

这是文档中的变更说明，不是新增 TB 文件或获准可执行源码。M2须明确：选择这个D+1后继或其他精确方案、批准的唯一新路径/原文diff/SHA、nominal clock与reset模型、窗口及适用工具。批准后由原负责者实施并重新装配75单元/source graph/申请/模块绑定，不能原地覆盖或冒用旧TB SHA。回退时停用后继并保留其失败/消费，不能恢复旧执行额度。

## 3. 确定性调度合同和受影响断言

1. 核准 core首正沿12500ps/周期25000ps及driver同相初值0的精确模型；此处仍为静态推导。输入计划、driver与M2源/ROM/include必须同版。不同模型先拒绝，不能调END或裁行凑合同。
2. finish只在指定实际core负沿置位，保持到capture_done；observer在每个实际正沿PRE_NBA采样。原始X/Z、异步reset初始/变化快照原样保留，同time epoch有歧义继续null/PENDING。
3. 保留 observer 的 `FROZEN_CAPTURE_WINDOW_REQUIRED`、`CAPTURE_SAMPLE_LIMIT`、`FINISH_NOT_AT_FROZEN_CORE_CYCLE`；不接受两个finish值作为“兼容”。如果选本提案，D行finish=0、D+1行为1、此前全0、此后无行。
4. END及唯一MONITOR_END必须与最后实际raw行的capture_id/cycle/time_ps/rows一致。MAX_CORE_SAMPLES必须严格大于所选finish；MAX_SIM_TIME_PS只为已批watchdog，不代表成功。旧1130676/28291500000仅为未批准上界提案。
5. 更新独立window、frame_input末epoch stop/finish、申请参数与argv、source/compile图及其SHA；唯一生产者仍为 `frame_plan_generator_candidate.py`。保留其来源及finish严格检查；source_identities供旧日历使用时恰为path/sha256两键，不改规则、不从raw FRAME反造期望。release802/1002482仍是待M2核准的源码推导，非实测。
6. 日历F/A分离、严格t−F<833且早于下一FRAME；TX833/834另核，startup/HOLD、ID0、取消后帧、同PCM异ID及三种clip/FX历史保留。末尾不完整serial half/frame继续UNKNOWN，计划结束不等于串行尾段完整。
7. `ready.drv`只驱动悬空诊断wire（TB95行），无法制造DUT背压。不得force ready或把driver辅助日志当实际接受；背压覆盖另由M2定范围。独立apply计划映射及audio_stable不填0、不用固定延迟补齐。

## 4. 当前完整 route 的实际边界与 M3 接缝遗漏

`capture_link_r01/entry.py`已具备PREPARE_APPLICATION_ONLY和PROCESS_CAPTURE分发；2026-10-18新增6例只证分发spy/拒收，不能再报“缺少分发入口”，也没有跑过完整route。冻结D4的114例结果仅复用原件。

| 现有路径 | 静态行为/边界 |
| --- | --- |
| entry.py:70–89 | 要求独立frame_input声明FROZEN、finish及timebase为整数、row_count=finish+1、END与window同一capture；缺项/错配拒收。该字符串不是M2审批凭证。 |
| entry.py:102–130 | PROCESS_CAPTURE交给固定D4 chain；输出限独占新目录；结果必须保持执行、真实、数学、板级标志false。 |
| D4 chain.py:68起 | 唯一FRAME生产者→raw转换/完整74字段CSV往返→intake/日历→TX/serial→ROM/机械math→provenance；完整窗口未调用。 |
| D4 provenance.py:108–151 | 全窗连续坐标、唯一finish、独立FRAME覆盖、唯一MONITOR_END与来源核同；origin仅合成或HDL_PUBLIC_CAPTURE_UNVERIFIED，始终不鉴真。 |

**可定位的完整原件接缝遗漏**：entry.required（67–68行）及D4 provenance.required（44–45行）没有实际execution_receipt/stderr这两个必需身份；D4 chain第147行将execution_receipt作为可选math角色，math_bundle缺它仍可返回MECHANICAL_INPUT_READY_MATH_PENDING。现状符合“机械候选不鉴真”的限定，但不足以形成R11要求的同次raw/reset/END/双流/退出/cleanup完整交接。不能把此限定结构成功升级真实完整capture。

最小后续修法应由总控串行认领：在获准的整链后继封套中增加同次receipt和stderr精确描述符，将source/输入/窗口/argv/cwd/env/工具/输出清单与它们绑定，入口和收尾都复核；核准receipt schema、exit/timeout/cleanup/日志水位及实际finish，缺失继续PENDING或在“完整原件”模式拒收；把双流实际本体纳入交接清单。只哈希批准字符串或把receipt交给机械math wrapper不构成可信执行证明。此处不改代码、不扩数学格式，也不建立执行器；可信执行权仍由M2另审。总控如已有后继，以其唯一写者继续，避免竞争。

raw中的72 ports已含i2s_bclk/lrck/din、pa_en、uart_tx，pins可用同一raw及行索引绑定；不虚构独立PINS文件。RESET_EDGES必须来自observer真实INITIAL/CHANGE记录，不能由逐行rst_n重建。工具stdout/stderr与退出/cleanup收据来自同一次可信执行器，不能用TB自报通过替代。当前上述真实原件全部NOT_CAPTURED/NOT_RUN。

## 5. 交付与恢复条件

本包写集仅本目录四份文档/JSON；无源码、TB、共享表、index、消费账或网络写入。SOURCE_BINDINGS保留现有原件和工具记录身份；商业工具本体不随仓库分发，其存在/哈希不代表已加载或动态闭包完整。EXECUTION_REQUEST列明决策、未获许可的参考argv和实际缺件，不是执行许可。

下一责任：夜间1汇总并用既有发布入口串行发布；M2批准精确finish后继及可信执行器/动态依赖/新HDL与完整处理预算；M3在新准入、冻结后继和同次实际材料齐后处理完整窗口；M1负责独立计划映射及实际PCM24/ID/clip数学。交接、M2最终复核、真实数字、数学、物理和上板分别记账。
