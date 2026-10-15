# T052 静态来源绑定后继

本后继复用已经发布的 `long_window_preparation_20261015`。已有 driver、薄 TB、公开端口 observer、独立事务日历及长窗 checker 均保持原样。本次补充准备包的独立来源绑定检查、软件负例和保留原始双流的运行入口；不编译或运行 HDL，不重跑已签 128 沿、17 项旧软件组或 T060。

## 文件与职责

- `static_bundle.py`：核 R01 固定输入与预期账本、M1 确认、当前软件源闭包、TB 副本、冻结 ZIP 成员与 ROM、工具静态库存、命令和预算提案；检查前后 SHA 一致。
- `test_static_bundle.py`：使用明确标记的软件小夹具验证正确包及版本漂移、漏源、错源、ROM/工具漂移、改命令、伪许可、伪证据等级和拒覆盖等负例。
- `run_software.py`：只启动两个固定 Python 入口：本后继的软件自测和可选的准备包静态检查；保存 argv/cwd、原 stdout/stderr、退出码、超时、源码快照、Python 身份与源前后 SHA。失败即停，无自动重试。

## 使用方法

在仓库根目录，用已有 Python 运行；输出目录必须是 `code/output/` 下全新目录：

```powershell
$py = 'C:\Users\songdongkuan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -B -X utf8 code/software/t052_publication_acceptance_candidate_20261012/static_binding_successor_20261015/run_software.py --output code/output/m3_t052_static_binding_NEW --prepared code/output/m3_t052_long_preparation_20261015_03/prepared
```

不带 `--prepared` 时只做本后继的新软件测试。每个子步骤上限 60 秒。不会再生成 375 MB 输入，不会执行准备提案内的 `compile_argv`、`run_argv` 或 `check_argv`，不会查询或调用 Icarus、VVP、ModelSim 或 EDA。

静态核验返回 0，仅表示 `STATIC_IDENTITY_MATCH_ONLY`；缺文件／访问不可用返回 3；矛盾、改源或合同变化返回 1。输入准备包必须能在当前本机原路径访问，不能修改旧 proposal 迁就不同机器；迁移需单独准备新的路径绑定。本机记录中的工具版本是既有元数据，静态库存也不是实际动态加载闭包。

R01 固定身份来源：已发布长窗准备 `plan.py`、M1 确认 SHA 和原 `prepared/proposal.json`。输入 `controls.hex` 为 375598784 bytes、SHA `fd220e83da98c03f0181c0a45e4edfa2ddc77adda055911508e7f7469131d4d0`；预期账本 SHA `5096c3ce4596574efb0c9e13629e27ae9b27f49d0a7e777c39cf324c80f136f6`。只有测试进程内的软件小夹具替换这两项身份和 M1 夹具身份；正式 CLI 没有缩窗或绕过开关。

## 验证和边界

- 当前结果最多是静态／软件 L0/L1，不是真实长窗 RTL 采集、PCM 数学、声音、整机或实物通过。
- 50 MHz／1042 拍与低有效复位的条件沿用冻结隔离输入；不更改引脚、时钟、复位或采样率。它不是 138K／40 MHz 的 833/834 拍合同。
- 静态核验不判断审批人身份，不签发许可，不证明原文件真实性或未来执行来源。`execution_authorized=false`、`complete_T052=false`、旧 4207 完整性 `UNKNOWN` 始终保持。
- 现有长窗 checker 即使事务匹配仍返回来源待核；本工具不会把它的返回 3 改为实际 RTL PASS。
- runner 的墙钟／进程树／文件上限及单次消费控制仍是未来真实 RTL 执行器的独立门槛。本后继不实现或启用该执行器，不恢复任何已消费许可。
- 若新的有效输入合同或源版本改变，应新增精确后继并由 M1/M2 核定，不能改旧封存或放宽本检查器求绿。
