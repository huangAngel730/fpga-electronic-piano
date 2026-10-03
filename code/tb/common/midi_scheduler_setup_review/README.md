# M2独立解析器修复复核夹具（2026-10-03）

只做de68038原DUT与3d6430e旧DUT的补充逐拍对照，四配置各256193拍；不修改M3文件，不替代其3329005拍长轨迹，不宣称PnR或板级通过。
参考必须从Git取原3d6430e的midi_event_parser.sv，raw SHA cfd4c33e91ba06a73c89dedb66b8636dc0c1bd1778ae454714325207424c28c4，只将module名改midi_event_parser_frozen。
当前DUT原SHA 834887a990a4866d54669c5f18588a0b799aa4c08ccb27c91a2f9e5609f331c6。四配置覆盖fifo depth1/8/16/3、burst1/8/8/3、rate Hz64000/64000/50000000/1。

TB通过真实字节/valid/error/ready/reset输入对照完整事件、FIFO水位/峰值/溢出/解析错误和调度寄存状态，含1kHz冷却、背压、非法字节和复位；不force内部寄存器。
编译：在新ASCII output目录放冻结参考，iverilog -g2012 -s tb_m2_parser_miter -o <out>/miter.vvp code/rtl/common/audio_defs_pkg.sv code/rtl/input/midi_input/midi_event_parser.sv <out>/old_frozen.sv code/tb/common/midi_scheduler_setup_review/tb_m2_parser_miter.sv，然后vvp <out>/miter.vvp。
既有CAD环境须含lib/bin，失败/超时非零，不重复使用旧capture假称新测试。

已实跑结果：四配置各256193拍PASS，成功事件28637/35793/32857/42002，控制3045/2950/6/9794。
M2另一项从de68038两段未修改的实际组合源码提取选择器，与独立Python线性oracle400384案例及三个可编译行为反例，已实跑，原代码/向量/日志保留忽略output/M3_parser_de68038_review_20261003/independent_selector。
本目录只保存短miter，不新增第二份生产选择实现；完整源码切片和参考SHA在本次evidence。M3原完整miter入口run_midi_scheduler_equivalence.py与附件ModelSim日志仍单独注明原执行者。

实际执行的TB原始CRLF文件仍保留在output；本目录按.gitattributes使用LF，两者仅换行不同，运行raw SHA和Git LF SHA分别列在source_manifest，不能说两者字节相同。
