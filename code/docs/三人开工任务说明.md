# 三人开工任务说明

> **【2026-09-16 只读横幅（D025）】** 本文是 W1 阶段的历史交接文档，**正文保持原样不再改写**。
> 文中所有「使用分支」「任务分支」「不要把多个任务混进一个大提交」之类的**分支类要求已作废**：
> 2026-09-16 起三人一律**直接推 `develop`，不新建任何分支**，复核统一归 M2。
> 现行规则见 `code/docs/Git协作规范.md`，决策见 `code/docs/技术决策记录.md` D025。
> 任务编号、授权目录、验收条件这三项仍然有效。

更新时间：2026-09-12。适用阶段：W1 收尾至 W2，目标是在 2026-09-20 前完成 S1 接口冻结和 S2 固定音链路的关键准备。

## 一 当前结论

三个人现在可以开始工作，不需要继续等待管理框架完善。

- M1 立即开始 Python DDS 参考模型和波表、FCW 生成工具。
- M2 用一至两天建立正式 FPGA 技术骨架，并组织接口冻结。
- M3 立即开始板卡、电源、引脚、外设和实验室资源核对。

开始工作不等于三个人同时随意修改 `code/rtl/`。每个人必须使用任务看板中的任务编号和独立分支，只修改授权目录。

## 二 已冻结公共接口

T001 已由 M2 直接完成，`模块接口规范.md` v1.0 是 M1、M2、M3 和各自 AI 的统一执行依据，不需要额外会议或签字。

关键结论：64 位演奏事件、10 位线性 Velocity、Note On Velocity 0 转换为 Note Off、32 深度事件 FIFO、valid ready 反压、连续控制限速合并、24 位有符号 PCM、32 位 I2S 槽位、低有效异步拉低同步释放复位、48 kHz 单周期 `sample_tick`、单 `sys_clk` 加时钟使能。

## 三 M1 立即任务

岗位：音频算法、验证与竞赛交付负责人。

### 当前任务

| 任务 | 分支 | 交付物 | 验收 |
|---|---|---|---|
| T002 Python DDS 参考模型 | `feature/model-dds` | 相位累加、波形生成、频率测量模型 | 440 Hz 误差满足文档阈值，自动 PASS |
| T003 波表和 FCW 生成脚本 | `feature/model-dds` | 波表文件、MIDI 音符 FCW 表和重复生成命令 | 两次生成结果一致，参数和格式有说明 |

### 授权目录

```text
code/model/
code/docs/test/
code/tb/中由任务明确授权的算法测试目录
```

### 第一批交付要求

- 参数至少包括 48 kHz 采样率、32 位相位和 16 位波表样本。
- 输出至少覆盖正弦、方波和锯齿波中的两种。
- 写明定点格式、舍入方式和预期误差。
- 测试不能只由肉眼看曲线判断，必须输出 PASS 或 FAIL。
- 暂不依赖开发板，不等待 M2 的完整顶层。

### 不要做

- 不自行修改公共接口、系统时钟和 I2S 格式。
- 不把 Python 或电脑音频作为正式实时合成通路。
- 不把正式算法写在已删除的早期原型 `legacy-prototype/` 上（该归档 2026-09-15 已移除，源码见 Git 历史）。

## 四 M2 立即任务

岗位：FPGA 技术与系统集成负责人，兼任当前技术和集成负责人。

### 当前任务

| 任务 | 分支 | 交付物 | 验收 |
|---|---|---|---|
| T019 时钟复位与 `sample_tick` | `feature/clocking` | 复位同步和 48 kHz 节拍模块及自检 TB | 复位、边界、长期计数自动 PASS |
| T005 I2S 发送器和解码 TB | `feature/i2s` | `i2s_tx`、I2S monitor 和自检 TB | 解码样本与输入 PCM 一致 |
| T020 可综合集成骨架 | `feature/integration` | Tang Mega 60K 顶层骨架 | 固定 PCM 到 I2S 链路可综合 |

建议顺序是 T019，随后 T005，最后 T020。公共接口直接引用 v1.0，不再重复设计。

### 需要建立的正式文件

按实际任务创建，不要只建空目录：

```text
code/rtl/common/audio_defs_pkg.sv
code/rtl/common/reset_sync.sv
code/rtl/common/sample_tick_gen.sv
code/rtl/audio_out/i2s_tx.sv
code/rtl/board/tang_mega_60k_top.sv
code/tb/common/tb_reset_sync.sv
code/tb/common/tb_sample_tick_gen.sv
code/tb/audio_out/i2s_monitor.sv
code/tb/audio_out/tb_i2s_tx.sv
code/scripts/run_sim.ps1
code/scripts/build_gowin.ps1
code/scripts/verify_all.ps1
```

### M2 的边界

- PCM 数学格式和算法行为由 M1 定义，M2负责工程实现和时序可行性。
- 实物引脚、电压和接线依据由 M3提供，M2将确认结果写入 CST、SDC和顶层。
- 未确认的引脚不得写成正式约束。
- 第一版目标是固定 PCM 能被 testbench 正确解码，不是立即实现32复音。

## 五 M3 立即任务

岗位：实体硬件、交互与上板验证负责人。

### 当前任务

| 任务 | 分支 | 交付物 | 验收 |
|---|---|---|---|
| T006 NEO Dock 引脚与电源核对 | `feature/board` | 带来源的引脚、电压和接口表 | 每项能追溯到原理图或官方资料 |
| T018 开发板到货与采购跟进 | `feature/board` | 到货、电源、附件和缺件记录 | 日期和缺件明确 |
| T011 板卡与仪器标签登记 | `docs/team-collaboration-governance` 或单独资源分支 | BD-01、BD-02、LA-01、LA-02登记 | 实物编号、保管位置和状态完整 |

### 第一批核对内容

- FPGA 完整料号与封装。
- 板载系统时钟来源和频率。
- NEO Dock JTAG、UART、音频和扩展接口。
- FPGA I/O Bank 电压和外设逻辑电平。
- 板载音频链路或 Codec 的型号、时钟要求和信号方向。
- 两套板卡、两个逻辑分析仪及实验室公共仪器的实际状态。
- 首次上电前的短路、电压、限流和共地检查表。

### 不要做

- 不凭网络二手引脚表直接编写正式 CST。
- 不把 5 V 输出直接接入 3.3 V FPGA GPIO。
- 不在带电状态修改跳线或焊接。
- 不在没有记录 Git 提交和码流来源时进行上板结论登记。

## 六 首次四天安排

| 日期 | M1 | M2 | M3 | 共同输出 |
|---|---|---|---|---|
| 09-12 | 建立 DDS 模型框架 | 读取接口 v1.0，设计 `sample_tick` | 收集板卡和电源官方资料 | 各自分支和任务边界确认 |
| 09-13 | 440 Hz 样本和 FCW 表 | `sample_tick` 模块与 TB | 第一版引脚和电压事实表 | 确认接口待决项 |
| 09-14 | 波表生成与自动测试 | I2S 发送器和 monitor | 复核 I2S 外设方向与电平 | 接口 v1.0 候选 |
| 09-15 | 提供固定 PCM 测试向量 | 接通固定 PCM 至 I2S TB | 复核测试方案 | 第一次数字音频链路集成 |

日期落后时不要机械补齐，应在任务看板更新实际状态并重新确定关键路径。

## 七 分支和交付规则

每个人开始前执行：

```powershell
git switch develop
git pull --ff-only origin develop
git switch -c feature/任务名
```

如果目标分支已经存在，切换到已有分支，不重复创建。提交前至少运行：

```powershell
. .\code\scripts\enter_fpga_env.ps1
.\code\scripts\check_repo.ps1
git diff --check
git status --short
```

每次交付必须说明：任务编号、修改文件、运行命令、实际结果、L0至L7验证等级、未验证项目和公共接口影响。

## 八 给各自 AI 的使用方法

队员把仓库交给 AI 后，不需要复制全部聊天记录。向 AI 发送：

```text
请先完整阅读 AGENTS.md、code/AGENTS.md、code/docs/协作入口.md、code/docs/三人开工任务说明.md，以及我岗位对应的局部 AGENTS.md。

我的岗位是 M[1/2/3]，本次任务是 Txxx，目标分支是 xxx，授权目录是 xxx，验收条件是 xxx。

只修改授权目录。需要修改公共接口、时钟、复位、位宽、采样率、顶层端口或引脚时先停止并提交影响分析。完成后运行测试，更新任务状态和验证记录，明确验证等级与未验证项。
```

更完整的岗位提示词见 `AI开工提示词.md`，跨账号或跨工具续接见 `AI交接上下文.md`。

可以直接转发给三名成员的独立通知：

- M1：`code/docs/发给M1的开工通知.md`
- M2：`code/docs/发给M2的开工通知.md`
- M3：`code/docs/发给M3的开工通知.md`

## 九 第一次共同验收线

第一次集成不要求真实开发板发声，先完成数字链路：

```text
固定 PCM 测试向量
    -> I2S 发送器
    -> testbench I2S monitor
    -> 解码 PCM
    -> 与原输入逐样本比较
    -> 自动 PASS 或 FAIL
```

通过后再接 M1 的 DDS 和 ADSR。开发板到货后，M3按照同一测试向量核对真实 BCLK、LRCLK和DATA。
