# 主对话3 → 白天总控：T052 chat8 现机补件

状态：**本轮授权的软件材料完成；执行准入仍 PARTIAL / WRITE_PROBE_SCOPE_NOT_GRANTED。未提交、未推送。**本窗口无fetch/merge/add/commit/push，共同树Git写及门禁由总控集中处理；不启用审核员/预审员。

基线HEAD/origin：`57ad4aeb8ef0a1dad3fcfaf68f83aad6d08b0af3`。仅新增software/doc两个`chat8_readiness_20261016/`子目录；Windows下文档父目录实际保留Git既有大写`LONG_WINDOW_PREPARATION_20261015`，与分工单小写路径是同一物理目录，不创建第二套大小写目录。

## 实际结果与原件

最终`R02/RUN_RECEIPT.json`：外层exit0 / `AUTHORIZED_PREFLIGHT_SOFTWARE_PASS_EXECUTION_PARTIAL`，子收集器exit3 / `SOURCE_ENV_RESOURCE_MATERIAL_COMPLETE_WRITE_PROBE_SCOPE_NOT_GRANTED`。外层0只指本轮已授权软件工作正确保留缺口，不能解释成执行许可或真实T052 PASS。

SHA-256：

```text
R02/RUN_RECEIPT.json
63a9251d6eb741354d40053dcdca2324c1f8f78a8df411633c80500591883591
R02/evidence/READINESS_RECEIPT.json
4783ef64be23a24e4a018a9ab07822af146019bdb3c134a1131f5c79e84b653e
R02/evidence/UNAPPROVED_UNIQUE_COMBINATION.json
8036d52758ab147fc51c0de0c1a341d3c7b8cf617b945f83cce26fb18a6a4164
```

最终采样：2026-10-16 11:37:10–11:37:13（Asia/Shanghai，原件UTC）。22项当前源/原提案/已签R02包身份，7项完整固定输入，325项现机EXE/静态DLL/ivl/Python-pyd等前后SHA全同。当前父目录源与M2核过的R02 ZIP manifest逐项同字节；新预检源码另列SHA，不用旧R01源快照代当前TB。原锁闭提案完整SHA仍`2a05f0fdff73b4f65c8c7898535b12369055fccdb36f21e1fe0eea756d8611f9`，物理原件保持`approved=false`。

两次真实只读版本查询、两次真实Python Job探针均进原`win_job.py`的挂起入Job后恢复路径，原双流/启动/Job清空/退出记录齐全。当前Icarus及VVP版本均`14.0 (devel) (s20260301-474-g5591c2dde-dirty)`；两个EXE的actual argv均只有`-V`，不是HDL编译或vvp运行。实际动态加载DLL仍UNKNOWN，325项是静态superset，不称动态闭包。

明确PATH/IVERILOG_ROOT及完整环境SHA在精确组合和原报告中。最终显式环境SHA：`4eec9e0a3d420eaf7c3ec9c6dbb7c38ed9a0f2b0ee10dedb7bb50da69366d9a4`。正常Python子进程回报的全摘要和值全部核同；子进程故意修改ROOT后即使退出0仍被独立比较拒收，诊断`JOB_EXPLICIT_ENVIRONMENT_MISMATCH:IVERILOG_ROOT`。没有在失败时忽略某个键或改摘要判据。

## 首失败、定位与必要增量

`R01`原外层exit1/子exit1、源码ZIP和原流保留：正常Python探针PATH/ROOT一致，却报`JOB_FULL_ENVIRONMENT_HASH_MISMATCH`。`ENV_DIAGNOSIS_R01`只新增1个Python Job诊断，exit0，逐变量摘要确定唯一差异是原本为空的COLORTERM从native子环境消失。修法仅在新预检目录：构造显式环境时列出并删除空值键，再设PATH/ROOT，完整环境摘要仍严格相等。未来实际启动必须同样构造，不能只设置PATH/ROOT。

最终`R02`执行不同SHA增量后成功，不是无变更盲重试。累计本轮只读metadata查询4次（首失败2＋最终2）、Python Job探针4次（首失败1＋定位1＋最终正负2）；不重跑已签29/34。失败原件不回填成功。

## 资源及唯一准入缺口

最终E盘采样可用从70,592,110,592到70,591,508,480字节，均大于2GiB。只读证明下列唯一名字在前后采样均不存在、父目录存在、绝对ASCII路径，**没有**创建实际输出/额度、没有消费：

```text
E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/output/m3_t052_long_actual_chat8_20261016_01
E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/output/m3_t052_long_allowance_chat8_20261016_01
```

空间未预留、名字未上锁。额度目录不存在不能说已有额度可用：M2批准唯一组合时还须明确允许准备这个固定空额度目录；启动前仍执行原检查及独占持久消费。

**WRITE_PROBE_SCOPE_NOT_GRANTED：**旧`bounded_runner.py:427`接收refusal参数，`:437`强制实际拒收收据位于code/output，`:448`独占写入。总控明确本轮不新增code/output写集，因此本窗口没有实际验证该路径可写，不以docs的JSON写成功替代。

最小待批准探针：仅允许新增`code/output/m3_t052_chat8_refusal_probe_20261016_01/`，Python独占写/读/哈希并保留一份明确合成的拒收日志；0execute、0HDL、0checker、0实际额度消费，不创建实际长窗输出或额度目录。当前脚本没有这项写入开关。此项请总控集中交M2决定，不再重复询问或自行跨界。

## 命令、等级与接手责任

最终实际命令（已有输出不得覆盖）：

```powershell
& 'C:\Users\songdongkuan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -X utf8 code/software/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015/chat8_readiness_20261016/run_readiness.py --prepared code/output/m3_t052_long_preparation_20261015_03/prepared --output code/docs/test/t052_publication_acceptance_20261012/long_window_preparation_20261015/chat8_readiness_20261016/R02
```

原命令、cwd、原stdout/stderr/每步退出及源码快照在R01/R02/诊断目录。`git diff --check`退出0；此命令不覆盖未跟踪文件，新增源码另做Python AST语法检查并封存结果。没有运行全仓九门禁，交总控最终精确树统一处理。

实际等级仅L0静态＋Python软件正负例。新T052 compile/run/实际capture checker各0、ModelSim/Gowin/设备0、旧128沿/T060与R05额度消费0。旧4207 UNKNOWN、完整T052 PARTIAL、board_release_allowed=false不变。未验：真实工具编译/捕获吞吐和动态依赖、两个RTL行为反例、PCM数学/声音、138K实物。

请总控将本件新源码/封存包/未批准精确组合和这项未验交M2，统一Git发布及准入沟通。当前不执行真实compile/run/check，不能直接翻旧proposal批准位。给真人M2仍待用户转发，尚未送达。
