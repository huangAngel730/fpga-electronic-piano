# d53fcd4 余97项限定只读复核

前次未决97项现已逐项分类，原`CONTENT_REUSE_AUDIT.json`保持原结论。结论为可保存的历史原件、来源快照和L0说明；没有发现本范围新增生产功能实现。**不能把它们统称为新增功能通过，M1第18批原始体仍缺，真实Pro、公开采集和板级准入继续PENDING。**

此次只读Git/ZIP/JSON/SHA，不运行被审脚本、测试、编译、EDA或设备。没有修改被审源、共享文档或C4，也没有提交/发布。`D53_REMAINING97_CLASSIFICATION.json`是全97逐项分类；各原件仍按旧失败、消费、时点和验证等级保存。

## 有据结论

- 7件HDL/工程/CST快照全部与既有真实Git原路径同字节。E1 current shell是50MHz双输出旧视觉壳，原工程是60K目标；Pro pins是参考候选，不能当实际Pro板修订/Bank/电气验收。B1 top和两个旧音频TB保持原历史用途。具体源路径/SHA/版本见`SOURCE_BINDINGS.json`、`FOLLOWUP_BINDINGS.json`，没有因名称含Pro而签新Pro。
- E1另3份旧文档快照（旧闭包、RTL规范、任务板）与`414e1a9`精确原路径同字节。旧任务板只是当时快照，不覆盖R07。
- 3个此前未决封包本体命中原容器SHA；先前载荷索引未含外层本体，现单列，不把重封包当新实现。
- 历史Git索引绑定实际核`8b9d11e`98/98、`ad2de21`两表各52/52。7个ZIP或别名的大小/SHA与各自历史收据一致。归档容器CRC正常，可识别manifest清单项均核同，未发现大小/SHA冲突。
- 4组历史门禁输入表全量JSON解析、前后逐对象一致：13225、13127、13127、13242记录。两份D门禁正文可精确还原旧CRLF SHA `a3d27dee...b81303b`。旧9/9只绑定`ad2/8b9/414`，不能复用为新树门禁。
- 3个Python辅助源码只用于旧Git只读核验、清单、封包和回件。仅静读，没有调用。

## 尚缺的原始来源与过期定义

M1第18批相关9份新说明和3份provenance说明保持L0。旧C原JSON/JSONL可核为496记录、19 FRAME、76 ACCEPT、75 PUBLISH、71 CONSUME、5 CANCEL；但M1第18批MANIFEST（2795B/SHA `07469e30eddb8e31f17ca21a1afe6471fef48515fab4b4c7f3eee27f7f071c34`）、FIELD_MAP（410082B/SHA `83cb365313788cec24594fcc2d8446d58a313c486fd1c43565ca959714332c6e`）、mapped receipt、INTAKE_STATUS、M1回复、mapper等原始体没有在本机已核原件中定位。不能把M3“16/16核同”的历史自述冒称本轮M2已核，也不能在缺manifest时自行枚举它声称的17个完整文件。需要这份目录或同SHA完整ZIP，旧7.38MB Pro算法包不能替代。精确已声明身份见子核验结果及97项原正文。

D/day_boundary_review旧2份说明针对旧D3 `3217f97...`和未执行R02提案，其中D834时q+833可取消的建议不符合当前M2 R05/R07严格`t-F<833`，只能归档，不能恢复旧提案、旧轮次或改变截止规则。

旧发布清单明确排除INPUT_ORIGINALS、新M1协调底稿标记NOT_FOR_PUBLICATION的时点说明仍保留。d53是后补归档；不能依据旧清单声称这些文件在旧提交时已发布，不能把旧通信回执当真人已送达或本轮运行授权。

## 实际阅读边界

JSON都完整解析；大输入表做全量前后比较，阅读身份/状态/版本字段，不逐一重建旧机器全部13k输入。封包读全部成员并核哈希/可识别清单，不重审已签算法。文本说明及3个helper做静读；1033行旧任务板只核身份/历史时点，不重审全部旧任务。七快照和M1九说明由本窗口只读子智能体辅助，结论由本窗口汇总。没有启用审核员/预审员制度。

本窗口只读绑定辅助曾因旧回执结构差异退出1，修正字段兼容后一次重试exit0；只是自有核验脚本，无被审修改、功能运行或额度消耗。子核验遇到旧目录访问/CIM读取限制后停止相应查询，无绕过、无改写。

## 全97逐项分类

| # | 文件 | 分类 | 阅读边界 |
| ---: | --- | --- | --- |
| 0 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017/HANDOFF_TO_COORDINATOR.md` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 1 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017/INPUT_ORIGINALS/current_board_shell.sv` | `EXACT_HISTORICAL_SOURCE_SNAPSHOT` | Full 132-line UTF-8 body; visual-event shell, local diagnostic time, old 50MHz video reference and existing instantiated blocks. No HDL run. |
| 2 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017/INPUT_ORIGINALS/current_project.gprj` | `EXACT_HISTORICAL_SOURCE_SNAPSHOT` | Full 83-line XML body and enabled file list; Device GW5AT-60B / GW5AT-LV60PG484AC1/I0, old 60K project. No project execution. |
| 3 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017/INPUT_ORIGINALS/m2_old_closure.md` | `EXACT_HISTORICAL_SOURCE_SNAPSHOT` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 4 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017/INPUT_ORIGINALS/pro_cst_candidate.cst` | `EXACT_HISTORICAL_SOURCE_SNAPSHOT` | CST lines 1-85 and last 35; complete byte SHA identity, not electrical/package/Bank certification. |
| 5 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017/INPUT_ORIGINALS/rtl_rules.md` | `EXACT_HISTORICAL_SOURCE_SNAPSHOT` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 6 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017/INPUT_ORIGINALS/task_board.md` | `EXACT_HISTORICAL_SOURCE_SNAPSHOT` | 全文件SHA与414任务板原件逐字节核同；仅读身份和历史时点，不重审1033行旧任务。 |
| 7 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017/PUBLISH_FILE_LIST.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 8 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017/RUN_02/products/PACKAGE_STATUS.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 9 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017/RUN_02/seal.launch.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 10 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017/RUN_02/seal.receipt.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 11 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017/RUN_02/seal.stdout` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 12 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/task2_coordinator/GATE_R01/GATE_RECEIPT.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 13 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/task2_coordinator/GATE_R01/INPUTS_AFTER.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 14 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/task2_coordinator/GATE_R01/INPUTS_BEFORE.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 15 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/task2_coordinator/HANDOFF_FINAL/FINAL_DELIVERY.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 16 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/task2_coordinator/HANDOFF_FINAL/HANDOFF_MANIFEST.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 17 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/task2_coordinator/HANDOFF_FINAL/M3_TASK2_FOUR_EXTENSIONS_HANDOFF_COMPLETE_20261017.zip` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 逐成员解读清单/大小/SHA及CRC；正文载荷复用原限定结论，不重审旧DUT算法。 |
| 18 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/task2_coordinator/HANDOFF_FINAL/README.txt` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 19 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/task2_coordinator/HANDOFF_FINAL/finish_handoff.py` | `ARCHIVED_PACKAGING_HELPER_NOT_RUN` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 20 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/task2_coordinator/HANDOFF_FINAL/给M1_待用户转发.md` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 21 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/task2_coordinator/HANDOFF_FINAL/给M2_待用户转发.md` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 22 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/task2_coordinator/PUBLICATION_AUDIT/INDEX_BINDING.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 23 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/task2_coordinator/PUBLICATION_AUDIT/audit_index.py` | `ARCHIVED_PACKAGING_HELPER_NOT_RUN` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 24 | `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/task2_coordinator/PUBLICATION_STATUS.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 25 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/HANDOFF_FINAL/FINAL_DELIVERY.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 26 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/HANDOFF_FINAL/HANDOFF_MANIFEST.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 27 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/HANDOFF_FINAL/M3_NIGHT_20261017_HANDOFF_COMPLETE.zip` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 逐成员解读清单/大小/SHA及CRC；正文载荷复用原限定结论，不重审旧DUT算法。 |
| 28 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/HANDOFF_FINAL/README.txt` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 29 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/HANDOFF_FINAL/给M1_待用户转发.md` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 30 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/HANDOFF_FINAL/给M2_待用户转发.md` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 31 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/PUBLICATION_AUDIT/INDEX_BINDING.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 32 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/PUBLICATION_AUDIT/INDEX_BINDING_FINAL.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 33 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/PUBLICATION_GATE/GATE_RECEIPT.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 34 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/PUBLICATION_GATE/INPUTS_AFTER.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 35 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/PUBLICATION_GATE/INPUTS_BEFORE.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 36 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/PUBLICATION_GATE_R01/GATE_RECEIPT.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 37 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/PUBLICATION_GATE_R01/INPUTS_AFTER.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 38 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/PUBLICATION_GATE_R01/INPUTS_BEFORE.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 39 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/PUBLICATION_STATUS.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 40 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/finish_handoff.py` | `ARCHIVED_PACKAGING_HELPER_NOT_RUN` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 41 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/d3_repair_proposal_20261017/HANDOFF_FINAL/M3_D3_R05_RECONCILED_HANDOFF_20261017.zip` | `KNOWN_ARCHIVE_BODY` | 逐成员解读清单/大小/SHA及CRC；正文载荷复用原限定结论，不重审旧DUT算法。 |
| 42 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/d3_repair_proposal_20261017/HANDOFF_FINAL/RECEIPT.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 43 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/day_boundary_review_20261017/INPUT_SHA.json` | `D3_SUPERSEDED_PROPOSAL_NOTE` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 44 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/day_boundary_review_20261017/REVIEW.txt` | `D3_SUPERSEDED_PROPOSAL_NOTE` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 45 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017/GATE_R01/GATE_RECEIPT.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 46 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017/GATE_R01/INPUTS_AFTER.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 47 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017/GATE_R01/INPUTS_BEFORE.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 48 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017/GATE_R01/LAUNCH.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 49 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017/HANDOFF_FINAL/HANDOFF_RECEIPT.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 50 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017/HANDOFF_FINAL/M1_FORWARD.md` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 51 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017/HANDOFF_FINAL/M2_FORWARD.md` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 52 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017/HANDOFF_FINAL/M3_PRO_PASSIVE_MONITOR_HANDOFF_20261017.zip` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 逐成员解读清单/大小/SHA及CRC；正文载荷复用原限定结论，不重审旧DUT算法。 |
| 53 | `code/docs/test/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017/PUBLICATION_STATUS.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 54 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/FINAL_AUDIT.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 55 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/FINAL_ENTRY.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 56 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/HANDOFF_TO_TASK1.md` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 57 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/PUBLICATION_FILES.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 58 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/SEAL_EXECUTION_LAUNCH.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 59 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/SEAL_EXECUTION_RECEIPT.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 60 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/coordinator_20261017/HANDOFF_FINAL/HANDOFF_RECEIPT.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 61 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/coordinator_20261017/HANDOFF_FINAL/M3_TASK_DAY_FIVE_WINDOWS_HANDOFF_20261017.zip` | `KNOWN_ARCHIVE_BODY` | 逐成员解读清单/大小/SHA及CRC；正文载荷复用原限定结论，不重审旧DUT算法。 |
| 62 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/day_m1_batch18_20261017/FIELD_DELTA.json` | `M1_BATCH18_L0_UNAUTHENTICATED_SOURCE` | Complete UTF-8 text; JSON fully parsed when applicable. Attached-input identities and claims compared; no mapper/checker execution. |
| 63 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/day_m1_batch18_20261017/INPUT_SHA.json` | `M1_BATCH18_L0_UNAUTHENTICATED_SOURCE` | Complete UTF-8 text; JSON fully parsed when applicable. Attached-input identities and claims compared; no mapper/checker execution. |
| 64 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/day_m1_batch18_20261017/RESULT.txt` | `M1_BATCH18_L0_UNAUTHENTICATED_SOURCE` | Complete UTF-8 text; JSON fully parsed when applicable. Attached-input identities and claims compared; no mapper/checker execution. |
| 65 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/day_m1_batch18_coordinator_20261017/INPUT_SHA.json` | `M1_BATCH18_L0_UNAUTHENTICATED_SOURCE` | Complete UTF-8 text; JSON fully parsed when applicable. Attached-input identities and claims compared; no mapper/checker execution. |
| 66 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/day_m1_batch18_coordinator_20261017/M2_FORWARD.md` | `M1_BATCH18_L0_UNAUTHENTICATED_SOURCE` | Complete UTF-8 text; JSON fully parsed when applicable. Attached-input identities and claims compared; no mapper/checker execution. |
| 67 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/day_m1_batch18_coordinator_20261017/RESULT.md` | `M1_BATCH18_L0_UNAUTHENTICATED_SOURCE` | Complete UTF-8 text; JSON fully parsed when applicable. Attached-input identities and claims compared; no mapper/checker execution. |
| 68 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/day_provenance_20261017/INTAKE_AUDIT.json` | `PROVENANCE_L0_PARTLY_VERIFIABLE` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 69 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/day_provenance_20261017/ORIGINALS_TO_FORWARD.txt` | `PROVENANCE_L0_PARTLY_VERIFIABLE` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 70 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/day_provenance_20261017/RESULT.txt` | `PROVENANCE_L0_PARTLY_VERIFIABLE` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 71 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/COPY_MAP.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 72 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/DELIVERY_MANIFEST.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 73 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/DELIVERY_RECEIPT.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 74 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/FINAL_FILE_LIST.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 75 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/HANDOFF_TO_TASK1.md` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 76 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/INPUT_ORIGINALS/017_HANDOFF_RECEIPT.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 77 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/INPUT_ORIGINALS/018_RECEIPT.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 78 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/INPUT_ORIGINALS/038_electronic_piano_top.sv` | `EXACT_HISTORICAL_SOURCE_SNAPSHOT` | Top source lines 1-90 header/old60K target/electrical/reset/purpose notes; complete byte SHA identity, not a new full functional review. |
| 79 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/INPUT_ORIGINALS/048_tang_mega_138k-pro_pins.cst` | `EXACT_HISTORICAL_SOURCE_SNAPSHOT` | Identical to index4 CST; same limited text reading and complete byte identity. |
| 80 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/INPUT_ORIGINALS/archive_04_M3_PRO_PASSIVE_MONITOR_HANDOFF_20261017.zip` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 逐成员解读清单/大小/SHA及CRC；正文载荷复用原限定结论，不重审旧DUT算法。 |
| 81 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/INPUT_ORIGINALS/archive_05_M3_PRO_PASSIVE_MONITOR_ORIGINALS_20261017.zip` | `KNOWN_ARCHIVE_BODY` | 逐成员解读清单/大小/SHA及CRC；正文载荷复用原限定结论，不重审旧DUT算法。 |
| 82 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/INPUT_ORIGINALS/supplement_02_tb_normal.sv` | `EXACT_HISTORICAL_SOURCE_SNAPSHOT` | Full 84-line TB; old sealed40MHz chain stimulus/private u_core hierarchy/end/timeout. Not eligible as new public observer TB. |
| 83 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/INPUT_ORIGINALS/supplement_03_serial_capture.sv` | `EXACT_HISTORICAL_SOURCE_SNAPSHOT` | Full65-line serial observer; PRE_NBA handshakes, adoption log, BCLK/WS/DIN shift decode. Not a new sidecar/finish/epoch proof. |
| 84 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/LIGHTWEIGHT/EXECUTION.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 85 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/LIGHTWEIGHT/seal.stdout` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 86 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/M3_TASK5_INTAKE_ORIGINALS_20261017.zip` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 逐成员解读清单/大小/SHA及CRC；正文载荷复用原限定结论，不重审旧DUT算法。 |
| 87 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/SEAL.stdout` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全文UTF-8静读，结合版本/SHA/已签报告区分事实与旧请求。 |
| 88 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/SEAL_EXECUTION.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 89 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/SEAL_LAUNCH.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 90 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_serial_successor_20261017/SEAL_01/VERIFICATION.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 91 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_serial_successor_20261017/day_m1_batch18_20261017/INPUT_SHA.json` | `M1_BATCH18_L0_UNAUTHENTICATED_SOURCE` | Complete UTF-8 text; JSON fully parsed when applicable. Attached-input identities and claims compared; no mapper/checker execution. |
| 92 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_serial_successor_20261017/day_m1_batch18_20261017/RESULT.txt` | `M1_BATCH18_L0_UNAUTHENTICATED_SOURCE` | Complete UTF-8 text; JSON fully parsed when applicable. Attached-input identities and claims compared; no mapper/checker execution. |
| 93 | `code/docs/test/m3_pro_fourvoice_trace_20261016/pro_serial_successor_20261017/day_m1_batch18_20261017/SERIAL_FIELD_DELTA.json` | `M1_BATCH18_L0_UNAUTHENTICATED_SOURCE` | Complete UTF-8 text; JSON fully parsed when applicable. Attached-input identities and claims compared; no mapper/checker execution. |
| 94 | `code/docs/test/m3_pro_waveform_successor_20261017/COMMUNICATION_RECEIPT.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 95 | `code/docs/test/m3_pro_waveform_successor_20261017/SEAL_EXECUTION.launch.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
| 96 | `code/docs/test/m3_pro_waveform_successor_20261017/SEAL_EXECUTION.receipt.json` | `HISTORICAL_PUBLICATION_OR_SEAL_METADATA` | 全量JSON解析及身份/状态/版本/引用字段阅读；输入大表逐对象比较前后，不逐一重建旧机器全部输入。 |
