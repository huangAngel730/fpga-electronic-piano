# task-day E1：双滑块 Pro 接入静态后继

本包只补接入来源/未知项和最小可逆差异。实际等级 **L0**，正式接入 **PENDING_PRO_SOURCE_OR_PRODUCERS**，board_release_allowed=false。未复制旧RTL做相同自测，旧487/4及闪光FAIL保持。

先读INTEGRATION_DIFF.md（逐项事实/来源/差异），再读CDC_PATHS.md（七组及64/98bit）、WIRING_PROPOSAL.md（受控最小接线/停止点）。INPUT_IDENTITIES.json、READ_ONLY_REFERENCES.json与FINAL_SOURCE_INDEX.md给原路径/完整SHA。42件本体在本地INPUT_ORIGINALS冻结；按总控收尾新指令，**旧已签案例/旧包及这些输入副本不入新zip或发布清单**，仅引用原Git/文件位置，保留本地原件供只读核查。每轮原始结果/封包落独占RUN_nn/products，失败不覆盖；成功后根RESULT/ANCHORS/READ_ONLY_REFERENCES/FINAL_SOURCE_INDEX/PACKAGE_STATUS只是同字节本地入口别名。解压包请读RUN_nn/products/实际报告及MANIFEST。来源/锚点与命令双流/退出/前后SHA见该RUN。FINAL_RECEIPT和当前RUN seal.*是最终外部回执，封包自己的SHA不写进自身。

有意义的新发现：当前board壳50MHz/双输出PLL与M2所引封存40MHz/三输出PLL不同；旧输出目录本体缺，只能读封存副本。新候选u_events与旧u_event_bridge层级不同。旧64/98bit payload文本只有setup定向报告，7组hold属于同步器二级。mode/score和frame epoch正式来源未选，TB真实+120帧只属于测试。mode载荷固定1可能优化，不能机械填一条新网表数据路径。

本轮功能正/负例、RTL采集、ModelSim/Icarus/Gowin/PnR/STA/设备均 **NOT_RUN**；旧L2仅只读复用，不计新测试。一次新软件组只核字节、原文行锚、声明位宽、来源边界、旧包身份及新封包CRC/SHA，不能升级为新RTL或Pro通过。静态脚本不调用编译器或EDA。预算最多2轮、每组90s，实际消费由RUN_*/CONSUMED.json及FINAL_RECEIPT.json唯一决定，成功即停。

运行命令（本任务runner成功后会拒绝重复运行）：

```powershell
& 'C:/Users/songdongkuan/miniconda3/python.exe' -B -X utf8 code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017/run_static.py
```

新输出独占docs/test的pro_integrate_successor_20261017；没有需要写的RTL/TB，故不创建空目录。未改正式top/PLL/pkg/CST/SDC、M1模型、旧pro_parallel/formal_geometry或共享状态。未提交/未推送/Git写入/门禁/编号0，由夜间任务1统一发布。按最新通信方式，本窗口不再发送工具回执，总控只读领取RESULT/RECEIPT/ZIP；PUBLISH_FILE_LIST.json给出新增可发布文件，明确排除本地INPUT_ORIGINALS，勿整目录误暂存旧原件副本。M2最终受控接入与准入、M3后续同版实屏责任见提案。真人M2待用户转发，尚未送达，本地文件存在不等于总控已处理或真人签收。
