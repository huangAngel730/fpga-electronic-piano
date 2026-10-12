# C 最小补件：B 复位尾段与剩余总预算 runner

2026-10-12，M3。依据 Callback3 的 V0295 后续任务。仅软件 L0/L1 准备，
不是 RTL 补采通过；完整 T060/T061 继续 PARTIAL。共享编号、正式登记由 M2 收口。

## 改动与冻结

`fixtures.py` 仅在 B 加 1510 rst_n=0、1514 rst_n=1、1518 原 A4/900 NoteOn、
1540 frame。去掉这四项后，按原 JSON 编码精确恢复旧 B SHA
`41dd5f908a04adce266b65c36b177175ce22ee8e50eb7db1299c212a715308b1`。
原 105/424/725/1033 四取消点与 end1600 保持。
新 B SHA `288eff5d6d0249997adf7dd52a487d37b8d31f624695c332f77ba75bbe9ceee1`；
A 计划 SHA `dc05bc68552b81e782db2ad0a7edf3c2e8f1278cb89728316dc7c4c3a63277e5`。
A 只复制/生成计划，没有执行 A 长软件轨迹。

新增软件尾段检查：在途复位、第二 epoch、1514 首沿全域清零、1571 epoch2/ID1
新提交以及完整脏复位反例拒收。1600 拍 B 前缀只是建立后缀状态，未重跑原22项专项。
清零与1571提交均为 `SYNTHETIC_SOFTWARE_TEST`，不得称实际 RTL 命中。
`fsm_oracle.py`、四数学依赖、业务19源、ROM、薄TB/observer没有修改。
V0295 旧主体/旧22项/A自然4800 tick结论仅标 REUSED；旧 seal 与失败不回填。

新增文件：`controlled_runner.py`、`windows_job.py`、`future_mutants.py`、
`prepare_followup.py`、`test_followup.py`、`run_followup.py`、`deliver_followup.py`。

## 受控入口

准备产生 `portable/CONTROLLED_CONFIG_NOT_AUTHORIZED.json`，固定精确源/ROM/
计划/下位命令/TB/observer/oracle/实际本机工具 SHA 与版本原始日志。
默认 `execution_authorized=false`，调用不带 approval 时只做身份预检，工具步骤为空。
不会因软件通过自动放行。未来必须 M2 明确放行这个 config SHA，另提供
authority=M2、execution_authorized=true、groups=[A,B]、attempt=1、notice 的独立 approval。
当前没有生成真实授权文件；单测中的假授权只测试身份/原子占用，不调用执行分支。

未来执行会独占创建 `ONE_SHOT_ATTEMPT.json`，一次失败同样消耗本包尝试，不重试。
新输出根/组目录，不复用已有 allocator/vvp/capture；从封存副本构建，不引用旧工作树。
两组各自 lower/compile，不声称共享编译；实际编译源/include/observer及生成allocator
独立列 SHA。原 ROM/include 路径重定位 diff 与56输入原件保留，可逆回原身份。

900秒从读取配置/预检开始，所有步骤用 `min(分项上限, 剩余总预算)`：
lower<=90、compile<=90、每组capture<=300、每个软件步骤<=90。
预检、复制、四完整定向坏capture生成/拒收及后置输入/工具不变检查均计入总预算。
预算不足即 FAIL_PARTIAL；不把分项上限相加当作900保证，不自动加限/换种子/重试。
超时后的安全清理和写失败证据也计入实际耗时；即使清理带来尾部超限也不能 PASS。

Windows 子进程以 suspended 状态创建，先加入本次独立 Job Object，再恢复执行；
超时 TerminateJobObject 只清本次树，关闭句柄也终止后代，不按工具名杀进程。
记录原命令/cwd/PID/原stdout/stderr/实际退出/有效timeout/partial产物SHA。
本次假 Python 父子进程检查真实验证了超时后子进程未留下延迟标记。
正常capture后仍必须精确 plan-bound checker，随后四个完整单字段目标反例指定非零
拒收。该未来路径尚未执行；软件通过不等于真实工具链全流程通过。

## 本机工具身份差异（须 M2 预检）

只读四次查询：Yosys `-V`、Icarus `-V`、VVP `-V`、显式加载 slang 插件后
`help read_slang`；未输入 HDL、未 lower/编译/运行新音频 RTL。
安装根 `D:/Gowin/oss-cad-suite`。实际 Yosys **0.69+75 / f0b945f63-dirty**，
Icarus/VVP **14.0 / s20260301-474-g5591c2dde-dirty**。
不是 M2 原回执的 Yosys0.68+206，不能冒同工具身份。
固定三可执行文件、Python、slang.so、bin/lib DLL、lib/ivl及share/yosys数据/插件的
保守依赖集合 SHA。工具本身不打包分发，只交身份、路径和查询日志；移机需重新预检，
不能改 config 后沿用旧批准。

## 运行及证据

新增软件检查命令（全新目录，拒覆盖；总300秒/步90秒，无原22/A长例）：

```powershell
& 'E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe' -I -S -B -X utf8 code/software/audio_math_acceptance_candidate/t060_minclosure_20261011/run_followup.py --output code/output/<NEW_C_FOLLOWUP> --suite D:/Gowin/oss-cad-suite
```

原首轮失败 `_01`：沙箱拒 taskkill，后代延迟标记出现，测试正确失败。修复采用 Job Object。
第二轮 `_02`：13项之前版本的11项新软件通过；版本查询缺少套件 lib PATH，
Yosys退出3221225781，修正仅查询环境；失败原件保留。
`_03` 是新增原子占用测试前的软件通过中间轮，不冒最终源码收据。
最终收据、原日志、源前后SHA、默认锁闭和隔离后缀检查见本目录新的 FOLLOWUP_SEALED。
所有轮独立新目录；不是 runner 失败后自动重试真实 A/B。

发布需精确索引树九门禁全通过，保留必需短 T007/T019，不能写成本任务新 RTL 补采。
Git 普通 develop 提交/推送和实际门禁以交付收据为准。
待用户转发 M2，尚未送达。下一步由 M2 核复位/预算/本机工具差异，再决定精确唯一 A/B。
N32帧事务纯软件任务另行独立提交，不混入本补件。
