# M1-B：视觉接入音频不退化的软件比较合同（2026-10-16）

本包完成现行 `M1_完赛任务单_2026-10-15.md` §2026-10-16 B 所授权的软件准备：同一事件、时钟和冻结窗口下，对接入前后两份导出帧合同逐行比较。实际视觉候选的前后原始流尚未收到，`REAL_RESULT=PENDING_REAL_CAPTURE`；不签视觉“不退化”、整链、CDC、STA、I2S、模拟音频、deadline 或板级通过，`board_release_allowed=false`。

只新增 `code/model/m1_visual_audio_guard_20261016/` 与本目录。未触及正式 RTL、top、约束、M3 显示/observer/CDC 或旧证据。交付由主窗口统一发布，本子任务不写 Git。

## 已绑定的 A 基线与合成事件范围

M1-A 的 `code/docs/test/m1_r05_pcm_oracle_20261016/REFERENCE_CONTRACT.json` 是本包 `--basis`，实际 SHA-256 为 `f7373c1be0d70b9bb45800738b8a992efadd854c1cb1aecf82910f3644cf091e`。该合同指向 R06 输入 ZIP `4be2b4c185691a3e493827a3a95303fa90f49ba6336eb4a8e0183942c8f05483`、40 MHz / 48 kHz 及 `SYNTHETIC_SETTLED_EVENT_CALENDAR`，自身真实结果仍待捕获。

B 不重算 A 的四声部算术，不把合成 PCM 符号冒充 A/RTL 输出。B 的 `synthetic_events.json` 专用于复位/活动窗口身份及比较反例，按本文件实际字节另算事件 SHA；它与 A 的 settled-event 样例不是同一事件日历，不能借此拼接算法或真实链通过。把 A 的 SHA 绑定到 B 只证明引用同一份已核数学合同；相等比较并不独立证明数学正确。

## 两份帧输入

根对象要求下列**精确键集**，不接受额外键、漏键、重复键、NaN、Infinity 或布尔值冒充整数：

```text
schema = M1_VISUAL_AUDIO_FRAMES_V1
source_kind = SYNTHETIC_FRAME_CONTRACT_ONLY | REAL_CAPTURE_DERIVED
clock_hz = 40000000
sample_rate_hz = 48000
input_events_sha256 = 64位小写十六进制SHA
basis_sha256 = A合同实际文件SHA
window = { first_cycle, last_cycle, expected_frames }
frames = [ frame_row, ... ]
```

`source_kind` 是来件声明，软件不能认证真实捕获；两流必须一致，禁止合成与真实互拼。所有 cycle、frame、epoch、序号与计数为非负整数；`expected_frames >= 1`。窗口首尾 cycle 为包含边界，期望帧数不得超过其包含的时钟周期数。设计采样率不是实际采样率测量结果。

每行的精确字段如下：

| 字段 | 明确定义与软件校验 |
|---|---|
| `epoch`, `frame` | 此选定窗口从 `(0,0)` 开始；进入低复位时 `epoch` 恰加 1、`frame` 归零，其余行同 epoch 且 frame 恰加 1。它们是导出合同的相对索引；原 trace 帧号/复位来源必须另交映射原件。 |
| `cycle` | 同一 40 MHz 绝对 cycle 原点下的**帧采样边界**，该行代表已经提交后在此边界可见的 PCM，严格递增。第一/末行必须落在冻结窗口边界。 |
| `rst_n` | 整数 0/1。复位行必须 `commit_seq=0`、ID/commit_cycle 为 null、左右 PCM/underflow/clip_count 清零。 |
| `commit_seq` | 本 epoch 的非负累计发布序号，每行只能保持或加 1。不能跳号或回退。零序号没有提交身份且 PCM 必须为 0。 |
| `commit_id` | 非负整数或 null，标识此行最近一次发布。新发布 ID 在同 epoch 必须递增；允许被取消的其他事务造成 ID 间隙。保持序号时 ID、commit_cycle 和 PCM 必须保持。真实 ID 来源与取消规则须由 M2/M3 给出。 |
| `commit_cycle` | 非负整数或 null。最近一次发布的绝对 cycle，不晚于本行 cycle；新发布必须晚于上一行采样边界。窗口第一行允许已有一次已提交的活动状态。 |
| `pcm_left`, `pcm_right` | 十进制有符号 PCM24，范围 `[-8388608, 8388607]`。前后逐样本零容差；不接受 float、bool 或字符串。 |
| `underflow` | 该观察帧欠载标记，整数 0/1，不是累计数。逐帧完全相等；已有且两流一致的欠载会原样保留，不因比较相等写成无欠载。新增/消失的标记均拒收。 |
| `clip_count` | 此 epoch 非负累计削波计数，非复位进入时不能回退；不限制每帧增量，避免擅自假设削波计数口径。前后必须逐帧相等。实际计数点仍按 A/M2 已冻结口径映射。 |

两个连续活动帧的 cycle 差只能为 833/834；每连续三个活动间隔之和为 2500，复位进入/释放处重新开始这项检查。这个检查只保护所选导出格式中设计节拍的连续性，不能替代实际请求/完成/下一帧账本，`deadline_result=NOT_EVALUATED_BY_THIS_CONTRACT`。窗口至少含一个活动且有提交的帧，拒绝空窗或全复位“通过”。

本格式是尚待真实数据字段映射的**软件合同**。如果实际导出采样相位、序号、欠载或复位语义不同，应先由 M1/M2/M3核定映射或合同增量，不能为了让来件通过而临时改帧号/丢帧/重采样/缩窗。特别是样本采样在提交之前的原 trace，不能直接套用本合同的 `commit_cycle <= cycle`。

## 独立比较合同与拒收行为

为防止两流同时截尾、同时篡改自报窗口，CLI 还要求执行前冻结的独立对象：

```text
schema = M1_VISUAL_AUDIO_COMPARE_CONTRACT_V1
clock_hz, sample_rate_hz, input_events_sha256, basis_sha256
window = { first_cycle, last_cycle, expected_frames }
```

该对象由实际获准的采集/比较范围填写，不能只复制待测流的自报值。软件核独立合同与实际 A 文件 SHA，核两流与独立合同的事件/时钟/窗口，再核行数、首尾、连续索引/复位及上述数值约束，最后按 `(epoch,frame)` 和 cycle 对齐比较所有行字段。

独立合同是调用者提供的信任锚，不是本软件替 M2 批准的运行许可。事件 SHA 必须对应真实输入/已接受事件日历的原件，软件本身不生成和认证这些硬件事件。

相等退出 0，输出 `FRAME_CONTRACT_EQUAL`、`L0_SOFTWARE_FRAME_CONTRACT`、零 LSB 容差、A/事件身份、选定窗口、各输入实际 SHA，并固定 `visual_audio_nondegradation=NOT_SIGNED_BY_THIS_SOFTWARE`。合成输入结果为 `PENDING_REAL_CAPTURE`；自报真实的输入仍为 `PENDING_RAW_CAPTURE_AND_M2_IDENTITY_REVIEW`。严格拒收退出 2；拒收不写成功 JSON。输出独占创建，已有输出/输入路径拒收，不覆盖原件。CLI 用同一次读取的字节做解析和摘要，并在写输出前核输入未变。

## 本轮软件验证与失败史

原始逐例材料放 `selftest_R01/<case>/`：before/after/独立合同 JSON、原始 `stdout.bin`/`stderr.bin`、实际 argv/cwd/退出码/耗时和每文件 SHA 的 `receipt.json`。总收据为 `selftest_R01/SELFTEST_SUMMARY.json`；最外层有原始 unittest 双流与启动收据。精确用例数、通过/拒收数、执行时间和实际失败史以这些运行原件及本目录 `软件验证回执_R01.md` 为准。

定向覆盖完整一致、已存在且一致的欠载、缺首/中/尾、双流同时缩窗、错帧/重复帧/复位 epoch、PCM 左右/符号边界、提交 ID/序号/周期、削波回退、事件/基线身份、833/834 节拍、严格 JSON/类型和已有输出保护。合成一致不能提升为视觉实际无退化。

## 真实前后流到件时还须交什么

1. M2 精确同版的接入前/后候选源码、ROM、top、CST/SDC、工具与码流 SHA；正式准入/比较范围另按现行权限执行。
2. 两份未经截短的原始公开 trace/capture 文件与 SHA、实际执行命令/工具/退出码、完整窗口及计划预期帧数；有失败保留首失败。
3. 同一真实事件原件与已应用事件 cycle、共同 cycle 原点、每次实际复位、帧号重编号映射、导出采样相位及 commit ID/序号/欠载/削波字段来源。字段不足就缺件拒收或保持待验，不能推断为零。
4. M3 将可公开观察的字段映射到本软件合同；本包不代写其采集/observer/CDC 工具，不自行改 M2 TB 或运行新 ModelSim。

这四类原件当前未齐。真实音画结论、逐请求 deadline、板测、实屏与板级时延均待原岗位接续；后续波形/最小传谱/N32不因本包软件完成而提前启动。
