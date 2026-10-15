# A 返工：7 ms watchdog 隔离候选真实功能通过

2026-10-16，机器 LAPTOP-KSS1MRR7，Git 基点
0513926eae41c698e24aaa47386b6d7c701383af。本窗口未 Git 写，整体发布仍由总控安排。
本说明更新当前结论；旧 README/FAILURE_HISTORY/SEAL 的错误说明保留作历史，不应继续沿用。

## 已定位、已修复

1. 原 `PREFLIGHT_2020_02` 并非 623：真实进程已创建，退出 1，stdout 为 290 字节
   `Usage: vlib -help`，SHA `05fe090e741f1c155ac12f3b0e3b8c71173a9bd65a0bfbb10bdac19c9e551d9a`。
   `vlib -version` 是自有预检错误。现在按 `vlib -help`＋原 EXE/安装元数据 SHA、
   `vlog/vsim -version` 的 SE-64 2020.4 实际横幅联合核身份，不把 help 冒充版本横幅。
2. STARTF_USESTDHANDLES 原来给 stdin=NULL。修为可继承只读 NUL，仍暂停创建、
   先放入 KILL_ON_JOB_CLOSE Job 再 Resume，记录 CreateProcess 返回值、创建事实、PID、
   失败阶段和 winerror，清理构造失败的句柄。NULL stdin 不能据此认定为 623 原因。
3. 修后受限环境的 `REWORK_PREFLIGHT_01` 明确 CreateProcessW 返回 false、Win623、
   无返回 PID/句柄，尚未执行 Assign/Resume。经平台正常批准的同工具调用随后成功。
   没改系统文件/缓解/注册表/永久环境/工具/许可证，也没换工具版本；未证明具体哪个 DLL
   导致受限环境中的 623，不能声称安装坏或底层加载问题已修。
4. 首轮真实 R05 在 6 ms 触发冻结 TB watchdog。静态核原 TB：17 字节×320000 ns，
   加初始/固定等待，END 最早6326000 ns、PASS 最早6327000 ns。旧6000000 ns上限
   必然先到。用户直接追加“允许继续解决这个问题 最终要A通过”，据此新增 A 隔离副本，
   仅 watchdog 6000000→7000000；3516字节中仅一个数字字符改变，反向恢复原 SHA。
   所有事件、等待、断言、算法、ROM、接口和正式工程原件保持。

候选 TB SHA：24e7407f6abfcc28ed9dd886f41539e8f07b64da6e67c5932abbe504f6b5096a。
原 TB SHA：6e677154d0a53ff97e794555ef57695e385a9963de43f1ac9135a54c32fc9777。
原 ZIP SHA：dcf15f5d3ded1a0b160f55eab43066c728f80b3c329c44ea9f099c63f178696a。

## 原始执行及消费

| 执行 | 实际结果 | 额度 |
|---|---|---|
| 历史 RUN_01 两条、PREFLIGHT_2020_01 | 623；缺足够 API 阶段，旧进程创建事实保守 UNKNOWN | 不是功能轮，不能回填成新运行 |
| 历史 PREFLIGHT_2020_02 | vlib -version 创建成功，exit1 Usage | 预检进程确实创建，单列记账 |
| REWORK_PREFLIGHT_01 | 新 vlib -help，CreateProcess false/623，功能0 | 没创建本次预检子进程 |
| REWORK_AUTHORIZED_RUN_01 | 3预检＋3功能工具，vlib/vlog/vsim退出0；vsim原 Fatal TIMEOUT，checker退出1 | 首轮标记已消费，保留 |
| REWORK_WATCHDOG_RUN_02 | 3预检＋3功能工具，全部退出0；真实PASS＋回执核验退出0 | 新用户修复轮标记已消费，保留 |

本轮不再有可自动使用的额外轮次。功能启动累计6（两轮，每轮vlib/vlog/vsim），
新预检尝试7（一次623＋两轮各3）；加历史4次共11次预检尝试。
历史三条623创建事实UNKNOWN，一条Usage确认创建；本轮预检6创建、1未创建。
两轮合计17次 ModelSim启动调用尝试，已知13个成功创建、1明确未创建、3历史UNKNOWN。
此统计不包括 Python 自测、软件审计及 C/B/D 的执行。

首轮调度13.406秒；修后调度3.844秒，vlib0.078、vlog0.156、vsim2.781秒。
所有工具 wall-time timeout=false，均小于300秒/工具、900秒/轮。
首轮是 TB 的6ms仿真时间 watchdog，不能写为300秒工具墙钟超时。

修后原日志：6接受、4活动声部、303提交、258非零提交、303帧、serial=3905，
DUT自报max_cycles=35；在6327us输出整行PASS。三步骤六原始流齐套（空流也保留），
七条编译/优化警告等以原日志为准；无 Error/Fatal，源码/工具/stage前后 SHA 不变。

## 自审和失败保留

`REWORK_SOFTWARE_08`：12新增测试＋20既有测试通过，外层两条命令退出0。
覆盖 NULL stdin 的调用前合同拒收、新 NUL 的实际 EOF、模拟 CreateProcess623、
Assign/Resume/消费回调失败、错误/错版本/安装漂移、超时/进程树/日志上限、
7ms候选只能改单一字符、重复第二消费拒收。假进程/合成数据明确标注，不冒充 ModelSim。

软件01–04失败为测试自身错误假设/代理实现，均保留原日志和执行源码：
01假设旧NULL stdin一定使Python stdin为None，但实为读取阻塞并被4秒终止；
02/03错误假设子进程GetStdHandle/GetStartupInfo不受宿主/CRT处理，实际句柄非NULL；
04代理未缓存函数导致restype丢失。05纠正为调用前精确合同检查后通过；06加诊断词负例；
07识别编辑器给候选新增了末尾LF，拒收；移除仅此格式差异后08通过。
旧包装的故意失败负例产生ResourceWarning原样保留，修后包装关闭构造失败流。
所有软件失败都不是 ModelSim 重试；无原样盲重复真实工具。

执行脚本/完整argv/cwd/退出码/原始双流/哈希在各RUN_RECEIPT及封包清单内。
标准启动句柄依据：https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/ns-processthreadsapi-startupinfow

## 限定结论与交接

A这份 **watchdog 7ms复制TB的真实R05隔离功能候选**通过，checker为
CONSISTENT_PENDING_M2；原6ms版本仍失败，不能回填为通过。
不将303次提交或DUT max35扩写成四独立频率到输出、逐请求833拍、串行左右逐样本
解码或模拟≤10ms；冻结TB没有这些轨迹。额外observer仍仅静态，不冒称本轮编译。
动态加载DLL闭包未测；库/许可至少支持本次实际编译/仿真，不能由此宣称任意工程可用。
新候选没有新的Gowin/整机STA/设备证据，board_release_allowed=false。
B/C/D没有新增执行。没有联系3/5/审核窗口，没有Git提交或推送。

给总控/M2：请核原失败与新成功两轮原始流、watchdog唯一字符差异、新用户授权记录、
同工具/输入SHA及两份消费标记，按隔离候选L2范围签收。整体发布仍暂停，待总控串行安排。
待用户转发，尚未送达。
