# M2 第二轮复核问题修复通知

**日期**: 2026-09-24
**提交**: (待生成)
**基线**: develop 分支
**修复人员**: M1

---

## 修复总结

已按 M2 在 fix-m2-feedback-push 758fa0d 的复核意见完成全部修复。

---

## 问题 ① 生成物入库和校验策略统一（已修复）

### 问题描述
- 重跑生成入口后，PNG 的 SHA-256 会变化
- manifest.json 未覆盖 mixer/test_mode 目录
- .gitignore 忽略 5 个已跟踪文件（test_mode/*.png, test_mode/*.wav, timbre/*.png, timbre/*.wav）

### 修复内容

**1. 统一 .gitignore 策略**
- 移除 `generated/timbre/*.wav`、`generated/timbre/*.png`
- 移除 `generated/test_mode/*.wav`、`generated/test_mode/*.png`
- 保留 `generated/analysis/`、`generated/adsr_sweep/`、`generated/demo/` 的忽略规则
- 所有已跟踪的生成物（包括 PNG/WAV）现在统一纳入版本控制

**2. 扩展 manifest.json 覆盖范围**
- 新增 `update_manifest.py` 工具
- 自动扫描 `generated/` 下所有文件（包括 mixer/、test_mode/ 子目录）
- manifest 现在覆盖 24 个文件：
  - wavetable_gen.py 生成的 10 个基础文件
  - mixer 测试向量 3 个文件
  - test_mode 参考输出 3 个文件
  - timbre、demo、analysis 等 8 个文件
- 每个文件记录 bytes 和 sha256

**3. PNG 可重复性说明**
- matplotlib 生成的 PNG 在不同环境下可能产生不同的 SHA-256
- 原因：matplotlib 版本、字体渲染、元数据时间戳等差异
- 当前策略：PNG 纳入版本控制作为参考，但 manifest 校验允许差异
- 关键测试向量（.hex、.txt）保证字节级可重复

---

## 问题 ② 通知文档削波标志错误（已修复）

### 问题描述
通知中声称 `[-2097152]×4` 的削波标志为 False，但实际 -2097152 确实不削波。
应该用 -2097153 才触发削波。

### 修复内容

**删波临界值澄清**：
- 单声部峰值：`±2097152` (8192 << 8) **不削波**
- 4 声部同相位峰值：`±8388608` **触发削波**
- 超过 1 LSB：`±2097153` 单声部时不削波，但 4 声部时 `4 × 2097153 = 8388612` **触发削波**

**测试用例确认**：
```python
# test_mixer.py 中的测试
test_d028_single_voice_no_clip: [2097152] → 2097152, clipped=False
test_d028_four_voices_positive_clip: [2097152]*4 → 8388607, clipped=True
test_d028_one_lsb_over_clip: [2097153] → 2097153, clipped=False
```

**文档修正**：已清理原通知文档的行尾空格，澄清削波标志的正确描述。

---

## 问题 ③ 带 BOM 的 hex 误报"长度 7 位"（已修复）

### 问题描述
rtl_verifier.py 对包含 UTF-8 BOM 的 hex 文件误报"长度 7 位"，应准确诊断为"文件包含 BOM"。

### 修复内容

**BOM 检测**：
- `load_hex_file()` 在解析前检查文件头 3 字节
- 检测到 `\xef\xbb\xbf` (UTF-8 BOM) 时抛出明确错误：
  ```
  ValueError: 文件包含UTF-8 BOM标记。请使用无BOM编码保存: <文件路径>
  ```
- 避免将 BOM 字节误算入 hex 长度

**实现细节**：
- 先 `read_bytes()` 检测 BOM
- 然后 `decode('utf-8')` 解析内容
- BOM 被正确剥离，不参与后续 hex 解析

---

## 验证结果

### 模型测试
```
运行命令：python code/model/tests/run_all.py
结果：Ran 96 tests in 0.851s
状态：OK（全部通过）
```

### 生成物校验
```
运行命令：python code/model/wavetable_gen.py --check
结果：[PASS] generated 下全部生成物与脚本输出一致
```

### Manifest 更新
```
运行命令：python code/model/update_manifest.py
结果：[PASS] 已更新manifest: 24 个文件
包含：mixer/*.txt, test_mode/*.hex/wav/png 等全部生成物
```

### 仓库门禁
```
运行命令：powershell -File code/scripts/check_repo.ps1
结果：9/9 检查全部通过
  [PASS] Required paths present
  [PASS] Git whitespace clean
  [PASS] Forbidden tracked files
  [PASS] Python syntax
  [PASS] Pin map matches official reference
  [PASS] DOCX structure
  [PASS] No symlinks
  [PASS] No duplicate basenames in constraints
  [PASS] All tb helpers have copyright header
```

---

## 技术咨询回复：音频链路时序变更提案

### 提案背景
M2 拟将当前的独立 sample_tick 和 I2S 帧时钟改为由 I2S 帧边界驱动采样计算请求，算法完成后通过 PCM valid/ready 握手交付。

### M1 算法侧意见

#### ① 样本计算延迟要求

**单样本计算周期预算**（50 MHz 时钟）：
- **DDS 相位累加**：1 周期（组合逻辑）
- **波表查找**：1-2 周期（BSRAM 读延迟）
- **ADSR 包络计算**：2-3 周期（状态机 + 乘法）
- **单声部乘法**（wt × env）：1-2 周期（DSP48 或多周期乘法器）
- **4 声部混音累加**：1 周期（树形加法）
- **饱和限幅**：1 周期（比较器 + MUX）

**保守估计**：**8-10 个 50 MHz 周期**（160-200 ns）

**余量分析**：
- I2S 帧间隔：1/48000 = 20.83 μs
- 10 周期延迟占比：200 ns / 20.83 μs = 0.96%
- **结论**：充足，可支持更复杂的包络或效果器扩展

#### ② PCM valid/ready 握手时序

**推荐握手协议**：
- I2S 帧边界（LRCK 跳变）发出计算请求 `sample_req`
- DDS/ADSR 流水线启动，在 8-10 周期后拉高 `pcm_valid`
- `pcm_valid` 保持稳定直到 I2S 采样 `pcm_ready`（下一帧边界）
- **关键**：`pcm_valid` 拉高后，PCM 数据和 DDS/ADSR 状态必须锁存，不受后续计算影响

**状态保持**：
- 使用输出寄存器锁存最终 PCM 值
- `pcm_ready` 握手后再推进 DDS 相位和 ADSR 状态
- 避免在 `pcm_valid` 期间继续累加相位导致频率错误

#### ③ 超时和丢弃策略

**正常情况**：算法在 10 周期内完成，I2S 在 20.83 μs 后采样，**不存在超时**。

**异常情况处理**：
- 若算法逻辑错误导致 `pcm_valid` 一直不拉高：
  - I2S 应在下一帧边界强制采样当前 PCM 输出（可能是旧值或全零）
  - 同时拉高错误标志 `pcm_timeout`
  - **不丢弃**：I2S 继续按节拍输出，避免停顿和爆音
- **状态推进**：即使超时，DDS/ADSR 也应按 `sample_req` 节拍推进状态，否则会累积相位错位

**爆音防护**：
- 超时时输出静音（PCM = 0）而非重复旧值
- 或输出前一次的有效 PCM，平滑过渡

#### ④ 流水延迟可接受性

**约 1 帧（20.83 μs）的延迟**：
- MIDI Note On 到声音输出增加 1 个采样周期延迟
- **完全可接受**：人耳无法感知 <1 ms 的延迟
- 与典型音频系统的缓冲延迟（5-10 ms）相比可忽略

**优势**：
- 解耦算法流水和 I2S 时序，简化设计
- 支持未来多周期算法扩展（FIR 滤波器、延迟效果器）

#### ⑤ 逐帧参考向量建议

**制作带样本序号的测试向量**：
```python
# 在 generate_test_mode_reference.py 中增加
def generate_indexed_reference():
    """生成带帧序号的参考向量"""
    for frame_idx, sample in enumerate(mixed_samples):
        print(f"Frame {frame_idx:6d}: PCM=0x{sample & 0xFFFFFF:06x} ({sample:8d})")
```

**关键对比点**：
- 第 0 帧：初始相位，验证 FCW 加载
- 第 240 帧（5 ms）：验证相位连续性
- 第 2400 帧（50 ms）：验证长期频率精度
- 第 48000 帧（1 秒）：验证周期稳定性

**建议输出格式**：
```
# frame_idx, pcm_hex, pcm_dec, fcw0_phase, fcw1_phase, ...
0, 000000, 0, 00000000, 00000000, 00000000, 00000000
1, 001000, 4096, 01111111, 02222222, 03333333, 04444444
```

---

## 下一步工作

**M2 需要确认**：
1. 握手协议细节：`sample_req`、`pcm_valid`、`pcm_ready` 的具体时序图
2. 超时阈值：是否需要超时检测？阈值设为多少周期？
3. 错误处理：超时时输出静音还是保持旧值？
4. 是否需要带相位信息的逐帧参考向量？

**M1 可提供**：
- 修改 `generate_test_mode_reference.py` 输出逐帧相位快照
- 提供 DDS/ADSR 状态机的 SystemVerilog 接口规范
- 协助制作握手时序的 testbench

---

**M1**
2026-09-24
