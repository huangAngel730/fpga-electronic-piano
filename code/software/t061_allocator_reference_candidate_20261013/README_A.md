# N32-A 平衡分配器独立后继

最新结果（2026-10-14，用户再次授权实际修复）：已通过正规批准的非沙箱
环境解除编译崩溃，实际完成原 18 步功能自检：N4/N8/N16/N32 共 4472
正常比较沿通过，两项真实 RTL 行为反例指定拒收，父监督 20.641 秒退出 0。
见 `ENVIRONMENT_RECOVERY_20261014.md` 和
`SEALED_FUNCTION_RECOVERY_RESULT_20261014_R01`。没有改业务 RTL/算法，
没有 Gowin、物理时序或设备操作，完整 T061 仍 PARTIAL；尚未提交/推送。
以下“未执行”说明均属前一准备阶段，不覆盖本条最新实际结果。

本轮最新边界（2026-10-14 用户更新）：主窗口与子智能体自行完成编译故障诊断
及可审核、未执行的修复方案，暂停中间送审，不等待 M2 复核。当前诊断结论和
实现说明见 `DIAGNOSIS_AND_REPAIR_20261014.md`。下文旧送审记录保留为历史，
不作为本轮准备工作的额外前置条件；本轮不宣称已修复实际编译崩溃或 A 功能通过。

2026-10-14，M3／主对话2。原任务为 N32 独立候选 A；当前内容为新 RTL、逐沿独立参考、向量和有界执行计划。状态与实际结果以后置收据及同版审核汇总为准，不预写仿真、综合或时序通过。

## 基线与接口

工作基线 `0b5f45388f974ce4ae0a2081eac7add93181c32a`。任务单引用的临时生成路径 `code/build/138k_polyphony_resource/prepared/N32_R1_20261011_01/sources/b2c_voice_allocator.sv` 本机不存在；仓库持久路径 `code/rtl/common/polyphony_scaling_candidate/b2c_voice_allocator.sv` 实际 SHA256 为 `9fec9f838a9ef333d01d1b79ecf77d137e41bc0c5e78a40d2820c37739506061`，逐字节身份与冻结基线相同。prepare 从该持久原件复制精确字节，实际执行只读本轮 capsule，不修改或补写旧生成目录。

新模块 `code/rtl/common/m3_n32_allocator_candidate_20261013/m3_balanced_voice_allocator.sv`，名称 `m3_balanced_voice_allocator`，参数 `N=8, SW=$clog2(N)`；本任务支持 N4/N8/N16/N32。原输入 `sys_clk/sys_rst_n/note_on/note_off/source_id/channel_id/midi_note/release_done` 及四公开输出、拍数、槽打包格式保持。单时钟，低有效异步复位；槽宽为 `18+SW`。

已阅读父目录硬件索引、BOARD_CONTEXT 和项目协作规范。本任务是无引脚的隔离数字模块，仿真时钟由 TB 提供，不增加物理时钟、不改正式时钟/复位/端口/约束，也不使用资料中尚待确认的外设电气参数。

## 结构与沿语义

- 每槽并行计算身份匹配、IDLE、旧年龄与槽号；平衡树按“身份匹配 → IDLE → LRU”归约。
- 匹配与 IDLE 选最小槽号；LRU 选最小年龄，同龄选最小槽号；同时传递被选旧年龄。
- 年龄与目标字段按槽并行写回；不存在选择目标后动态索引年龄的反馈串链。
- release_done、note_on、note_off 按原顺序覆盖相关字段，所有条件读取沿前状态。同沿完成释放不立即变为 IDLE 候选。
- NoteOff 对全部旧 active 身份匹配槽生效，公开 release_slot 取最大匹配槽；无事件时两个 slot 输出保持。
- N32 选择归约深度五层是源码结构说明；综合资源、PnR 和 40 MHz STA 尚未执行。

## 独立参考与覆盖

`reference.py` 以 Python 候选集合/min 规则和旧状态副本计算下一状态，与 RTL 平衡树结构独立。比较所有四公开输出和全部 packed 槽字段；期望由输入重算，向量内 expected 也核对，拒布尔冒整数、缺行/多行/字段或槽数不符。

`vectors.py` 固定 seed `0x3261`，每 N 含 1024 随机沿和定向填满/窃取/身份隔离/Release/重触发/复位。五个明确 `INJECT_` 旧状态专项用于多匹配和同龄等转移边界，独立注明不声称自然事件可达；正常随机链在注入后复位。

软件单测不代替实际 RTL 变异。计划中的两项行为变异将生成隔离副本：交换身份/IDLE 优先级、反转低槽 tie-break；必须真实编译和仿真后由独立 checker 指定拒收。

## 执行与审核

先 prepare 绑定源码、参考、向量、TB、Python/Icarus/VVP 及实际依赖静态 SHA、完整命令、次数与预算；同版不可变快照分别送审核员/预审员。按 N32 固定自检授权，计划核对通过后各步骤一次执行；单工具不超过300秒，runner全流程不超过900秒，包括后验和收尾。输出独占、私有进程树、失败立即停止并保留历史；不自动重试、换工具或加限。

PLAN 和 RESULT 使用不同 Review-Key。计划通过不冒充实际结果，结果变化必须升版。原声数学、旧专项、T052/T060 capture、Gowin、设备操作均不属于 A 的执行。

R02/B-001 最小返修：`plan.capsule_files` 绑定实际编译源、TB、向量、checker/reference 及 runner/helper 的私有副本；原路径只作 provenance。前后身份核对、封存和实际命令均指 capsule，拒额外文件和 shadow import。新增单个软件反例在临时 live 副本改动并恢复原 allocator/checker/helper，证明实际参数仍只读冻结副本；不重跑已签 15/7 软件组，也不把此软件检查写成 RTL 结果。

R03/B-002/B-003 后继：child cwd 在计划、verify 和 launcher 三处唯一固定为 capsule。单个软件 guard 在临时 live 的 worker/reference/vectors/helper 被破坏期间，由全新 `-I/-S/-B` Python 沿固定 SHA bootstrap 进入同一冻结 worker 的 `import-verify` 分支，实际加载六模块并记录、核对各自 `__file__` 和 SHA。该分支不进入 execute、不调用 HDL、也不创建 actual receipt；旧静态 guard 证据只保留为历史，不扩大成实际加载链证明。

启动时从审核过的 capsule 读取 `a_launch.py` 原字节，外部核 SHA 后 compile/exec。launcher 仅用标准库核 plan/纯标准库 bootstrap 的固定 SHA 和完整 capsule；随后载入 capsule 中原字节 supervisor。子进程按 `plan.launch.argv_prefix + [精确 plan SHA]` 调用 bootstrap，bootstrap 在同进程进入冻结 worker。parent budget 从 launcher 首次验证之前计起，整个子树仍只有 900 秒总上限；每个实际 HDL 工具上限 300 秒。父进程记录真实 child PID/退出码/日志/收据身份及 completion，失败不重试。父级输出是独立全新目录，不与实际证据目录嵌套。所有路径、SHA、命令在 PLAN 中冻结；最终 RESULT 另附这次实际父级观察，不沿用 PLAN 的 NOT_RUN。

## 并行所有权

主对话2及子智能体仅写 A 的 allocator 与本软件目录；主对话4写 B 专有 wrapper/TB，主对话3写 C 压力软件和 C 专有 TB。B 实际验证等待 A 同版通过，C 等 B 通过。共享看板与当前状态由 M2 维护。阶段成果最终统一交 M2 复核。

## 编译崩溃后的新环境诊断

原plan10实际首步0xC0000005、后17步未开始，Q-0005仅认可失败证据一致，根因仍UNKNOWN。用户随后明确要求自行诊断、修复并恢复分工；据此新增一次独立compile-only诊断，不复用已尝试输出，不重跑原清单。

静态发现旧runner未固定PATH/YOSYSHQ_ROOT，依赖清单漏suite/lib下DLL。新计划显式绑定suite/bin、suite/lib、Windows系统路径和YOSYSHQ_ROOT，并补lib DLL及environment.bat原字节SHA；只实现必要loader设置，不执行会更新gdk缓存的environment.bat，不安装或换工具。这是待实际验证的环境修复假设，不预宣称唯一根因。

`a_compile_diagnostic.py`独立config只允许原N4三源精确字节的一次编译，单步90秒、总300秒，无VVP/lower/version/Gowin。新配置及源码固定SHA、全新输出和私有Job，失败即停；执行前同版双审。诊断成功也只证明编译，不算A功能PASS，完整A后继仍需另行同版计划与实际结果。

诊断R02另冻结`diagnostic_launch.json`，绑定实际Python身份、隔离参数、capsule cwd、script/config/plan原字节SHA和一次命令。`a_diagnostic_launch.py`父进程从首次验证计时，以原字节supervisor私有Job对整个worker施加300秒硬watchdog，并保存实际PID/退出/双流/收据。worker同一raw验身份并解析config/plan，长循环检查预算，compile前及后验精确核suite/bin和lib的DLL集合；新增或漏绑DLL都拒收。此后继只修启动/预算/闭包，不扩大诊断范围。

诊断R03补齐父实际cwd/sys.orig_argv/隔离及UTF-8 flags的fail-before-worker准入，并将真实parent PID/argv/flags/Python身份写入独占entry且纳入父观察完成链。父helper先拒未列pyc/额外文件，再从同一次验SHA的raw加载，包括其嵌套显式文件导入；不再验哈希后重新从路径读代码。`a_qualify_diagnostic.py`把实际受测源码/测试/helpers/generator/Python及argv/cwd冻结，20项新诊断软件测试只从私有副本执行，保存真实父监督退出链及前后源SHA；delivery必须机械核归档字节等于受测字节。旧未绑定测试日志保留，不回填或冒充新资格。

诊断R04仅处理Q-0012的B-009至B-011：Python冻结身份进入父监督source admission，并在读取executable_before、实际worker调用前和后验均拒漂移；新增初次parent核验后稳定漂移反例，worker调用必须为0。封存验证器先验同一raw身份再执行；资格证据及派生patch必须绑定验证缓存，不允许验证旧证据后归档新字节。原R03实物一致但代码仍有上述缺口，按原字节保留；本轮不改allocator/参考/TB和声音算法，不重复旧15/7组。新资格仅运行绑定私有副本中的诊断及封存关联软件测试，不冒充真实编译或A功能通过。
