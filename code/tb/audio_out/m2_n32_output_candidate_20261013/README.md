# N32下游输出接入候选

M2新增隔离模块，未连接正式顶层。声音算法、原N32/pROM、帧适配器、sender与observer CDC只读。

接口：40MHz `clk`、25MHz `pixel_clk`，低有效异步复位断言，调用方负责已批准的同步释放/PLL-loss合同。候选侧已混音signed24左右PCM、ID32和准确clipped；帧credit与实际接受分开。发送侧PT8211 LSBJ仍使用原sender；observer采完整frame沿pre-NBA实际play PCM，显示不反压声音。

```powershell
python -B -X utf8 code/scripts/run_m2_n32_output_transport.py --case base --output code/output/NEW_UNIQUE_BASE
python -B -X utf8 code/scripts/run_m2_n32_output_transport.py --case full32 --output code/output/NEW_UNIQUE_FULL32
```

每步300秒、全流程900秒（含后验/收据），不自动重试；新目录拒覆盖。只使用已安装Icarus/VVP及原GW5A模型，source/tool前后SHA和输入原字节快照封存。实际执行必须在有效任务授权范围；本入口不运行Gowin/PnR/STA/设备。

- base：合成左右不同PCM运输、准确metadata、3帧欠载重复、像素停钟/满队列及reset清零；两份可编译行为变异错接左PCM/清clip指定拒收，另真实一音N32/pROM短例READ阻塞恢复。
- full32：当前原N32/pROM32槽同时占用的新接入短例，结果ID/PCM/clip到commit及真实播放观察逐项同；不重跑旧独立声音数学/长生命周期。
- 参考sender与被测sender使用同一冻结模块，串行bit对照只证明新接线不改旧sender输入/行为，不是新增独立LSBJ解码、舍入算法或物理采集。
- 合成clip是运输元数据刺激，不宣称真实削波算法；真实短例未要求饱和命中。原数学/正负饱和结论按其精确身份REUSED。

边界：未做新分配器/32槽长程/通用deadline/资源/物理STA/HDMI绘制或上板；当前旧allocator长路径风险不消失。READ故意阻塞时真实欠载必须如实计数，不要求绝对零。M3优化后继与本模块在公开接口上对接，必须给新组合关联验证，不借此签生产32音。

## 2026-10-13实际新结果

最终base目录 `code/output/M2_N32_output_transport_final_20261013_01`：8步，13.297秒，runner0。合成运输12frame/9commit/5clip/3underrun/12观察/7像素接收/5丢显示；两坏接线compile0/sim1目标 `COMMIT_PCM_CLIP_LEDGER_MISMATCH`。真实一音短例12frame/11接受/10结果/10commit/10非零/12观察/1510READ阻塞沿/2underrun。

最终full32目录 `code/output/M2_N32_output_transport_final_full32_20261013_01`：2步，12.672秒，runner0。32槽occupied=ffffffff，12frame/11接受/10结果/10commit/10非零/12观察/1510READ阻塞沿/2underrun。每次公开结果至commit的ID/左右PCM/clip核同，停钟合成例发送器bit流与由独立ledger驱动的原sender核同。

两个最终执行的输入原字节快照、工具SHA和原日志齐套；前后源相同。初次试跑01和full32_01均保留，它们与最终runner版本不同，不冒充最终树结果。最终版本再次验证只因TB开始窗口改为相对frame基准、runner添加精确快照与收尾资格，不是重跑历史声音专项。

M3交接：只引用此新运输模块及公开候选接口；不要覆盖原frame adapter/I2S/observer，不重跑本12frame/两坏接线组。你的新分配器N32后继定版后，M2按新精确组合补必要接入关联验证。你仍负责A/B/C/D及原T052/T060任务；本文件只证明原pROM候选的下游短程功能，不改变资源/时序准入。当前待用户转发，尚未送达。

本轮最终完整仓库门禁九项PASS0、481.235秒/未超时/2922输入SHA前后同。封存 `code/docs/evidence/m2_n32_output_transport_20261013/RAW_EVIDENCE.zip`，108成员/553096字节，SHA `b37d2084fada1cd595f207ec91c99125f28488cad4d07a1576b1e6c6da0c195c`，含最终输入原字节/原日志/工具SHA、两行为错误与门禁；工具exe/vvp二进制留ignored原输出不随包提交。旧试跑原件不回填。
