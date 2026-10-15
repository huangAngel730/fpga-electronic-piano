# T052 静态来源绑定后继：结果与交接

日期：2026-10-15。岗位 M3；任务 T052。待用户转发 M2，尚未送达。

## 范围与实际变化

开工实际 HEAD 与 origin/develop 为 `e9faa3f1591ad1640a2f68d89db5134973c7684c`；工作树原本干净。查实已有长窗工具已经发布，M2 复核 17 项软件自测通过，故本次复用其驱动、公开端口观察器、独立事务日历和长窗 checker，不重写或重跑已签组。只新增准备包身份绑定检查、34 项新软件测试和固定 Python-only 留痕 runner。

新增软件文件位于 `code/software/t052_publication_acceptance_candidate_20261012/static_binding_successor_20261015/`：`static_bundle.py`、`test_static_bundle.py`、`run_software.py` 和 `README.md`。本目录新增此交接说明、封存脚本、封存 ZIP 及收据。旧准备、旧源码、旧封存和共享状态表未修改。

补充检查覆盖固定输入、预期账本、M1 确认、源闭包、TB 副本、冻结归档与成员、ROM、工具库存、argv/cwd、预算／输出上限／仿真窗口，以及检查期间漂移；任一矛盾拒收，不通过修改旧 proposal 求绿。

## 运行、结果与失败历史

使用已有 Python：`C:\Users\songdongkuan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`。在仓库根执行：

```powershell
& 'C:\Users\songdongkuan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -X utf8 code/software/t052_publication_acceptance_candidate_20261012/static_binding_successor_20261015/run_software.py --output code/output/m3_t052_static_binding_20261015_r03 --prepared code/output/m3_t052_long_preparation_20261015_03/prepared
```

- R01：沙盒临时目录拒绝创建/清理夹具，32 项测试出现环境错误，runner 退出 1；未进入真实准备包检查。失败 stdout/stderr、源码快照和实际退出码全部保留。
- R02：经运行权限审批，换用全新输出目录执行相同代码，32 项软件测试通过；现有准备包静态核验通过，runner 退出 0。
- R03：自审补充输出上限和仿真窗口不可放宽规则及两个负例；最终 34 项软件测试通过，静态核验通过，两步骤均退出 0，runner 退出 0；源前后 SHA 一致。

三次记录均在 `code/output/m3_t052_static_binding_20261015_r01` 至 `r03`，均未覆盖。精确 argv/cwd、Python 版本与 SHA、耗时、原始双流及文件 SHA 见各 `receipt.json`。最终 `static_identity.json` 保存实际逐文件身份；新 ZIP 保存最终源码和全部三次原始软件运行记录。该 ZIP 不重复收纳 375 MB 控制文件；完整控制原件仍在原长窗封存 `LONG_WINDOW_PREPARATION_20261015/T052_LONG_STATIC_R01.zip`，交接时两包一并提供。

当前新增任务的实际验证仅静态／软件 L0/L1：HDL 编译 0、RTL 运行 0、EDA 0、设备 0。下文仓库发布门禁若运行，其既有烟测独立记录，不计入新 T052 长窗结果。

## 自审与未验边界

- 正式 CLI 无测试夹具覆盖开关，无缩窗开关；软件测试的小夹具明确不是真实 RTL。
- proposal 中的编译／运行命令仅核身份，绝不执行。
- 输入与预期账本的固定 SHA 沿用已发布 R01；M1 算法、定点、频点和隔离 50 MHz/1042 拍条件未改变。
- 工具为静态库存，不是动态加载闭包；静态匹配不认证操作者、执行机器或未来采集真实性，不签发 M2 许可。
- 真实长窗 RTL、可编译行为反例、PCM 数学、HOLD 数据数值稳定性、active/clip、40 MHz 整机、STA 和上板均未由本后继验证；旧 4207 完整性 UNKNOWN，完整 T052 PARTIAL。
- 默认自审，未启用审核员／预审员制度；不编辑任务看板／当前状态，不预取编号。

## M2 接手的精确事项

请核本次新增 diff 与封存原件，确认来源绑定工具只签静态身份；本次没有申请或消耗新的 RTL/EDA/设备额度。若后续确需真实长窗执行，再由 M2 单独核源、工具、机器、一次执行范围、预算、进程树／文件上限、消费标记和来源收据，不能因本工具返回 0 自动启动。

仓库发布门禁原始记录计划保存在 `code/output/m3_t052_static_binding_publish_gate_20261015_r01/`；其结果、提交号和远端 SHA 以最终交付消息及实际 Git 为准，本文件不提前宣称发布成功。共享状态／验证编号的登记信息交 M2 统筹。
