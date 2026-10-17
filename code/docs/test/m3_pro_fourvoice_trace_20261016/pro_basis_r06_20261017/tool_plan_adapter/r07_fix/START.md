# R6-4 消费端安全返修

夜间任务2，2026-10-17，当前HEAD 40d78131e8ed50643dd169816f7bfc7149a8ced9；沿用当晚18:55–22:55时间盒。依据总控新分派、M2_M3_R06准备包限定复核与源清单决定及reviews/source_tool，只新增本包software/docs的r07_fix候选；旧生产源、RUN_01七类及原ZIP只读，R7-A已封存原件不改。无Git写入。

先核原RESULT、RUN_01/GROUP_RECEIPT、coordinator_20261017/PACKAGE_STATUS、R07 dependency_audit及M2本次复核：只见初组一组、三个固定worker；本包根无RUN_02/修复消费。共享既有修复组剩一次，按本次明确缺陷仅消费一次≤60秒，先冻结新源码/输入/工具/输出/case。不得重跑旧七类，首失败全部保留，修复组无再次修复额度。无实物条件，HDL/EDA/设备0。

范围：消费时用独立pinned spec重建规范化计划，全部安全字段一致才收；重算plan SHA不产生权限。Popen紧前重核同一绑定、固定worker/Python/inputs/helpers/cwd/output/marker/timeout与独占输出。真实工具执行关闭。原Windows Job的孙树/超时/溢出/异常清退证明不扩展、不代签，不作为真实工具执行器。

另在R7-A独占目录新增C5静态绑定：只读M2的71源9ROM闭包及决定，追加原R6-2 driver和既有A observer/TB；不改原A结果/源码/ZIP，不消费A任何组，不运行HDL。
