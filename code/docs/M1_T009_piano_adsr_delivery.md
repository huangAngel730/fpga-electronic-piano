# M1 T009钢琴式ADSR包络交付文档

**日期**: 2026-09-24  
**交付人**: M1  
**基线**: develop 分支  
**对应任务**: T009 ADSR包络生成器增强版

---

## 一、问题背景

M2上板试听发现三个问题：
1. **按住时恒幅持续响** - 不符合钢琴自然衰减特性
2. **松键有明显"啪"声** - Release从固定电平跳变导致
3. **轻重弹音量基本相同** - 未实现Velocity到幅度映射

---

## 二、解决方案

### 2.1 钢琴式包络设计

**新包络特性**（`adsr_piano.py`）：

| 阶段 | 时长 | 特性 |
|------|------|------|
| **Attack** | 5ms (240样本) | 快速起音，线性上升到velocity峰值 |
| **Decay** | 100ms (4800样本) | 快速衰减到40%电平 |
| **Sustain** | 持续 | 保持40%电平并**缓慢指数衰减**（每秒-15%） |
| **Release** | 100ms (4800样本) | **从当前电平**平滑释放到0 |

**关键改进**：
1. Sustain阶段使用指数衰减：`level *= 0.999996875`（每采样）
2. Release从当前电平计算斜率，避免跳变
3. Velocity使用平方律映射，符合人耳感知

### 2.2 Velocity映射

```python
gain = 0.2 + 0.8 × (velocity / 1023)²
```

| Velocity | 增益(Q1.15) | 相对幅度 |
|----------|-------------|----------|
| 0        | 6553        | 20%      |
| 256      | 8194        | 25%      |
| 512      | 13119       | 40%      |
| 768      | 21327       | 65%      |
| 1023     | 32767       | 100%     |

最轻触键保留20%幅度，避免完全静音。

---

## 三、交付文件

### 3.1 Python参考模型

**`code/model/adsr_piano.py`** - 钢琴式ADSR包络生成器
- `PianoADSREnvelope` 类：包含完整ADSR状态机
- `velocity_to_gain(velocity)` 函数：Velocity映射
- `apply_envelope(sample, envelope)` 函数：包络应用
- 自检测试覆盖完整ADSR循环和Velocity响应

**API接口**：
```python
env = PianoADSREnvelope()
env.note_on(velocity=768)  # velocity范围0-1023
level_q15 = env.step()      # 每采样调用，返回Q1.15电平
env.note_off()              # 触发Release

# 应用到波表样本
output = apply_envelope(wt_sample_s16, level_q15)
```

### 3.2 边界测试

**`code/model/tests/test_adsr_piano.py`** - 8项边界测试
1. Velocity边界值（0和1023）
2. Attack阶段提前Release
3. Decay阶段提前Release
4. 长时间Sustain自然衰减验证（2秒）
5. Release阶段重触发
6. 快速连续Note On/Off（颤音，10ms周期）
7. 包络应用边界（最大/最小样本）
8. IDLE状态行为

**全部通过**，无边界异常。

### 3.3 带帧序号黄金向量

**`code/model/generate_indexed_reference.py`** - D031逐帧规则黄金向量生成器

生成两个文件：
- **`indexed_reference.txt`** (96000行) - 完整逐帧数据
  - 格式: `frame_idx pcm_hex pcm_dec phase0-3 voice0-3 clipped`
- **`indexed_reference_compact.txt`** (11行) - 关键帧精简版
  - 帧0, 1, 10, 100, 240, 480, 2400, 4800, 24000, 48000, 95999

**用途**：
- RTL逐帧对比验证DDS相位累加
- 验证混音器饱和限幅
- 定位失配帧的具体样本

**关键帧说明**：
- 帧0: 验证FCW加载和初始相位
- 帧1: 验证首次相位累加逻辑
- 帧240 (5ms): ADSR Attack典型时间
- 帧48000 (1.0s): 长期频率精度

---

## 四、验证结果

### 4.1 功能验证

**钢琴式ADSR自检**：
```
Attack峰值: 32767 (velocity=1023)
Decay结束: 13107 (40%电平)
Sustain开始: 13102
Sustain 0.5s后: 12157 (自然衰减7.2%)
Release结束: 0
```

**平滑Release验证**：
```
Note Off前电平: 13066
Release首样本: 13063
电平变化: 3 (<100, 无啪声)
```

### 4.2 边界测试

```
运行命令: python code/model/tests/test_adsr_piano.py
结果: [PASS] 全部边界测试通过
```

### 4.3 完整测试套件

```
运行命令: python code/model/tests/run_all.py
结果: Ran 96 tests in 1.018s - OK
状态: 全部通过
```

### 4.4 逐帧向量验证

```
运行命令: python code/model/generate_indexed_reference.py
生成: 96000帧完整向量 + 11个关键帧
相位累加验证: 前10帧全部PASS (phase[n+1] - phase[n] == FCW)
```

---

## 五、RTL实现指导

### 5.1 状态机

```systemverilog
typedef enum logic [1:0] {
    IDLE,    // 静音，level=0
    ATTACK,  // 线性上升
    DECAY,   // 线性下降到sustain
    SUSTAIN, // 指数衰减
    RELEASE  // 线性下降到0
} adsr_state_t;
```

### 5.2 关键寄存器

```systemverilog
logic [15:0] envelope_level;    // Q1.15当前电平
logic [15:0] velocity_gain;     // Q1.15 velocity映射增益
adsr_state_t state;
logic [15:0] counter;           // 当前阶段计数器
```

### 5.3 Sustain指数衰减实现

**选项1：查表**
- 预计算256个衰减系数，用高8位索引
- `level_next = (level * decay_lut[level[15:8]]) >> 16`

**选项2：近似**
- 每N个样本乘以固定系数（如每100样本×0.997）
- 误差<1%，节省乘法器

**选项3：简化线性**
- 每采样减去固定小量：`level -= 3`
- 最简单，但不是严格指数

M2可根据资源预算选择。Python参考使用严格指数，RTL允许近似。

### 5.4 Release平滑处理

```systemverilog
// Note Off时计算Release斜率
if (note_off && state != IDLE) begin
    release_slope <= envelope_level / RELEASE_SAMPLES;
    state <= RELEASE;
    counter <= 0;
end

// Release阶段
if (state == RELEASE) begin
    if (envelope_level > release_slope)
        envelope_level <= envelope_level - release_slope;
    else begin
        envelope_level <= 0;
        state <= IDLE;
    end
end
```

### 5.5 Velocity映射

**ROM查表方案**（推荐）：
- 1024×16位ROM，存储预计算的gain值
- `velocity_gain <= velocity_lut[event.velocity]`
- Python生成脚本：
```python
for v in range(1024):
    gain = int(32767 * (0.2 + 0.8 * (v/1023)**2))
    print(f"{gain:04x}")
```

---

## 六、逐样本对比向量

### 6.1 使用方法

**验证DDS相位累加**：
```bash
# 提取关键帧相位
grep "^     0 " indexed_reference_compact.txt  # 帧0
grep "^     1 " indexed_reference_compact.txt  # 帧1

# 验证: phase[1] - phase[0] == FCW
```

**验证混音器**：
```bash
# 提取PCM输出
awk '{print $2}' indexed_reference.txt > pcm_ref.hex

# RTL对比
python code/model/rtl_verifier.py
```

### 6.2 文件格式

**完整向量** (`indexed_reference.txt`)：
```
# frame pcm_hex pcm_dec phase0 phase1 phase2 phase3 voice0 voice1 voice2 voice3 clipped
0 000000 0 01111111 02222222 03333333 04444444 0 0 0 0 0
1 080b00 527104 02222222 04444444 06666666 08888888 131072 262144 393216 524288 0
```

**精简向量** (`indexed_reference_compact.txt`)：
```
# frame pcm_hex pcm_dec phase0 phase1 phase2 phase3
0 000000 0 01111111 02222222 03333333 04444444
1 080b00 527104 02222222 04444444 06666666 08888888
```

---

## 七、下一步工作

### M1待完成
- [ ] T004 DDS单声部RTL（基于现有Python模型）
- [ ] T010 声部管理Python模型集成钢琴式ADSR
- [ ] T023 混音器Python模型已完成，待RTL对齐

### M2待完成
- [ ] T009 ADSR RTL实现（基于本文档）
- [ ] 上板验证钢琴式包络效果
- [ ] 集成Velocity映射到事件处理

### 验收标准
1. RTL ADSR输出与Python参考逐样本一致（tolerance=1 LSB）
2. 上板试听无"啪"声
3. Velocity响应明显（轻重弹音量区分）
4. 长按音符自然衰减

---

## 八、文件清单

```
code/model/adsr_piano.py                          # 钢琴式ADSR Python实现
code/model/tests/test_adsr_piano.py                # 边界测试（8项）
code/model/generate_indexed_reference.py           # D031逐帧向量生成器
code/model/generated/test_mode/indexed_reference.txt          # 完整向量(96000帧)
code/model/generated/test_mode/indexed_reference_compact.txt  # 精简向量(11帧)
```

---

**M1**  
2026-09-24
