# M1 算法侧完整交付文档（T004/T009/T010/T023）

**日期**: 2026-09-24  
**交付人**: M1  
**基线**: develop 分支  
**对应任务**: T004 DDS、T009 ADSR、T010 声部管理、T023 混音器

---

## 一、交付总览

| 任务 | 状态 | Python模型 | 测试向量 | 边界测试 |
|------|------|-----------|---------|---------|
| T004 DDS | ✅ 完成 | dds_model.py | 5个测试文件 | 覆盖MIDI全音域 |
| T009 ADSR | ✅ 完成 | adsr_piano.py | 钢琴式包络 | 8项边界测试 |
| T010 声部管理 | ✅ 完成 | voice_manager.py | 4声部集成 | 窃取/重触发 |
| T023 混音器 | ✅ 完成 | mixer.py | 1000个向量 | D028临界点 |
| D031 逐帧向量 | ✅ 完成 | indexed_reference | 96000帧 | 11个关键帧 |

---

## 二、T004 DDS单声部

### 2.1 Python参考模型

**文件**: `code/model/dds_model.py`

**核心类**: `WavetableOscillator`
- 32位相位累加器
- 先取样后累加（第0样本相位为0）
- 1024点波表，相位截断查表
- 支持三种波形：sine, square, saw

**API接口**:
```python
osc = WavetableOscillator(table=sine_table, fcw=fcw)
wt_sample = osc.step()  # 返回16位有符号波表样本
```

### 2.2 测试向量

**目录**: `code/model/generated/dds_test/`

| 文件 | 内容 | 用途 |
|------|------|------|
| `dds_a4_440hz.txt` | A4单音1秒完整波形(48000样本) | 逐样本相位/波表对比 |
| `dds_midi_range.txt` | C0-C8每个八度C音(9音×16样本) | MIDI音域覆盖 |
| `dds_midi_range_summary.txt` | MIDI音符FCW对照表 | 频率误差验证 |
| `dds_phase_continuity.txt` | FCW切换测试(200→400→200Hz) | 相位连续性 |
| `dds_edge_cases.txt` | DC/最低音/最高音边界 | 极端情况稳定性 |

### 2.3 RTL验证要点

1. **相位累加验证**:
   - `phase[n+1] = (phase[n] + FCW) & 0xFFFFFFFF`
   - 首样本相位必须为FCW（先累加后取样）

2. **波表查表**:
   - 地址 = phase[31:22]（高10位）
   - 输出范围：[-8192, 8191]（WT_AMPLITUDE）

3. **FCW精度**:
   - A4(440Hz): FCW=0x0258bf26, 误差<0.000005Hz

---

## 三、T009 钢琴式ADSR包络

### 3.1 Python参考模型

**文件**: `code/model/adsr_piano.py`

**改进要点**:
1. **Sustain自然衰减**: 指数衰减每秒-15%，模拟钢琴弦自然衰减
2. **平滑Release**: 从当前电平计算斜率，电平变化<3 LSB
3. **Velocity映射**: 平方律响应，20%-100%幅度范围

**包络参数**:
| 阶段 | 时长 | 特性 |
|------|------|------|
| Attack | 5ms (240样本) | 线性上升到velocity峰值 |
| Decay | 100ms (4800样本) | 线性下降到40%电平 |
| Sustain | 持续 | 40%基准+指数衰减 |
| Release | 100ms (4800样本) | 从当前电平线性下降 |

**API接口**:
```python
env = PianoADSREnvelope()
env.note_on(velocity=768)  # 0-1023
level_q15 = env.step()      # Q1.15格式
output = apply_envelope(wt_sample, level_q15)
```

### 3.2 边界测试

**文件**: `code/model/tests/test_adsr_piano.py`

8项测试全部通过：
1. Velocity边界（0和1023）
2. Attack中途Release
3. Decay中途Release
4. 长时间Sustain衰减验证（2秒衰减25.9%）
5. Release重触发
6. 快速Note On/Off（10ms颤音）
7. 包络应用边界
8. IDLE状态

### 3.3 验证数据

```
Attack峰值: 32767 (velocity=1023)
Sustain开始: 13107 (40%电平)
Sustain 0.5s后: 12157 (自然衰减)
Release平滑性: 电平变化3 LSB (无啪声)
```

---

## 四、T010 声部管理

### 4.1 Python参考模型

**文件**: `code/model/voice_manager.py`

**核心类**: `VoiceAllocator`
- 4声部LRU(最久未用)分配
- 同音重触发返回原槽（不换槽）
- 声部窃取选择最旧时间戳

**API接口**:
```python
allocator = VoiceAllocator(num_voices=4)
slot = allocator.note_on(note_number)  # 返回0-3
slot = allocator.note_off(note_number) # 返回槽索引
```

### 4.2 集成测试

**文件**: `code/model/test_polyphony_integration.py`

测试场景：
1. **4声部复音**: C4-E4-G4和弦演奏，19200样本
2. **声部窃取**: 5音符→4槽，最老音符被替换
3. **同音重触发**: 验证返回原槽

**输出向量**: `code/model/generated/polyphony_test/polyphony_4voice.txt`
- 格式: `sample_idx pcm_hex pcm_dec voice0-3_active clipped`

---

## 五、T023 混音器与饱和限幅

### 5.1 Python参考模型

**文件**: `code/model/mixer.py`

**核心函数**: `mix_voices(voice_samples) -> (pcm, clipped)`
- 输入: 4个24位有符号PCM
- 累加器: 26位（足够4声部峰值）
- 饱和限幅: [-8388608, 8388607]
- 削波标志: True表示发生削波

### 5.2 测试向量

**目录**: `code/model/generated/mixer/`

| 文件 | 内容 |
|------|------|
| `mixer_inputs.txt` | 1000组输入(4×6位hex) |
| `mixer_outputs.txt` | 1000个输出(6位hex) |
| `mixer_clipped.txt` | 1000个削波标志(0/1) |

### 5.3 D028工作点验证

```python
# 单声部峰值不削波
[2097152] → 2097152, clipped=False

# 4声部同相位触发削波
[2097152]*4 → 8388607, clipped=True (饱和到PCM_MAX)

# 余量
4声部峰值约6.8M，余量1.84dB
```

---

## 六、D031逐帧黄金向量

### 6.1 生成器

**文件**: `code/model/generate_indexed_reference.py`

测试序列: 200/400/600/800 Hz四声部正弦，2秒

### 6.2 输出文件

**完整向量** (`indexed_reference.txt`, 96000行):
```
格式: frame pcm_hex pcm_dec phase0 phase1 phase2 phase3 voice0 voice1 voice2 voice3 clipped
示例: 0 000000 0 01111111 02222222 03333333 04444444 0 0 0 0 0
```

**精简向量** (`indexed_reference_compact.txt`, 11行):
关键帧: 0, 1, 10, 100, 240, 480, 2400, 4800, 24000, 48000, 95999

### 6.3 验证方法

```bash
# 提取帧1的相位
grep "^     1 " indexed_reference_compact.txt
# 输出: 1 080b00 527104 02222222 04444444 06666666 08888888

# 验证相位累加
phase[1] - phase[0] = 0x02222222 - 0x01111111 = 0x01111111 (FCW正确)
```

---

## 七、完整测试套件验证

### 7.1 模型测试

```
运行命令: python code/model/tests/run_all.py
结果: Ran 96 tests in 1.018s
状态: OK（全部通过）
```

包含：
- DDS模型测试（FCW转换、查表）
- 钢琴式ADSR边界测试（8项）
- 混音器临界点测试（D028工作点）
- RTL验证器测试（BOM检测、失配检测）

### 7.2 验证工具

**文件**: `code/model/rtl_verifier.py`

功能：
- 加载hex文件（支持0x前缀、注释）
- BOM检测（准确诊断UTF-8 BOM）
- 逐样本对比（PCM + 削波标志）
- 失败退出码（0=通过，1=失败）

使用示例：
```bash
python code/model/rtl_verifier.py
# 自动对比 rtl_outputs/mixer_rtl_outputs.txt 与参考
```

---

## 八、RTL实现指导

### 8.1 DDS实现要点

```systemverilog
// 相位累加器
always_ff @(posedge sys_clk) begin
    if (!sys_rst_n)
        phase_acc <= '0;
    else if (sample_tick)
        phase_acc <= phase_acc + fcw;
end

// 波表查表（BSRAM）
assign wt_addr = phase_acc[31:22];  // 高10位
assign wt_sample = sine_rom[wt_addr];  // 16位有符号
```

### 8.2 ADSR实现选项

**Sustain衰减**:
- 选项1: 查表（256点衰减系数LUT）
- 选项2: 近似（每100样本×0.997）
- 选项3: 线性（每样本-3，最简单）

**Velocity映射**:
- ROM查表: 1024×16位（推荐）
- Python生成脚本见交付文档

### 8.3 混音器实现

```systemverilog
// 26位累加器
logic signed [25:0] sum;
assign sum = voice0 + voice1 + voice2 + voice3;

// 饱和限幅
always_comb begin
    if (sum > PCM_MAX) begin
        pcm_out = PCM_MAX;
        clipped = 1'b1;
    end else if (sum < PCM_MIN) begin
        pcm_out = PCM_MIN;
        clipped = 1'b1;
    end else begin
        pcm_out = sum[23:0];
        clipped = 1'b0;
    end
end
```

---

## 九、文件清单

### 9.1 Python参考模型
```
code/model/dds_model.py               # T004 DDS模型
code/model/adsr_piano.py              # T009 钢琴式ADSR
code/model/voice_manager.py           # T010 声部管理
code/model/mixer.py                   # T023 混音器
code/model/audio_defs.py              # 公共常量定义
```

### 9.2 测试向量生成器
```
code/model/generate_dds_test_vectors.py        # DDS测试向量
code/model/generate_indexed_reference.py       # D031逐帧向量
code/model/generate_test_mode_reference.py     # T052测试模式
code/model/test_polyphony_integration.py       # 声部集成测试
```

### 9.3 生成的测试向量
```
code/model/generated/dds_test/                 # DDS 5个测试文件
code/model/generated/test_mode/                # 逐帧向量(96000帧)
code/model/generated/mixer/                    # 混音器1000组向量
code/model/generated/polyphony_test/           # 4声部集成向量
```

### 9.4 测试套件
```
code/model/tests/test_dds_model.py             # DDS测试
code/model/tests/test_adsr_piano.py            # ADSR边界测试
code/model/tests/test_mixer.py                 # 混音器测试
code/model/tests/test_rtl_verifier.py          # 验证工具测试
code/model/tests/run_all.py                    # 完整测试运行器
```

### 9.5 验证工具
```
code/model/rtl_verifier.py                     # RTL对比验证器
code/model/update_manifest.py                  # 生成物manifest工具
```

---

## 十、验收标准

### 10.1 功能完整性

- ✅ DDS支持MIDI 0-127全音域
- ✅ ADSR解决啪声/恒幅/velocity问题
- ✅ 4声部管理支持窃取和重触发
- ✅ 混音器D028临界点无溢出
- ✅ D031逐帧向量覆盖96000帧

### 10.2 测试覆盖

- ✅ 96项单元测试全部通过
- ✅ 边界测试覆盖极端情况
- ✅ 集成测试验证4声部协同
- ✅ 验证工具能检测失配

### 10.3 文档完整性

- ✅ 每个模块有API文档
- ✅ RTL实现指导含代码示例
- ✅ 测试向量格式说明清晰
- ✅ 验证方法步骤明确

---

## 十一、下一步工作

### M1待完成
- T052 4声部自证测试模式（已有Python参考）
- 第二音色支持（预留接口）
- 延迟效果器（W5任务）

### M2待完成
- T004 DDS RTL实现与波表BSRAM
- T009 ADSR RTL实现与Velocity ROM
- T010 声部管理RTL实现
- T023 混音器RTL实现
- 顶层集成与时序优化
- 上板验证钢琴式包络效果

### 验收里程碑
- [ ] RTL逐样本对比PASS（所有测试向量）
- [ ] 上板试听无啪声
- [ ] Velocity响应明显（轻重弹区分）
- [ ] 4声部和弦清晰无混叠
- [ ] T052频谱显示4个峰

---

**M1**  
2026-09-24

**附件**:
- M1_T009_piano_adsr_delivery.md（T009详细文档）
- M2_second_review_fixes.md（第二轮修复总结）
