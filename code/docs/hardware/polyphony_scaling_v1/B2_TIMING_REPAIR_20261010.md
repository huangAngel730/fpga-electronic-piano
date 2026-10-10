# B2 时间 checker 最小返修（2026-10-10）

本轮响应 M2 Callback2 反馈包，只改 B 候选软件 checker、测试、复现与交付文档。
原 B2a/B2b RTL 时点经 M2 审计正确；本轮修的是 checker 漏收，不推翻原数学结论，
不重新生成原 capture、不改 RTL/ROM/原封存、不运行长程 RTL 或 Gowin。
完整 T060/T061 保持未关闭；共享登记交 M2，不自行取号或改共享状态。

## 独立源码日历

`b2_clock.py` 从 admission C 开始逐状态推进 PITCH(7)、ADVANCE、SETTLE(4)、
ROM_START/ROM_WAIT(R)、GAIN、ACCUM。参数来自固定 profile，不从 A/L/F/O 观测值反推期望。
L 是 GAIN 后 NBA 的公开 tap；A 与首次 valid 由 TB 在 NBA 前观察。

| 事件 | 源码期望时点 |
|---|---|
| 统一推进 A | C+8 |
| 槽 i 的 L（含空槽） | C+15+R+(R+3)i |
| 后端首次可观察 valid | C+14+N(R+3)，即末槽 L+2 |
| N4 wrapper 首次 F | 后端首次 valid+2，即末槽 L+4 / C+28+4R |

B2b 原有 Q/C 推导保持：C=Q+27。额外两拍来自银行提交资格与注册 HOLD，
不是任意补偿常数；源码/TB 随证据只读封存。每一时钟边沿（包括 capture 空隙）
检查 L/F 是否应出现，不只检查已出现记录。F 必须精确且只出现一次，P 是可延迟的输出握手。
deadline 使用首次可见 valid 与 admission 的源日历 age（差值减一），不使用 P 等待时间。

B2a 原 fixture 只记录 O 握手，没有独立首次 valid tap；其完成后被背压的帧会取消，
不恢复输出。本轮 O 固定时点检查只适用于该 fixture；不宣称任意 ready 反压下 O 仍固定，
也不把任意握手等待算作 compute。未来补首次 valid/反压观察需另列 TB 范围。

X/身份作废优先于同沿检查。取消不强制每 C 都有 O/F，不回滚已接受 LFO 或已推进 DDS/ADSR。
B2a reset 的 R 是保持四个上升沿后的释放观测；检查取消/复位前确实应有的阶段，不要求复位期间 tap。
现有全 tag、原子发布、银行读回与非回滚数学检查均保留。

## 实际软件终验

全新收据：`code/output/m3_t061_b2_timing_repair_20261010_02/receipt.json`。
47 个命令步骤符合各自预期退出码，总耗时约 33 秒，工作流退出 0。
`_01` 是补充行为核验前的软件正例通过记录，原样保留，不回填。

- 6 份 B2a、2 份 B2b 原完整 capture 与旧封存 manifest 的原 bytes/SHA 逐一绑定后重放，全部退出 0。
  B2a compute 精确为 29/37/45/77/141/1133；B2b N4 R1 为 67–77、R3 为 75–85。
- M2 两份原短正例通过；M2 7 份完整时间反例全部按源时钟诊断退出 1。
- 新增 14 份完整时间反例：A/L/O/F 前后错一拍、缺 F、重复 F；全部退出 1。
  缺/重复 F 的 END 计数同步保持真实，不靠计数不符拒收。
- F 不变、首次 P 后移两拍的完整正例退出 0，验证首次 valid 与握手分离。
- 3 份 deadline 字段反例按指定诊断退出 1；4 项日历单测含 832/833/834 边界。
  临界边界是软件逻辑测试，不冒称新 RTL 临界激励已执行。
- 9 个 B2a、6 个 B2b 原语义反例仍按原指定原因拒收；B2b 六例另逐项 CLI 验证退出 1。
- 只读核验已封存的 B2a gain/skip-last 与 B2b generation 原日志身份、退出码及指定 FATAL；
  B2b 原 gain 行为 capture 由新 checker 重放，仍以 `MATH_GAIN_PCM` 拒收。未重跑行为 RTL。
- 日历 4 项、既有 checker 6 项、候选合同 40 项单测全部通过。

原始命令、stdout/stderr、真实退出码/超时上限、源码与保护项前后 SHA、反例及新收据封存于
`B2_TIMING_REPAIR_20261010_02`，旧封存与反馈包保持字节不变。
仓库门禁独立运行：只使用暂存树导出的隔离副本，保留九项真实检查日志。
门禁内既有 T007/T019 短自检不等于本轮重跑 B2 长程 RTL；不执行 Gowin。
首次发布副本导出因 Windows 长路径失败，九门禁尚未开始；失败日志另存，不冒充门禁通过。
修复仅为导出命令临时启用 Git longpaths，并采用较短隔离输出路径；不更改公共 Git 配置。

## 复现与限制

```powershell
python -B -X utf8 code/software/polyphony_scaling_candidate/b2_timing_repair.py --feedback E:/FPGA/GAOYUNFPGA/Callback2/M2_T061_B2a_B2b_复核与时间checker返修_20261010 --output code/output/m3_t061_b2_timing_repair_replay_NEW
```

输出目录必须全新；输入 capture/旧封存须从既有包恢复到原相对路径，反馈包须保持 manifest 身份。
也可直接对封存中的原 capture 调用 b2_check.py / b2b_check.py。

本轮是 L1 checker 与既有 capture 离线 L3 重算；不增加 RTL/STA/设备验证等级。
B2a 正饱和 RTL 未命中、高 N 短程 Release、N4 对冻结 L 整体逐时钟差异、任意背压与事件服务上界仍保留。
不声称 8/16/32 整链演奏或整机 deadline/STA 通过，不使用额外综合额度。
现有用户单独授权的 RAM 无时限 PnR 任务不属于本包，本轮既不重启也不停止它。

待 M2 复核后统一登记；后续继续 RAM 候选和同一复音候选 N8 独立推进。
