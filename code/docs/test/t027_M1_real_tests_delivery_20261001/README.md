# M1交付原文（2026-10-01）

来源ZIP SHA1106a1b93feab038ec9aef7c43f9caefc243d4cd5e153b29dcdbb0a25489c18e。本目录保留M1交付说明和changes.json原文（只统一LF）；“所有失败返回非零/任一失败不能通过”不等于M2确认该验证器可靠。实际接收结论以../../T027_真实自检补交_M2复核_2026-10-01.md为准。

M1模型test_t027_timbre.py、TB和振荡器注释已接收；test_t027_rtl.py只保留收到原件于忽略output，不入正式模型测试入口。M2发现正向忽略sim_ok、负向无偏差也返回False被主流程算成功两处判定漏洞，源码缺失/仿真不可用不是负例检测通过。

正式可复跑入口：python -X utf8 code/scripts/run_t027_m1_test_suite.py；保留既有M2更广的run_t027_revised_delivery.py。原ModelSim日志仅收件来源，M2本机实际用Icarus，不冒称复跑ModelSim。
