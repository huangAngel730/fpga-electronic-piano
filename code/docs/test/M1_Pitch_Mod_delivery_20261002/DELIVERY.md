# M1 Pitch / Mod 算法交付（2026-10-02）

源基线 **0e29e22**（M1 T027/Pitch/Mod/T028 离线工作包）。本轮只做任务书
**第二阶段 Pitch Bend + Modulation 的算法模块与接口合同**，不含 T028。

对应 M2 通知：M2 已完成 `performance_control_state`（控制保存/四槽绑定/快照），
M2 明确"M1 只提供 base_FCW + signed12 bend + unsigned12 mod + range 的算法模块与
sample_enable/latency 合同，本轮不替 M1 发明 LFO 深度/波形或定点乘法口径"。
本包即为该算法模块与合同。**未重写顶层/接口/CST/ADSR/音色**。

---

## 交付物

| 文件 | 操作 | 说明 |
|---|---|---|
| `code/model/pitch_mod_model.py` | add | 黄金模型（纯标准库，无 numpy） |
| `code/model/generate_pitch_mod_luts.py` | add | 生成三张 LUT 的 .mem |
| `code/model/generate_pitch_mod_vectors.py` | add | 生成 6 万余条黄金向量 |
| `code/model/test_pitch_mod.py` | add | 25 项自检，任一失败非零退出 |
| `code/model/check_rtl_equivalence.py` | add | 按 RTL 位宽语义复刻并与向量逐条比对 |
| `code/rtl/audio/pitch_mod_fcw.sv` | add | 可综合 Pitch+Mod FCW 控制器 |
| `code/tb/audio/tb_pitch_mod_fcw.sv` | add | 自检 TB，读向量逐样本比对，失败 $fatal |
| `code/scripts/run_pitch_mod_tests.py` | add | 一键运行器（含可选 iverilog） |
| `code/docs/test/Pitch_Mod_算法接口合同_2026-10-02.md` | add | **M2 接线所需的接口合同** |
| `code/model/generated/pitch_mod/*.mem` | add | OCT/SUB/LFO 三表 |
| `code/model/generated/pitch_mod/pitch_mod_vectors.txt` | add | 62273 条向量 |

## 数学 / 位宽 / 舍入 / 饱和

分辨率 **Q10 半音**（0.098 音分/LSB），见合同文档第 2 节。核心：

```
semi_q10  = (bend * range) >>> 1
depth_q10 = (mod * 512 + 2048) >>> 12
vib_q10   = (lfo_q15 * depth_q10) >>> 15
total_q10 = semi_q10 + vib_q10
factor_q16 = (OCT[total>>>10 + 25] * SUB[total & 0x3FF]) >> 16
fcw = saturate((base_fcw * factor_q16 + 32768) >> 16, 0, 2**31)
```

- 符号：`bend` signed12 补码；`modulation/pitch_range/base_fcw` 无符号。
- 舍入：OCT/SUB 生成时各舍入一次；中间乘积截断；仅最后一步四舍五入。
- 饱和：`fcw > 2**31` 饱和到 `2**31`（24 kHz = DDS 奈奎斯特），**不回绕**。

## 输入更新 / 输出 latency

- `sample_enable` 每音频采样**一个脉冲**，LFO **每脉冲只推进一次**。
  **不得接 `snapshot_valid`（那是保持电平）**——误接会使颤音频率偏 ~1042 倍。
- 本模块**不需要 ready**：纯前馈 + 1 级寄存器，下游 ready 不可能重推 LFO。
- latency：本拍采样 → 下个 `sys_clk` 出 `fcw_out`，即 **1 个 sys_clk（20 ns）**。
- `note_on` 与 `sample_enable` 同拍：note_on 优先，相位按 0 读，寄存器置 `LFO_INC`，
  新音符**从精确 base 音高起振**且本拍只推进一次。

## 运行命令与实测结果

```powershell
python -X utf8 code/scripts/run_pitch_mod_tests.py
```

| 步骤 | 结果 | 退出码 |
|---|---|---|
| LUT 生成 | PASS（50+1024+1024 项） | 0 |
| 黄金模型自检 | **25 checks, 0 failures** | 0 |
| 向量生成 | PASS（162 用例，62273 条） | 0 |
| RTL 语义等价 | **62273 vectors, 0 mismatches** | 0 |
| Icarus TB | SKIP（本机无 iverilog），已随包交 M2 | — |

日志：`logs/all_tests.log`。报告：`code/model/generated/pitch_mod/model_report.json`。

### 关键实测指标

| 指标 | 实测 | 阈值 |
|---|---|---|
| 精确旁路最大偏移（bend0/range0/mod0） | **0 LSB** | 0 |
| 全网格最坏音高误差 | **0.137 音分** | <0.2（可闻阈 5–10 音分的 1/40） |
| 单调性反转 | **0** | 0 |
| mod=4095 峰值深度 | **+50.0 音分** | 提案 ±0.5 半音 |
| 颤音周期 | **9600 采样 = 5.0 Hz** | 提案 |
| Nyquist 边界 | fcw ≤ 2³¹，恒正 | 不回绕 |
| r∈[0,24] 全 range 最坏 | 0.074 音分 | <0.1 |

## 验证等级（按任务书口径）

- **L1**：模型逻辑自测 —— 已做。
- **L3**：模型逐样本对照 —— 已做（RTL 语义复刻 vs 黄金模型 62273 条全量）。
- **L2**：真实 TB 仿真 —— **未做**，本机无 iverilog/verilator；
  TB 与向量已随包，M2 在有仿真器处运行即可（运行器自动探测）。
- **L4/L5**：综合/PnR/上板 —— **未做**，M2 负责；本包无 Gowin 报告。

**未拿 RTL 语义复刻冒充真实仿真。** 复刻只能证明"源码按写的位宽语义与模型一致"，
不能替代真实 TB（可捕捉 X 传播、复位时序、工具语义差异）。

## 负向 / 边界用例

- 重置：async reset 清 `fcw_out` 与 LFO 相位；TB 显式检查。
- `range==0` 任意 bend、`mod==0` 任意 mod：逐位旁路，已测。
- 最高音 + 最大 range + 最大 mod：饱和不回绕，不出现负 FCW。
- 重触发：LFO 偏离 0 后 note_on 精确回 base（对照不置 note_on 则不等）。
- 向量文件若格式错误，TB 计为失败并 `$fatal`；模型测试任一失败返非零。
- `.mem` 与模型表**逐项相等**（防生成器与 RTL 漂移）。

## 尚未做 / 待定

- 综合/PnR/STA/上板（M2）。**资源预估待 M2 实测**：三表建议 BSRAM，预计 ≤3 块，0 DSP。
- **待用户冻结**：`MOD_LFO_HZ=5.0`、`MOD_DEPTH_MAX_Q10=512`（±50 音分）。
  属 M1 提案，改动只影响这两个参数。
- 未定义 Portamento（未授权）。
- MIDI 解码/限速/合并（M3）、身份 source/channel 绑定与路由（M2）。
- 未改 `dds_oscillator.sv`/`note_pitch.sv`/ADSR/音色/CST/top/GPRJ。

## 涉及公共接口的待定问题（M2 走受控发布）

1. **三张新 LUT 的存放路径与 ROM 参数**：本包给 `code/model/generated/pitch_mod/`，
   M2 可迁入正式路径；RTL 已用参数化 `OCT_FILE/SUB_FILE/LFO_FILE` 与
   `+OCT_PATH/+SUB_PATH/+LFO_PATH` 覆盖，改路径无需改逻辑。
2. **本模块是新增独立模块**，不改任何已冻结端口；接线位置（DDS 之前）与
   每槽是否需要独立实例属 M2 实施，本包不预设层次。
3. **`pitch_range` 默认 2** 与接口规范一致；`bend`/`mod` 位宽直接对应
   `performance_control_state` 的 `slot_pitch_bend/slot_modulation`，无位宽转换。

---
作者：M1。基线 0e29e22。本包为源码快照，不含 Git 元数据。
跨岗位正式交接须用户私发，本文件仅记录，不代表已送达。
