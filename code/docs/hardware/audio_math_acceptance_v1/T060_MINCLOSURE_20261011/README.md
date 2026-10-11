# T060 机器 scope 与最小补采准备入口

2026-10-12，M3。按 M2 V0288 最新规格，只写本新增目录和配套新增软件／TB目录。

当前实现：`scope.py` 只绑定旧封存和 M2 两计数收据，输出组合范围，不运行旧 capture2、
数学/router或56反例。旧数学／路由注明 REUSED，原入口 PARTIAL/exit3 原样保留。
三 END 原值 28/697/6228000 保留、expected=null；两 flag 仅排除精确两点的独立期望，
其 PCM/DDS/包络/ROM/增益/混音/时序、0/1和身份／运输／END严格性均未排除。
原始双 SHA 之外的数据不得自动沿用排除范围，不能由 flag 选择黄金数学。

```powershell
python -B -X utf8 code/software/audio_math_acceptance_candidate/t060_minclosure_20261011/scope.py --output code/output/m3_t060_scope_20261012_01
python -B -X utf8 code/software/audio_math_acceptance_candidate/t060_minclosure_20261011/test_scope.py -v
```

此阶段只达 L0/L1 软件 scope，完整 T060/T061 仍 PARTIAL；无新音频 RTL、综合、PnR、
STA或设备操作。机器 scope 不是通用音频验收器，也不把旧 exit3 改写为 PASS。

## 下一交付阶段（尚未完成，不冒称已有可执行新捕获）

按 M2 同一规格准备独立薄 TB／observer／严格 oracle 和源码日历，再交静态预检。
允许的准备不等于新 RTL 编译／执行许可，当前不得启动两组捕获：

1. A：原 H 单活动槽 NoteOff→原 4800 Release tick→Idle/release_done→真实退休／回收→
   同身份新 generation 重分配；另短例 CC64 deferred 后 panic 真正握手并释放。
2. B：数学前、ADVANCE 同沿、推进后 SNAPSHOT 前、HOLD 背压四点取消；独立输入／源码 FSM
   推导旧 ID 拒收、tick 抑制、DSP 不回滚、held 稳定及恢复 PCM。已提交 pending PCM 依法播放
   不误当过期接受，未提交过期结果不能新接受。

需补精确 H 源／ROM／实际依赖清单、原生成 TB 差异、pre-NBA 口径和独立源码 FSM 锚点，
再给 M2 静态预检。不可换 L/N32/新 RAM，不删旧 unsupported、不用 Q+20 粗窗或观测 phase
生成黄金，不缩短释放、force/reset代退休。计划至少四完整损坏 capture；未来建议编译90秒、
每组300秒、软件90秒、总900秒，实际执行等待 M2 明确确认。

M2 交接：待用户转发，尚未送达。共享状态／编号由 M2 统一登记，本处不写共享表。
