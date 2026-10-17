# M1 R6-1 DSP 观察候选语义

本文件对应 `code/rtl/audio/m1_pro_observer_r06_20261017/` 中同名 bank、audio、chain 三份候选。仅增加显式观察输出与逐层连线，不新增 DSP 状态或控制，不修改算法、ROM、流水阶段、握手和取消条件。新增部分均在 `BEGIN M1_OBSERVER_R06` / `END M1_OBSERVER_R06` 成对注释之间；删除这些段应恢复所列来源全文。结构同一性检查及本批软件结果由主窗口统一留原始双流；本子任务没有执行测试、HDL 或 EDA。

## 原始来源

下表各文件均来自仓库目录 `code/docs/test/m3_r05_functional_integration_20261015/night_20261016/RESUME_R02/RUN_01/stage/inputs/sources/`。这是 R06 已封存运行输入，不能据其存在认定新 Pro top、目标器件或物理配置已匹配。

| 原文件 | SHA256 |
|---|---|
| `m1td_polyphonic_envelope_bank.sv` | `f1da9dfd870328d60723c67707d6af5d58466967d0ca9b3f6d48a8569b477cd7` |
| `m1td_audio_candidate.sv` | `6bc32ea435ca4b6f0132cbdbccafd0c54664becd75a393d8dff90aafc746ff25` |
| `m1td_timbre_delay_chain.sv` | `72c8e06b83fab7d5264a4ac79d27f33035da8ada509c4f59e4d8b658ee4641b5` |
| `m1td_stereo_delay.sv`（只读依赖） | `afba156c187520b03a9b422c3074d6fde48bfeceb590cafa5883b7037626da2a` |
| `m1td_delay_effect.sv`（只读依赖） | `07bcc6f4d0a448e029b5349a43fa8bcaa4afac32323bffb21fdc0e7c6a9633ac` |

## 统一采样沿

观察者在同一个 `clk` 上升沿的 **pre-NBA** 时刻记录观察口。组合观察口表示该沿即将被顺序逻辑消费的已有谓词或当前寄存器值；不得增加观察寄存器后仍沿用原发生沿编号。`rst_n` 异步拉低，释放由上游同步；真实复位边沿和 epoch 由独立采集合同处理，不从本观察口倒推出。

槽状态为 pre-NBA 当前状态；例如同沿有 `obs_retire_mask` 时，`obs_slot_occupied` 仍可能是清除前的值，清除后值到下一采样沿才能作为当前状态观察。以掩码事件与前后状态分别表达，不把 NoteOff、释放与退休合并。

## bank → audio → chain 同名透传

| 观察口 | 位宽 | bank 内真实来源及有效条件 |
|---|---:|---|
| `obs_slot_occupied` | 4 | `slot_occupied`；占槽包括 release 期间 |
| `obs_slot_releasing` | 4 | `slot_releasing`；仅已下发实际释放的槽为 1 |
| `obs_slot_note_on` | 4 | `slot_note_on`；该沿被 DDS/ADSR 消费的注册脉冲 |
| `obs_slot_note_off` | 4 | `slot_note_off`；该沿被 DDS/ADSR 消费的注册脉冲 |
| `obs_slot_sources` | 16 | `slot_sources`；lane i 为 `[4*i +: 4]` |
| `obs_slot_channels` | 16 | `slot_channels`；lane i 为 `[4*i +: 4]` |
| `obs_slot_notes` | 32 | `slot_notes`；lane i 为 `[8*i +: 8]`，实际 MIDI note 是零扩展 7 bit |
| `obs_slot_generations` | 128 | `slot_generations`；lane i 为 `[32*i +: 32]` |
| `obs_advance_mask` | 4 | `{4{lane_tick}}`；不以 occupied 筛选 |
| `obs_advance_frame_id` | 32 | `pending_req_id`；仅 `obs_advance_mask != 0` 时代表实际推进请求 |

原 `lane_tick = rst_n && !frame_tick && phase == ADVANCE && live_identity_matches`，四个 DDS 和四个 ADSR 均消费同一个 tick，包括未占用 lane。因此合法实际推进只出现 `0000` 或 `1111`，不可将四 lane 伪造为四个错开周期，也不可把 occupied mask 当推进掩码。ID 用 bank 已接收并保存的 `pending_req_id`，不使用可能已被后继 frame 更新的 `sample_req_id`。

原 bank 在 `IDLE` 接请求，或在 `DRAIN` 暂存下一请求，经过实际派发/控制/FCW 检查才进入 `ADVANCE`。本候选不改这些条件。推进 E 沿之后，原 `SNAPSHOT` 倒计数于 E+5 pre-NBA 捕获 wave/env；实际后处理输入接受以观察握手为准，不能把所有流量强行推定为固定请求偏移。

下列 router 观察口按 router 作者确定的原名和位宽逐层透传，不重新计算、不以 accept+1 生成应用事件：

| 观察口 | 位宽 | 责任边界 |
|---|---:|---|
| `obs_apply_valid` | 1 | router 实际应用谓词 |
| `obs_apply_data` | 64 | router 绑定的原始事件数据；不为无来源退休补旧数据 |
| `obs_apply_kind` | 4 | router 已区分的应用种类 |
| `obs_apply_mask` | 4 | router 当次应用目标 mask |
| `obs_apply_seq` | 32 | router 诊断序号 |
| `obs_apply_seq_valid` | 1 | router 对该序号关联的有效声明 |
| `obs_retire_mask` | 4 | router 实际退休谓词；不是 NoteOff mask |

router 新增的诊断序号状态及其定义属于独立 router 候选；这三份 DSP 透传文件不添加序号计数器、held event 或任何寄存器。源码同一性检查应分别检查 router 与 DSP 候选，不能用 DSP 透传证明代替 router 状态审查。

## chain 的效果输入观察口

| 观察口 | 位宽 | 原始来源 |
|---|---:|---|
| `obs_effect_input_valid` | 1 | `audio_valid`，接至 `u_post.input_valid` |
| `obs_effect_input_ready` | 1 | `audio_ready`，来自 `u_post.input_ready` |
| `obs_effect_input_id` | 32 | `audio_id`，接至 `u_post.input_id` |
| `obs_effect_input_left` | signed 24 | `audio_left`，四声部混音饱和后的左 PCM |
| `obs_effect_input_right` | signed 24 | `audio_right`，四声部混音饱和后的右 PCM |
| `obs_effect_input_clip` | 2 | `{audio_clip_right, audio_clip_left}`，bit0 左、bit1 右上游混音 clip |

只有 `valid && ready` 的上升沿是效果输入接受。输入 ready 原有条件为复位已释放、非 frame 沿、无 config_valid、非 busy、ID 等于 current_req_id，且同 ID 未被重复消费。只看 valid 不代表已消费，最终 commit 也不代表每次效果历史写入。

启用效果时，原后处理器在接受 E 沿发起运算，底层在 E+2 更新延迟缓存和原始效果输出，wrapper 于 E+3 NBA 保存可发布输出。frame 取消只取消发布资格，不撤销已接受历史。`config_enable == 0` 走直接 PCM 暂存旁路，不 clock 延迟历史。`obs_effect_input_clip` 为上游混音 clip；最终 `clipped_left/right = upstream_clipped_left/right OR effect_clipped_left/right`，反馈缓存 clip 单列，不并入最终 clip。

## config 打包提案

新增 `obs_config_take` 是现有外层 `config_valid && config_ready` 的组合别名，等价于内层 gated config 的实际接受；不增加接受机会、不更新配置。`config_ready = raw_config_ready && config_idle`，其中 `config_idle = audio_calc_ready && !audio_valid && !sample_req && !frame_tick`。内层还要求非 busy、复位已释放、非 frame 沿以及 `config_delay_samples < 1024`。

`obs_config_payload[61:0]` 仅为供 M2 确认的观察打包提案：

| 位段 | 原分量 | 定义 |
|---|---|---|
| `[61]` | `config_enable` | 1 bit；旁路/效果选择 |
| `[60:45]` | `config_delay_samples` | unsigned 16；实际接受范围 0–1023 |
| `[44:30]` | `config_dry_gain` | unsigned Q0.15，0–32767 |
| `[29:15]` | `config_wet_gain` | unsigned Q0.15，0–32767 |
| `[14:0]` | `config_feedback` | unsigned Q0.15，0–32767 |

打包口始终反映当前输入引脚，只有 `obs_config_take == 1` 的沿构成应用记录。复位默认 enable=0、delay=1、dry=32767、wet=0、feedback=0。enable 或 delay 在接受沿改变时，原 wrapper 对延迟器发出 flush；仅 gain 改变不 flush。此提案未批准为 M2 公共 trace 的最终位段合同，原控制端口保持原样。

## 装配与未验边界

新增三份候选仍使用原模块名。source-list 应以新候选路径替换旧三个同名文件，并同时选用带匹配观察端口的 M1 router 候选；不能同时编入旧文件造成重复模块。其余 DDS、ADSR、PitchMod、gain、mixer、stereo delay、delay effect 与 ROM 继续引用原冻结文件。M2 新 top/frame core/adapter 必须显式连接以上观察口并保持真实双 clip，M3 observer 只读取公开端口。

截至本文件编写，只有静态语义和候选源码，尚无本批 HDL 编译/仿真、真实 Pro 同版捕获、物理实现或板测。`board_release_allowed=false`；M2 包的 source-list/端口装配与最终 config 位段仍需绑定，不能以原 R06 SHA 代签新 Pro 身份。
