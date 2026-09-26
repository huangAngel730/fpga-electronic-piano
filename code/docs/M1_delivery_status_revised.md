# M1 算法侧交付状态说明（修订版）

**日期**: 2026-09-24  
**修订**: 响应M2复核反馈  
**基线**: develop 分支

---

## 一、交付状态总览

| 任务 | Python模型 | 测试向量 | RTL实现 | 备注 |
|------|-----------|---------|---------|------|
| T004 DDS | ✅ 已完成 | ✅ 5个测试文件 | ⏳ M1待交付 | Python参考已验证 |
| T009 ADSR | ✅ 已完成 | ✅ 钢琴式包络 | ⏳ M1待交付 | Python参考已验证 |
| T010 声部管理 | ✅ 已完成 | ✅ 4声部集成 | ⏳ M1待交付 | Python参考已验证 |
| T023 混音器 | ✅ 已完成 | ✅ 1000组向量 | ⏳ M1待交付 | Python参考已验证 |
| D031 逐帧向量 | ✅ 已完成 | ✅ 96000帧+完整链路 | N/A | 供RTL对比 |

**说明**: 
- ✅ 已完成：Python模型和测试向量已交付，96项测试通过
- ⏳ M1待交付：RTL实现由M1负责，待后续交付
- RTL实现责任与交付日期待负责人裁决

---

## 二、M2复核反馈修正项

### 2.1 ✅ 混音器累加器位宽说明

**修正前**: 注释提到"26位足够"可能引起误解  
**修正后**: 明确标注接口规范v1.2要求≥32位

`code/model/mixer.py`:
```python
#: 混音中间结果位宽（接口规范v1.2要求：不少于32位）
MIXER_ACCUM_BITS = 32

#: Python实现使用Python int（无位宽限制），但规格要求RTL必须用≥32位累加器
# 数学分析：4声部峰值 2097152 * 4 = 8388608 < 2^24，26位足够
# 但接口规范v1.2明确要求：累加器不少于32位
# RTL实现示例：logic signed [31:0] accumulator;
```

### 2.2 ✅ Release重触发幅度连续性测试

**问题**: Release中途重触发时电平从6530跳变到54（跳变6476）  
**原因**: 当前实现重触发总是从0开始Attack

**测试文件**: `code/model/test_adsr_release_retrigger.py`
```
Release中途电平: 6533
重触发后首样本: 54
电平跳变: 6479

[WARNING] 电平跳变过大: 6479
建议: Release重触发应从当前电平开始新Attack
```

**补充到边界测试**: `code/model/tests/test_adsr_piano.py` 测试5已更新，记录此现象

**决策选项**:
1. **保持当前行为**：钢琴物理特性就是重按会有明显的锤击感
2. **改为平滑重触发**：从当前Release电平开始新Attack（需修改adsr_piano.py）

待M1/M2决策后实施。

### 2.3 ✅ 完整链路带帧序号参考向量

**新增文件**: `code/model/generate_complete_reference.py`

生成包含ADSR/Velocity的完整音频链路参考：
- **完整向量**: `audio_chain_full.txt` (19200帧)
- **精简向量**: `audio_chain_compact.txt` (9个关键帧)

**格式** (完整):
```
frame pcm_hex pcm_dec phase0 phase1 phase2 phase3 wt0 wt1 wt2 wt3 env0 env1 env2 env3 voice0 voice1 voice2 voice3 clipped
```

**测试序列**:
- 0ms: C4(60) velocity=768 → 槽0
- 5ms: E4(64) velocity=640 → 槽1
- 10ms: G4(67) velocity=512 → 槽2
- 100ms: E4 Note Off
- 200ms: C4 Note Off
- 300ms: G4 Note Off

**RTL验证项**:
1. DDS相位累加和波表查表
2. ADSR包络状态机（Attack/Decay/Sustain/Release）
3. Velocity响应（不同velocity的包络峰值）
4. 包络调制（wt_sample × env_level）
5. 4声部混音累加
6. 饱和限幅和削波标志

---

## 三、Python模型验证状态

### 3.1 完整测试套件

```bash
运行命令: python code/model/tests/run_all.py
结果: Ran 96 tests in 1.018s
状态: OK（全部通过）
```

**测试覆盖**:
- DDS模型：FCW转换、查表、相位累加
- ADSR钢琴式包络：8项边界测试（含Release重触发）
- 混音器：D028临界点、削波标志
- RTL验证器：BOM检测、失配检测、退出码
- 波表生成：可重复性、SHA-256校验

### 3.2 生成的测试向量

**DDS测试** (`code/model/generated/dds_test/`):
- `dds_a4_440hz.txt` - A4单音1秒(48000样本)
- `dds_midi_range.txt` - MIDI音域测试
- `dds_phase_continuity.txt` - FCW切换
- `dds_edge_cases.txt` - 边界情况

**完整链路** (`code/model/generated/complete_reference/`):
- `audio_chain_full.txt` - 19200帧完整链路
- `audio_chain_compact.txt` - 9个关键帧

**混音器** (`code/model/generated/mixer/`):
- `mixer_inputs.txt` - 1000组输入
- `mixer_outputs.txt` - 1000个输出
- `mixer_clipped.txt` - 削波标志

**逐帧向量** (`code/model/generated/test_mode/`):
- `indexed_reference.txt` - 96000帧
- `indexed_reference_compact.txt` - 11关键帧

---

## 四、RTL实现指导（M1待交付）

### 4.1 T004 DDS实现要点

```systemverilog
// 32位相位累加器
logic [31:0] phase_acc;

always_ff @(posedge sys_clk) begin
    if (!sys_rst_n)
        phase_acc <= '0;
    else if (sample_tick)
        phase_acc <= phase_acc + fcw;  // 自然回绕
end

// 波表查表（建议BSRAM）
assign wt_addr = phase_acc[31:22];  // 高10位
assign wt_sample = sine_rom[wt_addr];  // 16位有符号
```

### 4.2 T009 ADSR实现要点

状态机：IDLE → ATTACK → DECAY → SUSTAIN → RELEASE → IDLE

**Sustain指数衰减**选项:
1. 查表法：256点LUT
2. 近似法：每100样本×0.997
3. 线性法：每样本-3（最简单）

**Velocity映射**：1024×16位ROM查表

### 4.3 T023 混音器实现要点

```systemverilog
// ≥32位累加器（接口规范v1.2要求）
logic signed [31:0] accumulator;

always_comb begin
    accumulator = voice0 + voice1 + voice2 + voice3;
    
    if (accumulator > PCM_MAX) begin
        pcm_out = PCM_MAX;
        clipped = 1'b1;
    end else if (accumulator < PCM_MIN) begin
        pcm_out = PCM_MIN;
        clipped = 1'b1;
    end else begin
        pcm_out = accumulator[23:0];
        clipped = 1'b0;
    end
end
```

---

## 五、文件清单

### 5.1 Python参考模型
```
code/model/dds_model.py               # T004 DDS
code/model/adsr_piano.py              # T009 钢琴式ADSR
code/model/voice_manager.py           # T010 声部管理
code/model/mixer.py                   # T023 混音器（已修正注释）
```

### 5.2 测试向量生成器
```
code/model/generate_dds_test_vectors.py        # DDS测试
code/model/generate_indexed_reference.py       # D031逐帧
code/model/generate_complete_reference.py      # 完整链路（新增）
code/model/test_polyphony_integration.py       # 声部集成
```

### 5.3 边界测试
```
code/model/tests/test_adsr_piano.py            # ADSR 8项测试（已更新）
code/model/test_adsr_release_retrigger.py      # Release重触发（新增）
code/model/tests/test_mixer.py                 # 混音器D028测试
code/model/tests/test_rtl_verifier.py          # 验证工具测试
```

### 5.4 验证工具
```
code/model/rtl_verifier.py                     # RTL对比验证
code/model/update_manifest.py                  # manifest管理
```

---

## 六、待决策事项

### 6.1 RTL实现责任与交付日期

**问题**: 交付文档将T004/T009/T010/T023的RTL全部列为"M2待完成"  
**现状**: 与既定分工不一致  
**请求**: 负责人明确裁决RTL实现责任归属和交付时间表

### 6.2 Release重触发策略

**问题**: Release中途重触发电平跳变6479 LSB  
**选项A**: 保持当前（从0开始Attack），符合钢琴物理特性  
**选项B**: 从当前电平开始Attack，更平滑

**当前测试**: 选项A实现，测试记录了此现象  
**请求**: M1/M2决策后实施

---

## 七、后续工作

### M1待完成
- [ ] T004/T009/T010/T023 RTL实现（待裁决责任归属）
- [ ] Release重触发策略决策和实施
- [ ] T052 4声部自证测试模式

### M2待完成
- [ ] 复核完整链路参考向量
- [ ] 顶层集成时序
- [ ] 上板验证

---

**M1**  
2026-09-24

**注**: 本文档已根据M2复核反馈修正，后续上传GitHub前将征得M2同意。
