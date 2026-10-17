# M2-R6-1 公共采样合同候选

基线42d28c4；来源ZIP931b7d2b…；仅源端静态合同与新软件校验，真实公开端口、TX旁带、M1语义、Pro身份/PLL/物理/板测尚缺，整个R6-1保持PARTIAL。CAPTURE_CONTRACT、61字段schema、SOURCE_BINDINGS和ROUTING_PLAN供M1/M3实现；FRAME_PLAN_RULES只给独立时钟/复位推导，不是已运行RTL结果。

采样固定POSEDGE_PRE_NBA。保留FRAME预算起点F、请求首valid和真实握手A；原严格t-F<833预算不放宽，并同时早于独立下一FRAME。t-A独立报告。TX取该沿NBA前pending/held元组，当前源码没有ID/clip旁带。raw cancel每FRAME都有，不能无条件变成合法交易取消。D3只作为明确标注的帧预算诊断视图，REQUEST不是实际握手，不能改写真实时间；原25CLI不重跑。

独立FRAME规则从reset零态和S=659706977推导第k边界ceil(128*k*2^32/S)，首有效沿序号834/1667/2500/3334…；来源是冻结输入/复位/clock计划，不能用实际FRAME行反推。无计划或未知相位PENDING；空账本/合法取消不提前结束覆盖。真实finish须计划、尾段、退出码及唯一结束标记齐套。

官_主开发2由用户授权为只读复核协作窗口，但实际跨对话消息因平台approval policy=never被拒，未送达/未接单/未复核；未换工具绕过。正式审核员/预审员制度未启用。M2集成窗口继续已授权独立工作，最终签收责任不转移。

本轮实际软件结果：初组1正7负/3.397714秒/exit0；之后自审发现字符串位宽与可移动消费标记缺口，保留BEFORE/初组后，仅一次≤60秒修复增量1接受7预期拒收/3.461287秒/exit0。修后已知宽度字符串限制maxLength，保留X/null，禁止bool冒充整数；初组入口使用固定任务账本，换两个父目录均exit2且无新输出，旧marker不变。原八项未重跑，不称最终版十六项全量。级别仅L1软件合同，原件ZIP和SOFTWARE_EXECUTION_RECEIPT给出实际源/输入/工具身份及双流；外部官_主开发2仍未送达/未复核。
