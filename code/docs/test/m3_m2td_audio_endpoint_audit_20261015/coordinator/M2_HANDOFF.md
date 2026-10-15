# 发给 M2：40 MHz 音频端点准备回执

状态：**待用户转发，尚未送达 M2 真人**。未提交／未推送；完整任务 PARTIAL／待原件与许可，软件成果 L0/L1。

M2，M3 已按你交付的《M3_并行接管M2_40MHz音频STA端点准备_2026-10-15.md》实际开工，由用户指定的主对话2、4并行完成软件验收器与真实报告端点／STA提案，总控已整合核对。实际工作区为 `E:\FPGA\GAOYUNFPGA\team\fpga-electronic-piano`，任务单使用实际 fetch 后的 `e2200b2571afe3c38807a2d8ee2e4264c5881fd8`。只新增两个授权目录，未联系负责 T052／R04 的主对话3、5，未启审核员／预审员制度。

入口：`code/docs/test/m3_m2td_audio_endpoint_audit_20261015/coordinator/README.md`。封包和逐文件SHA清单位于同目录的 `delivery_R01/`；请转交文件本体及 `SEAL_RECEIPT.json`，不只转SHA。软件源位于 `code/software/m3_m2td_audio_endpoint_audit_20261015/`。具体文件、完整命令、退出码、原始双流、源／依赖／输入SHA、失败历史和验证边界均在包内收据。

实际结果：清单13项自检通过；验收器32项单测通过，合成完整正例exit0，七类坏报告均按指定诊断exit1；总控将5对真实端点逐对接入验收器，4对按MISSING_SETUP、1对按MISSING_HOLD拒收，联接入口exit0。10条提案命令的get_regs→get_pins类型与[]字面转义和验收器一致。源与输入前后SHA稳定，只有软件／静态L0/L1，不是新STA通过。

原物理ZIP SHA `17e71ebd5b54743fd0214af5fbfdfd1a4cca4eddbcedab56f7b3df7b3ca521ff` 与原报告SHA核同；原最坏路径L5结论不被本次缺项观察推翻。但ZIP不含同次综合网表，本机指定output也不存在；因此base_s1/base_s2物理pair及voice→mix、PCM→I2S精确目标仍UNKNOWN，不能用源码名或拼接旧路径代替。两条pitch→ROM、phase→ROM、延迟RAM地址及事件入口的实际节点／LOC／原文字节片段已交付，均没有该同一pair的双分析齐套证明。

请你接手三项决定：①补同次 `.vg`／实现数据库及SHA并确认最终真实端点；②核提案query集合／转义／时钟关联，明确一次真实定向STA的工具／机器／命令／预算／新输出目录；③确认发布门禁写入范围和串行发布安排。当前严格写集只有两新目录，原check_repo间接入口会写code/output，且有其他窗口并发T052修改，本轮没有运行门禁或擅自提交推送。用户补充工具路径为 `E:\FPGA\GAOYUNFPGA\138K\tools`，尚未启动或核验该工具。

本轮未改SDC/CST/LOC、旧报告／checker、R04、正式RTL、公共接口或共享编号／状态表，未Gowin／ModelSim／PnR／STA／下载。`board_release_allowed=false`保持；真实R04／同版物理最终签收／实物仍由原责任人按精确许可推进。请收到实际回执后再登记开工与限定成果，不将此包记作指定端点L5或整机通过。
