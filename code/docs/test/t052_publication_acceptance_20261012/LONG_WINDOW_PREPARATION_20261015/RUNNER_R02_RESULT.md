# R02 实际软件结果与 M2 交接

基线：`e2200b2571afe3c38807a2d8ee2e4264c5881fd8`。本轮交接针对 V0357要求的 TB首沿修复、受限runner原件及假进程负例；不接管其他窗口的音频STA准备，不改共享表。原R01 ZIP完整SHA仍为`43d2c43ce0a59fc1c91dd09b2c6842ef40b856b3de74d66f4c513706e0275252`，新包内原字节保留，不冒称它包含修复后TB。

## 实际命令与结果

在仓库根目录执行：

```powershell
& 'C:\Users\songdongkuan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -X utf8 code/software/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015/run_runner_preparation.py --prepared code/output/m3_t052_long_preparation_20261015_03/prepared --output code/output/m3_t052_runner_revision_20261015_01
```

退出0／`SOFTWARE_PREPARATION_PASS`；源码前后完全核同。子命令 row0、fakes、proposal 均退出0。row0软件检查7项，假进程检查29项通过。全量原始双流、每个失败case的实际退出/终止原因、子孙身份与停止证据、源码快照、命令/耗时/依赖SHA在该输出原收据及新ZIP中。

新TB：`daf67848153214d791d1f51e348dbbe7c7995c06424f0a819a23080c1fba3e20`。

新runner：`f55d19ac0584b8e483c7a7299c841b804ba1ebbe261c06194af33c12e6d5e10b`。

精确锁闭提案：`code/output/m3_t052_runner_revision_20261015_01/LOCKED_PROPOSAL.json`，SHA `2a05f0fdff73b4f65c8c7898535b12369055fccdb36f21e1fe0eea756d8611f9`。它绑定当前TB、全部Python源、冻结输入与DUT/ROM、已有工具静态库存与原版本、Python、机器/环境SHA、确切argv、拟用cwd/额度目录及上限；`approved=false`。新ZIP保存原件；所有文件完整SHA以其MANIFEST逐项列明。

首次真实Python假进程 `_01` 24例中2失败，证实Windows Job退出计数滞后；失败原收据和双流保留。修复后 `_02` 27通过；身份查询AccessDenied处理硬化 `_03` 27通过；新增优化模式拒收/源码快照/元数据夹具等 `_04`、`_05`及主入口final轮继续保留。早三轮只有源码SHA，没有预存失败源码字节；这是明确历史缺口，不伪造快照。旧失败不回填PASS，软件反例不称RTL行为反例。

## 改动范围

仅三条既有授权新目录内：

- TB目录：修改`tb_t052_long.sv`，新增`test_row0_schedule.py`、`ROW0_STATIC_PROOF.md`。observer未改。
- 软件目录：新增`win_job.py`、`bounded_runner.py`、`fake_process.py`、`test_bounded_runner.py`、`propose_runner.py`、`run_runner_preparation.py`；prepare增加t0防护文本检查，README指向新补件说明。旧checker/FSM/数据合同未改。
- 文档目录：新增本结果、`RUNNER_R02.md`、新封存脚本/包/收据；旧ZIP、旧RESULT及旧门禁原件不覆盖。

静态核对方法：`git diff --check`；新package ZIP CRC及每成员字节/完整SHA逐个重算；新源码与测试前后SHA比对；新capture格式与M2 V0357逐条对应。仓库九门禁独立原收据随最终交接附上，不以普通门禁推断新T052 RTL编译通过。提交/推送身份由最终发布回执列出，本文件不预占提交号或T/V/D编号。

## 必须保留的边界及请 M2 决定事项

当前等级仅 **L0静态与软件假进程检查**。新长窗RTL编译0、实际采集0、EDA0、设备0；旧4207完整性UNKNOWN，T052整体PARTIAL。已签128沿与T060 H未重跑。

请 M2 先核新精确组合及完整SHA，再决定一次compile/run/check：不复用旧额度，未签前不开跑。尤其请确认：

1. 直接捕获文件采用50ms动态监测超阈值后终止，允许瞬时超量；stdout/stderr每路16MiB精确限写。此实现不是NTFS硬配额，不能承诺任意时刻始终≤750/1200MiB。如果要求零瞬时超量，现候选不能满足，不准以假进程拒收结果替代该决定。
2. 900s为监督调度上限；失败树清理另最多2s，后置SHA/最终收据耗时独立记录。OS强杀/断电缺最终收据就判INCOMPLETE。实际吞吐未测，不加预算、不缩窗。
3. 只提交raw pending review，不把原checker exit3改为PASS；动态加载DLL仍UNKNOWN；完整compile→vvp→checker未真实运行，两个可编译RTL行为反例仍待另定范围。

基础四声部/现场一次指定SHA SRAM诊断顺序不变。当前AI未做下载或仪器测量。M2负责准入与最终签收，本轮**待用户转发，尚未送达**。
