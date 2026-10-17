# M3 B2 task-day：公开逐沿CSV到串行核验

基线414e1a9d3ee0617c5e8ba72dd4b22c36122c9926；用户task-day当日单SHA4142a701d0f48c3965c0596641be859d85cf7788b2d17d5d3af64f0e1745af75、同行完赛单SHA7235fb23d4584687259d2743aaa4b91a517e2b5bd3dc8867f0e29857f3b14033。总控DAY_PLAN及已核直接userMessage 01a14797-672a-7462-a629-9845497d8ee2授权本轮回传和自身子智能体自审。

| 项目 | 本包实核/执行上限 |
| --- | --- |
| 范围 | 仅software、tb/board、docs/test下m3_pro_fourvoice_trace_20261016/pro_serial_successor_20261017新目录；原C/D、D3、被动监视器、旧封存只读。 |
| 目标 | 新CSV解析/时基与源身份适配，调用已pin的PinDecoder核心；不复制D3，不调用旧R05 analyze或重跑旧组。 |
| 输入缺口 | 新Pro源/ROM/top/真实trace/M1同版黄金缺失；B1冻结字段合同尚未到。监视器29列没有TX实际采样的身份/PCM/clip，需公开sidecar或M2明确映射，不能从result/commit私自推造。 |
| 时间 | T0北京10:04:35，14:04:35前收工；齐套或无可行动增量即停止。 |
| 工具 | 现场核现有Python EXE/DLL/标准库及只读依赖SHA。B2最多6轮，每Python组90秒；无需要不选Icarus。全组新功能3600秒共享，本包不各领3600秒；ModelSim/Gowin/设备0。 |
| 验收 | 新入口L1正/拒收定向自检，原始行号/cycle/epoch/ID不改；缺BCLK/WS/PCM、错SHA/ID/声道/期限拒收。明确真Pro、算法、48k物理/PT8211实物及board全PENDING。 |
| 原件 | 每轮执行前源/输入/依赖SHA、argv/cwd/机器/起止/PID/双流/退出、首失败保留；源码漂移拒签，成功即停。 |
| 收口 | 只读子智能体按需自审新差异；最终一份收据/ZIP回总控，由总控Git/门禁/发布。此窗不碰Git/index/编号/共享状态/正式接口。 |

依赖复用选择：RESUME_R02/consume_capture.py的PinDecoder/quantize/parse_json，旧D3已pin SHA da91462e8421719e09ffab60d7bbe38d4ee05ac1793ea70e1f09c7a69ccda0cb；用None表示启动，(epoch,id)包含合法0。D夹具Decoder的id0哨兵不适用于真实ID回绕。

监视器CSV无finish/END列，完整性必须另绑定成功退出及MONITOR_END原日志；本包不据文件恰好结束签事务已闭合。不兼容D3的REQUEST恰在FRAME、CONSUME下一FRAME和PA等式合同，不伪装同schema。
