# M2需绑定的最小执行输入（仅提案，尚未获准）

**D3纯软件返修与Pro真实链分开准入。** 当前可以完成静态提案；实际后继写入/CLI预算为0，状态 `NO_ACTIONABLE_EXECUTION_PENDING_M2`。缺Pro工程、商业许可或板卡不应阻止获得独立D3定向Python返修许可；它们只阻止真实Pro/硬件结论。

## A. 仅D3定向软件返修，须M2明确绑定

| 项目 | 精确请求／已有身份 |
| --- | --- |
| 原基线 | `c7e0144ac33acfde9b449183933ef7a21aa9325c`；只读 `code/software/m3_pro_fourvoice_trace_20261016/D/ingest/ingest.py`，SHA `3217f97e57daec534306a213c64566fa111e3116f15a15967ca881847c218e07`。原文件不得覆盖。 |
| 后继写集提案 | 建议由M2绑定 `code/software/m3_pro_fourvoice_trace_20261016/D/ingest_deadline_successor_20261017/ingest.py` 及同目录定向runner，证据输出仅 `code/docs/test/m3_pro_fourvoice_trace_20261016/D/ingest_deadline_successor_20261017/ROUND_01/`；没有RTL/TB或模型写入。本窗口未创建上述目录；最终采用任务2提案还是该名称须M2选定，不构成现有授权。 |
| 补丁与独立时基 | 合并 `../patch_proposal/` 的最终补丁文本与 `../boundary_cases/` 的定向输入后取现场SHA。须明确冻结帧日历/首次帧与epoch重启语义、普通记录/CANCEL/END/RESET的截止检查和同cycle顺序；不能依赖实际FRAME到达才产生截止。本窗口不替任务2/4决定新schema或填期望。 |
| 负／正输入 | 负例原件 `code/docs/test/m2_pro_offline_review_20261017/D3_COUNTEREXAMPLE.json`，SHA `4a32745969b0a4fe6b5aa7a4e880e96659ad677c9b22d790ff6ee4ce4eda0ee4`：req8=1677、漏FRAME2510、CANCEL2512/END2513。须生成新独占manifest/五角色输入及大小/SHA，另绑定严格截止前合法取消对照和必要END/RESET边界。静态预期拒收／接受，不是已执行结果。 |
| 原输入格式 | 原入口的 `M3_PRO_INTAKE_V1` 要求source/rom/contract/calendar/trace五角色；纯软件定向组可明确用 `SYNTHETIC_FIXTURE` 占位源/ROM，禁止改称真实Pro。旧 `D/ingest/ROUND_02/positive/manifest.json` SHA `508a684a4d5429f053315a533b5b661b9713b39af103cda221bdbf95a3cbdad6` 仅只读参考，不重跑。 |
| 只读依赖 | `code/software/m3_40mhz_pcm_i2s_latency_20261015/night_20261016/RESUME_R02/consume_capture.py`，SHA `da91462e8421719e09ffab60d7bbe38d4ee05ac1793ea70e1f09c7a69ccda0cb`；原D3第9–11、23–28行固定并import该依赖。新后继须保留来源绑定；本轮未import。 |
| 工具及预算提案 | 仅已在本机使用的Python，启动前现场核EXE/版本及依赖SHA。建议M2明确批准**一次定向软件组≤90秒**、唯一新输出、首失败即停，若需第二组另批；精确CLI/argv、cwd、manifest SHA及预期拒收码由M2绑定。此建议不是已发额度；本轮仍为0，不继承旧D3或上午审计轮数。 |
| 不在该软件组内 | ModelSim/Icarus/Gowin/完整链/STA/设备/Git写入均0；P7执行器关闭边界不解除，不设置强开变量。成功最多签实际L1增量，不签原D3全量或Pro真链。 |

原实现风险位置：FRAME第109–124行才登记due，CANCEL第164–168行只核due为空，END第130–132行只核终态；RESET第96–105行只对未消费/取消项做保护。需独立截止检查先于可能抹去在途状态的处理。具体修法/边界由任务2/4给出，M2仅复核该增量，不重跑其余已签组。

## B. 只有真实Pro链/实物阶段才需要

- M2同版完整source list/top/ROM字节和SHA、FPG676目标/IP/公开端口映射、真实统一cycle/epoch/ID/lane/效果/PCM/串行trace及新有效执行许可；M1同源黄金适配。七处任务指定目录在本工作树仍不存在，见DELTA_IDENTITIES。M2活单第17行报告其未跟踪候选，应交可核原件，不能把其描述认作本机到件。
- 商业许可与完整PnR/Setup/Hold/Recovery/Removal/CDC、同版.fs/恢复SHA及精确单次SRAM许可，均无本轮新增事实；旧预计10月19/20不等于已到位。
- B0实物全料号/4072与4071修订/Bank供电/MIDI电平共地/复位及PA_EN/PT8211原件仍UNKNOWN。沿用原B0缺口，不重测、不复核旧PDF/CST或重复复制7个封包。

上述B项缺失**不成为A项纯软件定向返修的前置门槛**；M2可先绑定A项，Pro同版与实物另按既定顺序推进。真人M2许可仍待用户转发/明确绑定，尚未取得。
