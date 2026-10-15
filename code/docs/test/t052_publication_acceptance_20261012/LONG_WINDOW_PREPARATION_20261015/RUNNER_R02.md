# T052 长窗首沿修复与受限 runner R02

对应 M2 V0357–V0358 的新补件要求。仅在原授权三个新长窗目录新增软件、修改新 TB/准备检查；没有修改冻结 DUT、ROM、旧 capture、旧 JSONL 合同或原 R01 ZIP。`T052_LONG_PUBLIC_HEX_V1` 已由 M2 接受为本次专用格式，但本次仍**没有 RTL 编译/采集许可**。基础四声部及唯一 SHA 的现场 SRAM 诊断优先级不变；AI 没有执行设备操作。

## 首沿与版本

TB 的 negedge 条件增加 `$time > 0`，排除 t0 X→0。新 TB SHA：`daf67848153214d791d1f51e348dbbe7c7995c06424f0a819a23080c1fba3e20`。详见同 TB 目录的 `ROW0_STATIC_PROOF.md` 和源码绑定的7项纯软件测试。它们核实10ns首正沿 row0、20ns读 row1、全8536336沿连续、170726710ns最后一沿、+1ns结束；旧无保护/#0变体拒收。不是 HDL 调度仿真实测，实际编译器行为待许可后验证。

controls 原件仍是375598784字节/SHA `fd220e83da98c03f0181c0a45e4edfa2ddc77adda055911508e7f7469131d4d0`。M1 R01、冻结源码/ROM及完整输入不变。A/P/C=8207/8201/6只是独立静态预期，旧4207完整性仍 UNKNOWN。

## runner 防护和失败语义

`bounded_runner.py` 默认锁闭；仅有 `--approval` 不执行，返回3。`--execute` 还要求 M2 新精确确认 JSON、完整确认 SHA、全新拒收收据路径、机器/环境/源/工具/冻结输入身份、ASCII 全新 cwd、已有且唯一的额度目录及≥2GiB空闲盘。JSON 本身不是数字签名：`approved=true` 必须来自用户转发的 M2 新准入决定，不能自行改为 true。本件的 `LOCKED_PROPOSAL.json` 始终 false。

- 先持久独占创建 `attempt.consumed.json`；每步启动前再独占创建 compile/run/check 消费文件。失败、超时、崩溃也不删除；不自动重试，不借旧许可。M2 必须固定同一个额度目录；删标记、另建目录、更换 approval_id 均不能自动获得新许可。
- 用 Windows `CreateProcessW(CREATE_SUSPENDED)` 创建工具，先加入带 `KILL_ON_JOB_CLOSE` 的 Job，再 ResumeThread。子孙默认继承 Job，禁止 breakaway；不用 PID-only/taskkill。Job 无法分配时失败关闭。
- 单步90/300/300s、总调度900s（复制/核验也计入总预算）是上限模型，不是本次执行授权。正常 root 退出后允许至多100ms Job 计数收敛，仍在原 deadline 内检查文件/流；残留子树拒收。失败时终止 Job、至多2s确认清空及根退出码，保留实际清理耗时；不能把清理时间冒称实时硬截止。
- 捕获计入三轨迹及各步 stdout/stderr，不计独立 controls；总输出包含 controls、源码、工具产物和收据。两路 stdout/stderr **每路16MiB**精确截断写入并标明不完整/FAIL；被截断的数据不伪造为完整双流。
- 模拟器直接写的文件每≤50ms轮询，超750MiB捕获或1200MiB总输出立即终止整棵 Job并拒收，保留超限原文件。**这是动态阈值监督，不是 NTFS 硬配额；调度、文件写速及轮询之间可能瞬时超量。**不保证任何时刻磁盘字节都不越线，也不为满足数字而事后截断 capture。M2 复核精确组合时须接受这一边界；若要求内核级零超量，当前未实现，必须另定文件系统配额或代理捕获方案与授权，不得据此直接放行。
- stdout/stderr 即使 exit0，含 Error:/Fatal:/Failure: 诊断也拒收；编译没有非空 long.vvp、运行缺唯一结束标记、任一捕获缺失/为空、checker不匹配均失败。缺原始流不能成功。
- 原离线 checker 不改：真实全沿匹配也返回3/PROVENANCE_NOT_VERIFIED。runner只允许其严格预期 exit3、完整数量及捕获 SHA 对应，最终仍是 `RAW_ATTEMPT_FINISHED_PENDING_M2_PROVENANCE_REVIEW`，**不自行签完整 T052 PASS**。缺沿/INCOMPLETE同样exit3不会被接受。
- 输入、TB、工具、全部 checker/runner Python源及工作副本前后核 SHA，编译产物绑定到运行/检查。环境只保存全量环境的 SHA，不泄露值；版本使用原真实 metadata 记录，静态 DLL 库存仍不是动态加载闭包，实际加载依赖 UNKNOWN。批准后环境变化需要重新核精确组合，不能绕过身份检查。
- OS强杀/断电时不承诺一定能落最后一份 JSON。持久消费、started/launched 和原双流保留；缺最终收据必须 INCOMPLETE，绝不凭退出0/标记补造成功。

## 可重复的软件命令

在仓库根目录使用已有 Python，不安装、不联网、不启动 HDL：

```powershell
$py = 'C:\Users\songdongkuan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -B -X utf8 code/software/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015/run_runner_preparation.py --prepared code/output/m3_t052_long_preparation_20261015_03/prepared --output code/output/m3_t052_runner_revision_20261015_NEW
```

所有输出必须全新。入口执行 row0 静态证明、Python假进程正负例、当前来源/工具哈希和锁闭提案生成，保存源码快照、真实 argv/cwd/双流/退出码/耗时及前后 SHA。不会调用 `bounded_runner.execute`，不会设置批准为 true，也不会创建实际尝试额度目录。

假进程测试真的使用本机 Windows Job 和 Python子孙，不是模拟 Job API；其文本/合成 capture **不是真实RTL捕获**。覆盖正常退出、两流溢出、直接捕获/总输出溢出、单步/总预算超时、root退出但子孙仍活、非零码、exit0含错误、重复消费、身份/环境/许可/预算错误、缺/空原件、缺/重复标记；子孙停止还核创建 FILETIME 和心跳，不仅凭 PID。

完整 compile→vvp→checker orchestration 尚未在真实工具上运行，首次实际执行及两个可编译 RTL 行为反例仍待 M2 新许可。七项旧数学、128沿、T060 H 不重跑；仓库九门禁的既有 smoke 与新长窗编译/采集分别记录，不能混称本轮真实长窗通过。

## 失败历史、交接与待验

首轮假进程 `_01` 为24例22通过2失败：正常 root 退出后 Job accounting 计数滞后，normal/missing_marker 被误报残留。保留原始双流/失败收据；增加有界计数收敛检查后 `_02` 27/27通过。另发现终止后 root 退出码短时未可取，已在同一最多2s清理窗口内等待真实退出码，不能用 null 充成功。`_03` 自审修复进程身份查询：AccessDenied不等于已退出，只有确认不存在的错误才记消失。以上旧日志不覆盖。早轮测试只记录源码 SHA、未预先保存全套失败源码字节，明确缺口；新轮起保存实际测试源码 ZIP。后续完整实际结果及文件 SHA 见本目录新封存包/manifest/收据，不回填早轮。

本件只交 L0静态与软件假进程防护证据。请 M2 复核新 TB/observer、冻结源/ROM、完整 controls、runner/Job、工具/环境/命令、实际输出名、额度目录及阈值边界，再决定一次编译/运行；当前额度为0。动态 DLL、实际吞吐/完整采集、PCM数学、138K音频、板级电气、发声及旧4207闭合全部未验。

待用户转发，尚未送达。没有预占 T/V/D 编号，没有修改共享状态表。
