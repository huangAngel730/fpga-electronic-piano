# 夜间任务2：C/C2 独立日历，2026-10-17

本轮由夜间任务1派发，用户在该总控对话直接授权四窗口调度与子智能体自审；已读取原文。基线ca4859abc28e3a5f7fdd0250e9f2cd43de39a8c0；总时间盒00:21–05:21北京时间，本窗口Python实跑最多2000秒，仍受C最多6轮、每轮90秒约束，首过即停。总控掌握C/D合计4500秒；本窗口不共享写消费文件。

只写code/software、code/tb/board、code/docs/test三处m3_pro_fourvoice_trace_20261016/C/。本包仅Python独立夹具，无需新增RTL或Icarus。ModelSim/Gowin/综合/PnR/STA/码流/硬件执行0；不碰Git index、门禁、编号和共享状态。旧A/C只读且不重跑，本轮不消费旧日志作新事实。

目标：四音高各独奏及同帧四音、逐音NoteOff、reset epoch、四lane推进、接受后取消、背压valid/id/data保持、返回/发布/消费生命周期及定向拒收。Pro源码/ROM/top/trace与M1已发布黄金缺失，仅签SYNTHETIC_FIXTURE_NOT_PRO_DUT。slot最低空闲、NoteOff立即释放、固定lane=slot、inactive也推进均为夹具假设，不是正式分配规则。无PCM计算。

完成条件：冻结input/calendar/字段合同和SHA；独立手算锚；Python正例和所有目标坏轨迹实际拒收、拒收码及首差异符合预设；原始argv/cwd/机器/版本/EXE/依赖/源码前后SHA/双流/退出/耗时与唯一轮收据齐套。首失败保留后静态定位，仅修本包新缺陷，在剩余轮内定向复测；工具/依赖/正式接口阻断则停并给缺件。

完成后只发总控一份最终回执。缺真实Pro时不转工具跑DUT；交冻结输入给M1、身份给D只读，真实映射留M2。无必要增量即提前结束。board_release_allowed=false。
