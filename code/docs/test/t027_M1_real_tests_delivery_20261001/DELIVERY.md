# DELIVERY —— T027 修正说明 + 真实 RTL 自检

- **源基线**：`0e29e22`
- **交付人**：M1
- **日期**：2026-10-01
- **对应 M2 反馈**：`T027_修正版_M2接收复核_2026-10-01.md`（本地功能提交 88f63d5）
- **性质**：修正交付说明表述 + 补真实 RTL 自检；**不改动 M2 已接收入库的算法逻辑**

---

## 一、本次修正的两个问题

### 1. “5/5 RTL 自检”说法不实 —— 已撤销并补真实自检

**M2 指出**：`test_t027_rtl.py` 未运行 RTL、未实例化模块、5 项中 4 项无断言，
唯一有断言的四声部项只比较 Python 列表长度。**不认可其“5/5 RTL 自检”。**

**本次处理（不是改措辞，是补实现）：**

| 文件 | 操作 | 说明 |
|---|---|---|
| `code/tb/audio/tb_t027_timbre_rtl.sv` | **新增** | 真实 RTL 自检 TB：独立参考模型、逐周期导出 capture、失败走 `$fatal(1)`、含防空跑下限 |
| `code/model/test_t027_rtl.py` | **重写** | 真实调用 HDL 仿真器；Python 独立复算相位/锁存/4 级流水线并**逐样本比对**；含负向用例 |
| `code/model/test_t027_timbre.py` | **重写** | 5 项全部改为**真实断言**，不再有纯打印项 |

### 2. 流水线口径“2 周期 / 3 级”不精确 —— 已更正为 E 到 E+3

真实数据路径共 **4 个寄存阶段**：

| 边沿 | 动作 |
|---|---|
| **E** | `addr_pipe[0] <- wt_addr`；`timbre_pipe[0] <- timbre_latched`；`valid_pipe[0] <- sample_tick` |
| **E+1** | `addr_pipe[1] <- addr_pipe[0]`；`timbre_pipe[1]`、`valid_pipe[1]` 同步移位 |
| **E+2** | 同步 ROM 数据寄存器 `<-- ROM[addr_pipe[1]]`（`sine_data` / `triangle_data`） |
| **E+3** | `sample_out <- 音色选择(ROM 数据)`；`sample_valid <- valid_pipe[2]` |

- `valid_pipe[0..2]` 与 `sample_valid` 同样 4 级；`timbre_pipe[2]` 与同拍 ROM 数据对齐。
- **Note On 与 `sample_tick` 同沿**：本拍仍用旧的 `timbre_latched`，下一拍生效。
- 源码注释与交付说明已同步更正；**RTL 逻辑零改动**（见第三节证明）。

---

## 二、数学 / 位宽 / 舍入 / 饱和

本次**未改动**任何定点口径，沿用已冻结 v1.5：

| 项目 | 值 |
|---|---|
| 波表 | 1024 点 × 16 位有符号，**标称峰值 ±8192** |
| 相位累加器 | 32 位，取高 10 位作地址 |
| 相位步进 | `phase_acc <= phase_acc + fcw`（**先取样、后累加**） |
| 音色锁存 | `if (note_on) timbre_latched <= timbre_select;` |
| 相位连续性 | Note On **不清零**；Note Off **继续推进**（供外部 ADSR Release） |
| ROM 读取 | 同步读，1 拍数据寄存器 |
| 输出 | `sample_out` signed16 ∈ [−8192, +8192]，越界即失败 |

**输入更新与输出延迟**：`sample_tick` 对应输入拍为 E；对应输出在 **E+3** 有效。

**舍入 / 饱和**：本模块无乘法与舍入，直接把 ROM 值送出，不做截断或饱和处理；
幅度约束由 TB 断言守（`+/- 8192`）。

---

## 三、越界声明与改动性质说明

1. **`code/rtl/audio/timbre_oscillator.sv` 本次为纯注释改动。**
   去注释后与修改前逐行一致（已比对验证，逻辑零改动）。
   M2 已按原 SHA 接收入库该文件；如 M2 认为「已接收文件不应再动」，
   **该文件可回退为 M2 接收版本，不影响本次任何结论**。

2. **两份 ROM（`sine_wavetable.hex` / `triangle_wavetable.hex`）未改动**，
   SHA-256 与 M2 接收时一致：
   - sine：`85a1d27131227696ae077506bd9ebdb4bc0bd87828260bcd90407da6c21acd93`
   - triangle：`5b6892e95325641f2b319588bae10b556585ae103d6f16df81c28babe1072996`

3. **未修改**任何公共接口、顶层、CST、`audio_defs_pkg.sv` 或 M2 正式构建脚本。

---

## 四、运行命令与实际结果

```bash
cd code/model

# 1. 模型级测试（L1，真实断言）
python -X utf8 test_t027_timbre.py
# 预期：5/5 通过，退出码 0

# 2. 真实 RTL 验证（L2/L3，调用仿真器）
python -X utf8 test_t027_rtl.py                       # 自动探测
python -X utf8 test_t027_rtl.py --simulator modelsim  # 强制指定
# 预期：2/2 通过，退出码 0

# 3. ROM 可复现
python -X utf8 generate_t027_roms.py
# 预期：两次生成字节一致
```

**实际执行结果（本机 ModelSim SE-64 10.7 实跑，非声明）：**

```text
test_t027_timbre.py   → 5/5 PASS，退出码 0
test_t027_rtl.py      → 2/2 PASS，退出码 0
  正向：仿真检查=46164  有效输出=45175  音色锁存=72  ROM/1024点
  负向：+CORRUPT 人为 1 LSB 偏差 → 被检出（Fatal）
TB 内部自检           → checks=91339  valid_outputs=45175  latches=72  cycles=11541
generate_t027_roms.py → 两次生成 md5 一致
```

**通过数量与退出码**：正向 2/2、模型 5/5，**退出码均为 0**；负向用例被正确检出。
任一失败返回非零，不存在只 print PASS 的路径。

---

## 五、复位 / 异常 / 负向用例覆盖

TB 实际覆盖的场景：

| 场景 | 验证方式 |
|---|---|
| 静音复位 | 复位后 `sample_valid=0`、`sample_out=0`，逐拍断言 |
| 正在发声时全局切换音色 | 已锁存槽不得跟随（逐样本比对） |
| 单槽重触发 | 仅 lane1 重新锁存，其他三槽保持 |
| Note Off 后波形持续 | Note Off 后继续运行，相位持续推进 |
| 最低/最高合法音符 | MIDI 21（27.5 Hz）、MIDI 108（4186.009 Hz） |
| 四路不同音色并发 | 四实例独立锁存，逐样本比对 |
| 独立稀疏使能 + 变化 FCW | 四路不同 tick 模式与 FCW 回绕 |
| 复位冲刷在途数据 | 流水线 pending 时复位，必须丢弃 |
| **负向**：1 LSB 人为偏差 | `+CORRUPT`，必须被检出并失败 |

**防空跑保护**：TB 结束时断言 `valid_outputs >= 40000` 且 `latches >= 20`，
避免“零比较却 PASS”（M2 曾在 `tb_dds_oscillator.sv` 抓到同类问题）。

---

## 六、尚未完成项（不得写成已通过）

| 项目 | 状态 |
|---|---|
| Gowin 综合 | **未执行**（M2 主责） |
| 布局布线 / 时序收敛 | **未执行** |
| 上板 / 实物验证 | **未执行** |
| 正式四声部接入 | **未执行**（M2 主责） |
| 切换防爆音 | **未实现**：当前无跨淡化，仅相位连续；**不能声称无爆音** |

**验证等级**：模型测试 L1；`test_t027_rtl.py` **L2 + L3**（真实仿真 + Python 逐样本）。
无 L4/L5/L6 —— 本机无 Gowin 工具报告。

---

## 七、涉及公共接口的待定问题（交由 M2 决定）

1. **音色编号映射**：Sine=0 / Triangle=1 仍是**候选建议**，未冻结。
2. **每槽选择与有效缓冲**：`CTRL_VOICE_SELECT=5` 已有编号，但正式控制事件
   的值范围、每来源/通道归属、每槽选择时机由 M2 按公共规范连接。
3. **ROM 参数与路径**：正式 Gowin 工作目录下 `SINE_ROM_FILE` /
   `TRIANGLE_ROM_FILE` 的实际映射由 M2 集成时确定。
4. **同沿语义**：Note On 与 `sample_tick` 同沿时用旧锁存值。
   M2 路由应保证 Note On 锁存完成后才采样，避免该边沿混淆。
5. **切换防爆音**：已有音符不跟随、下一 Note On 才锁存。
   活跃同音重触发 / 声部抢占导致的切音色安全边界，需 M2 明确或另交平滑方案。

---

## 八、仿真器说明（环境差异，请 M2 留意）

- **M1 本机没有 Icarus Verilog**，只有 **ModelSim SE-64 10.7**。
- 验证器会自动探测 `iverilog+vvp` 或 `vlog+vsim`；
  M2 侧若有 Icarus，可直接 `python -X utf8 test_t027_rtl.py` 走 Icarus 路径。
- **已知坑**：ModelSim 的进程退出码会被 `quit` 覆盖，
  即使 `$fatal` 触发也可能返回 0。因此该路径以**日志中的 PASS/Fatal 标记**判定，
  并已在验证器中显式处理；Icarus 路径同时校验真实退出码。

---

**交付：** M1　**日期：** 2026-10-01　**基线：** 0e29e22
