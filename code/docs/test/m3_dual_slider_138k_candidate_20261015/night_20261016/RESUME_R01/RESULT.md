# D恢复R01：四个未执行RTL行为负例限定完成

日期2026-10-16；基线c12636c034be62e10c564217298564422a533b9c。仅本轮明确授权的四个故障注入验收已完成；D正式整机、真实R05算法、STA/实屏/模拟发声仍未验。旧PARTIAL回执与失败原件作为历史保留，未覆盖。未提交/未推送；由夜间总控统一精确树门禁与Git发布，M2最终复核。

真实执行命令：

```powershell
& 'C:/Users/songdongkuan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -X utf8 code/docs/test/m3_dual_slider_138k_candidate_20261015/night_20261016/RESUME_R01/run_negatives.py --output code/docs/test/m3_dual_slider_138k_candidate_20261015/night_20261016/RESUME_R01/RUN_01
```

正常require_escalated审批通过，runner退出0。实际11个子调用：2个版本查询、1次共用编译、4次VVP、4次checker；未运行正常组。编译/四次仿真均exit0，每次58项视觉/音频共存进度检查完成；四次checker均exit1且命中启动前固定诊断。组耗时18.782s，实际仿真14.063s，无超时；仅消费新批1组，首过封存，剩余2组不继续使用。每工具/组≤300s，本批累计仿真≤900s。Windows Job创建挂起子进程、attach后resume，退出后关闭Job；命令/cwd/原始双流/退出/时间/前后SHA/消费原件全在RUN_01。

| 真实RTL夹具故障 | 实际公开轨迹 | checker指定拒收 |
|---|---|---|
| epoch1 req48漏生产PCM | 该ID提交0，总成功PCM提交189；epoch1欠载计数1、epoch2为0 | UNEXPECTED_UNDERFLOW |
| 左右PCM接线交换 | PCM公开轨迹与原正常捕获完全一致、190提交/欠载0；引脚变化35150行 | SERIAL_PCM_LSBJ_OR_STEREO |
| BCLK采样的DIN延迟一位 | PCM公开轨迹同正常、190提交/欠载0；引脚变化18154行 | SERIAL_PCM_LSBJ_OR_STEREO |
| 下落模式错误门控tx.valid | PCM公开轨迹同正常、190提交/欠载0；引脚变化6708行 | SERIAL_PCM_LSBJ_OR_STEREO |

每个新capture均160024个连续系统沿，均由真实VVP产生，不改写capture来冒充行为变异。独立只读audit_trace.py退出0，对比旧正常capture确定表中事实；详见TRACE_FACTS.json。错相故障在TB引脚观测路径的BCLK管线实施，非声称原tx内部存在缺陷。四个反例有意损坏输出，功能“负例被拒收”是成功条件，不把反例音频本身称为通过。

原正例只引用：封包D_AUDIO_VISUAL_COEXIST_PARTIAL_20261016.zip（SHA dd3031c4eb4d476fac6e73565728df2b699b00cf4cc9add7d0dab64cf8386352）、正常capture SHA45678d9e408fe9d38a9a9c6e797a4725d28439c03abfdda814928acdb3e6e87f；188个完整立体声帧含2次启动静音、186请求完整观察、58项检查/欠载0。旧94/95复位串行截断、96号取消与窗口尾段的分类不改。新封包内同时携带旧ZIP本体，便于核正例/失败原件；不重跑旧99/4或正常组。

来源/写集：只新增D docs/test与tb/input/visualizer的night_20261016/RESUME_R01；复制TB与旧已过正常组同字节SHA92b8a1873fef2b6d296596c0ba6bfb92ad99ae090869e17b3b3eed958c47ed7b；checker只迁移ROOT一行，runner删正常组、迁移路径/独立新批账本并增加旧原件SHA校验，COPY_MAP及两个diff齐全。原算法/ROM、视觉/音频正式RTL、约束和接口均只读。源码/工具/Job/C decoder/旧normal/TB/checker/runner在执行前后SHA稳定。旧MANIFEST本身未列前后输入，最终静态核同SHA3cedcbf46977a0750374e26ce44c57174b0cf74e63b1568df366ab14f5b2c02e，不回填旧收据。

默认自审：主窗口检查运行结果、消费、公开轨迹差异及封包；自有只读子智能体核launch/receipt argv一致、全部双流SHA、before/after一致、COPY_MAP与执行源一致、1消费/无positive、预算和预定诊断，未发现本次范围具体阻断。子智能体未修改或运行被审内容；未启用审核员制度。

实际等级限L2隔离模块行为负例，checker/差异核验为L1软件。诊断PCM生产者不是真实R05算法，frame_start为加速显示夹具而非完整raster；board_release_allowed=false。未跑ModelSim/Gowin、综合/STA、码流、下载、实屏、模拟≤10ms或命中闪光；命中闪光旧FAIL不修。本轮无新的执行失败，不恢复任何旧消费，不修改旧暂存文件。

交接责任：夜间总控核本轮同版来源、将新增恢复包与旧正例关联并统一发布，再交M2最终限定复核；正式接入/物理/实物仍按原准入办理。直接回报总控的授权已由read_thread核到用户原文；实际发送回执另列，不把落盘当送达。
