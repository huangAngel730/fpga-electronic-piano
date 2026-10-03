# E调度时序返修：补充合同配置复核

功能优化已独立提交de68038。本目录不重复实现parser或另一套TB。
`run_midi_scheduler_timing_review.py`复用已提交的完整选择oracle、逐拍miter与三个
可编译行为反例；仅在忽略output的临时TB副本将第四配置burst3替换为burst16。
冻结参考使用任务单指定的3ad0650，精确SHA仍为
`cfd4c33e91ba06a73c89dedb66b8636dc0c1bd1778ae454714325207424c28c4`，
与原3d6430e parser逐字节相同。参考只改模块名，不用新候选生成参考。

```powershell
python -X utf8 code/scripts/run_midi_scheduler_timing_review.py --output code/output/m3_E_timing_review
```

四组FIFO/BURST/CLK_HZ：1/1/64000、8/8/64000、16/8/50000000、3/16/1。
沿用32RR起点、空满/稀疏/密集pending、逐槽插入/最新值/取消及独立线性oracle，
全部公开输出、FIFO诊断与运输调度状态逐拍比较；真实50MHz/1kHz与随机反压、复位。
既有TB/runner只读，新增入口遇到配置锚点变化拒收。无需新寄存器或流水拍。

evidence.json记录实际冻结SHA、生成TB SHA、命令、日志及退出码。
三个反例必须编译成功并由selector oracle拒收，超时不算行为反例通过。
只证明L2仿真等价；实际Setup/Hold/Recovery及Gowin兼容性由M2最新组合PnR/STA核实。

2026-10-03实际ModelSim SE-64 2020.4复跑：400384组oracle、四组各3329005拍、
15次复位PASS；第四配置burst16为6650事件/2958控制/11997停顿拍。
正向library/compile/run退出0/0/0；三个反例均0/0/1、指定行为断言拒收。
原scheduler九正向/三反例、Program三正向及仓库九项门禁全部PASS。
日志保留在`code/output/m3_E_timing_review_20261003/`，不覆盖此前证据。
