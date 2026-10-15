# 开发故障与保留范围

## 首次只读原报告探查（exit1）

实际命令形态：本机 `C:/Users/songdongkuan/miniconda3/python.exe -B -X utf8 -c ...`，
将新目录加入 sys.path、导入 endpoint_audit、只读原 ZIP 的 pnr/timing.html，然后调用 parse_report。
首实现把方法命名为 `offset()`，与 HTMLParser 自身的整数属性 offset 冲突；首次 feed 在 Table创建处抛出
`TypeError: 'int' object is not callable`，工具返回 exit1，未产生 timing PASS，没有 EDA调用。
修复为 `char_offset()`，同类只读探查 exit0，实际解析269行。该临时探查只有对话工具返回保留，
未落完整 argv/-c字面量与独立原始双流文件，**不补造首失败收据**；它不是正式交付测试轮次。

## R01（exit0，原件保留）

有界统一 runner 实际10次纯软件子进程，23项单测，原报告指定音频pair按MISSING_SETUP退出1；
合成正例exit0及七反例exit1/诊断正确。完整原始双流/命令/执行前后源码SHA保留 `runs/R01/`。
该轮后自审增加可见报告错误诊断拒收及 sys_clk 绑定对象空值拒收，并补八种诊断位置/零计数/空对象测试，
因此 **R01源码SHA不代表最终交付源**，不用R01代签补强后源。
随后主控指出真实候选是FF→RAM/ROM pin，R01仅双get_regs定向字符串的支持范围过窄；
在同一软件写集修正为from get_regs、to完整get_pins，转义实际lane/bus索引，FF/D保留两个合法collection形式，
增加RAM误当FF、未转义/错索引、FF/D、FF/CE的纯软件正负例。原R01不覆盖这项后继。

## R02（最终限定软件轮次）

以 `runs/R02/RUN_RECEIPT.json` 为实际结果，独立新输出/拒覆盖。只做新增纯软件检查与原始报告解析，
没有重跑任何旧 RTL、ModelSim、Gowin或设备操作。最终封包仅以 R02 测试源码为准；R01历史仍保留。
