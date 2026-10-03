# M3 E补充合同与F真实UART到PCM：M2证据复核（2026-10-04）

## 顺序与结论

按用户指令先准备G/H/I的具体合同、范围、只读源SHA和可私发任务，再开始审核E/F。任务通知**待用户转发，尚未送达**，不能写M3已开工。

- E功能de68038已在V0170签收，本轮不重复签收或重做；c1a24af补充burst1/8/16合同的原生成TB、baseline、退出码和日志身份核对通过。
- F45e4cff原ModelSim L2/L3候选交付证据可以签收，M2对原capture独立整数重算与12个拒收检查实际通过。不是本机重新运行完整ModelSim，也不等于上板效果或新时序收敛。
- 背景one-hot试验按用户允许保持运行，本任务不轮询、不终止、不自动采用；原60分钟停止安排被后续背景运行指令替代。

## 来源校验

新ZIP `M3_E_F_M2_delivery_20261003.zip` SHA：
`c5a62c9617999721fe347b5644dafcb490dfb3d0d8bf29cf85aab37177c60b78`。
77份附件size/SHA、8份源文件与本地Git原件匹配；所有原日志哈希一致。
F39项只读依赖按原始SHA核对，三mem若换行不同分别记录raw SHA，验证LF/CRLF表示与表值等价，不静默修改。
重执行已有M2 ADSR生成函数到新output，其两个候选SHA和改名bank_reference SHA与M3compiled evidence完全一致；没有把当前正式ADSR随便替代原流水候选。
F三mutant源码从当前不修改原件重构，SHA与原ModelSim evidence一致。

## E补充合同复核

c1a24af没有改解析器：复用原TB唯一第四配置burst3→16替换，M2重建字节SHA f699d9ee…0fa2db，与原evidence一致。
3ad0650冻结parser SHA与原3d6430e一致。原M3工具ModelSim2020.4执行400384选择检查、四配置各3329005拍、15复位，正向编译/运行exit0；三个新选择变异编译0/运行1。
原scheduler三行为反例与Program/输入专项日志身份在附件保留，原M3执行，不当作M2新运行。
原V0170已有M2四配置各256193拍等价（本轮one-hot试验也含16，但该实验结果不混到本提交），不为补合同无限重复长仿真。
当前源de68038在V0171公平物理对照已让47输入组合通过工具STA（Setup+.017/Hold报告.000），余量工程目标未达；新E/F只测功能，不改写该物理边界。

## F独立原capture重算

DUT确实串两路真实50MHz/31250/8N1 UART、32项公共FIFO、真实voice_allocator/router/sustain/V1/PitchMod银行及原PCM提交，非A的手写声部身份夹具。
层级slot/base用于观测参考，分配动作由真实RTL场景断言；不能把这个参考称为独立完整allocator模型。

M2使用匹配SHA的Fchecker对原正向capture重算，并逐项对照原evidence：

| 项目 | 实际原capture复核 |
|---|---:|
| 正常PCM帧 |2484|
| 明确夹具PCM帧 |2|
| PCM成功提交 |2486|
| 非零控制声部结果 |3734|
| 非零PCM |2301|
| UART字节／正常输入事件 |103／34|
| TB竞争夹具事件 |34|
| 必需场景 |17|
| 身份／通道组合 |8|
| 中心bank对照 |697|
| 满FIFO同拍出入 |1|
| 控制反压周期 |59|
| 采样边缘事件 |6|
| 请求被复位取消 |1|

独立M1FCW、按FCW累计的DDS相位、原V1波表和Q15 floor/PCM24混音、提交frame tag全部一致；normal/fixture分开，不把34人工竞争事件说成真实DIN。
原TB要求正常无UART帧错误/解析器溢出/PCM欠载，并复位后恢复；其run.log正向Errors0/一次PASS及source identity核对有效。
ADSR包络和table选择取真实bank观测值，只独立验证波表采样和PCM算术，不冒称又建立一份完整音色/ADSR黄金模型。

### 反例与防假绿

1. DDS错用base：原变异编译0/仿真0，但M2重算该原mutant capture实际拒绝“DDS adjusted FCW bypass”；正确拒收来自独立reference，不假称RTL返回1。
2. 错PCM frame id：原ModelSim编译0/仿真1且日志“PCM frame tag mismatch”；其提前终止capture也被M2拒收，但不将missing-END等二次拒收冒称复现原RTL断言。
3. 控制提前应用：原编译0/仿真1且日志“control updated before public FIFO acceptance”；capture独立拒收、源码变异SHA验证。
4. 本机重新执行test_capture.run_checks：10损坏capture经过真实公开`--check-capture` CLI全部退出1；scratch缺ROM/缺UART源码两preflight实际拒绝，总12项PASS，生产输入未改。

本轮没有把编译失败、工具超时或mutant无关错误当PASS，也没有重跑完整F RTL。实际原capture生成来源仍为M3 ModelSim2020.4。

## 发布与下一步

E/F交付可以按候选L2/L3证据收口，不重复开发A-F；整个T036实际音效及正式音画验收仍未关闭。
G/H/I接口准备交给用户私发，M3在独立范围内实现／自检，M2继续正式接入、参数平滑策略和整机余量。
I只有1024/4096/16384各一次综合，与当前T028容量选择有关，不恢复暂停的泛化资源优化。H不能宣称立体声独立处理、参数无爆音或模拟延迟。
当前生产RTL、公共包、顶层、GPRJ/CST/SDC、算法和可视化均未修改。所有原日志和新检查产物存output/M3_E_F_evidence_review_20261004。

反馈待用户转发，尚未送达。
