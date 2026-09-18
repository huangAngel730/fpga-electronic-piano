# T009 ADSR 包络设计

**任务**: T009 ADSR参考和RTL  
**主负责人**: M1  
**分担**: M2（流水线、资源优化）  
**周次**: W3（已逾期）  
**版本**: v1.0  
**日期**: 2026-09-18  

---

## 一、目标

1. 消除按键咔哒声（V0038问题：0→满幅跳变）
2. 定义ADSR包络数学（时间常数、曲线形状）
3. 提供Python参考实现

---

## 二、ADSR定义

### 2.1 四个阶段

```
幅度
  ↑
1.0├─╱╲___________
   │╱A │D    S    │R╲
0.0└──────────────────→ 时间
    ↑NoteOn    ↑NoteOff
```

- **Attack (A)**: Note On后，从0线性上升到峰值1.0
- **Decay (D)**: 从峰值1.0线性下降到Sustain电平
- **Sustain (S)**: 保持在固定电平（按住期间）
- **Release (R)**: Note Off后，从当前电平线性下降到0

### 2.2 参数定义（M1定义权）

| 参数 | 值（样本数@48kHz） | 时间 | 说明 |
|------|-------------------|------|------|
| Attack | 480 | 10ms | 快速起音，避免咔哒 |
| Decay | 2400 | 50ms | 适中衰减 |
| Sustain Level | 0.75 | 75% | 保持电平 |
| Release | 4800 | 100ms | 自然释音 |

**曲线**: 全部使用线性（简化RTL实现，音质可接受）

---

## 三、定点格式

### 3.1 包络幅度表示

- **格式**: Q1.15（16位有符号定点数）
- **范围**: 0.0 ~ 1.0 映射到 0 ~ 32767
- **Sustain电平**: 0.75 × 32767 = 24575

### 3.2 斜率计算

```python
# Attack: 0 → 32767 in 480 samples
attack_slope = 32767 / 480 ≈ 68.26 → 68 (整数)

# Decay: 32767 → 24575 in 2400 samples  
decay_slope = (32767 - 24575) / 2400 ≈ 3.41 → 3

# Release: 当前电平 → 0 in 4800 samples
release_slope = current_level / 4800
```

---

## 四、状态机

```
      ┌─────┐ NoteOn
      │ IDLE│────────→┌────────┐
      └─────┘         │ ATTACK │
         ↑            └────────┘
         │                │自动
    Release=0            ↓
         │            ┌────────┐
      ┌────────┐←────│ DECAY  │
      │RELEASE │     └────────┘
      └────────┘         │自动
         ↑               ↓
         │NoteOff    ┌─────────┐
         └───────────│ SUSTAIN │
                     └─────────┘
```

---

## 五、Python实现（简化）

```python
class ADSREnvelope:
    def __init__(self):
        self.state = 'IDLE'
        self.level = 0  # Q1.15
        
        # 参数
        self.attack_time = 480
        self.decay_time = 2400
        self.sustain_level = 24575
        self.release_time = 4800
        
        # 斜率（预计算）
        self.attack_slope = 68
        self.decay_slope = 3
        
    def note_on(self):
        self.state = 'ATTACK'
        self.level = 0
        
    def note_off(self):
        self.state = 'RELEASE'
        self.release_start = self.level
        self.release_slope = self.level // self.release_time
        
    def step(self) -> int:
        """返回当前包络幅度（Q1.15）"""
        if self.state == 'ATTACK':
            self.level += self.attack_slope
            if self.level >= 32767:
                self.level = 32767
                self.state = 'DECAY'
                
        elif self.state == 'DECAY':
            self.level -= self.decay_slope
            if self.level <= self.sustain_level:
                self.level = self.sustain_level
                self.state = 'SUSTAIN'
                
        elif self.state == 'SUSTAIN':
            self.level = self.sustain_level
            
        elif self.state == 'RELEASE':
            self.level -= self.release_slope
            if self.level <= 0:
                self.level = 0
                self.state = 'IDLE'
                
        return self.level
```

---

## 六、与波表的集成

```python
# 应用包络到波表样本
wt_sample_16bit = oscillator.step()  # [-32767, 32767]
envelope_gain = adsr.step()           # [0, 32767] Q1.15

# 定点乘法: (s16 × u16) >> 15
output = (wt_sample_16bit * envelope_gain) >> 15  # 结果仍为s16
```

---

## 七、验收标准

1. ✅ Python实现完成并测试
2. ✅ Note On无咔哒声（波形平滑上升）
3. ✅ Note Off平滑衰减
4. ✅ 生成测试波形供M2参考

---

## 八、给M2的RTL建议

- 状态机4态
- 每个sample_tick更新一次电平
- 斜率用整数递增/递减（无乘法器）
- Release斜率需要除法（可用移位近似）
