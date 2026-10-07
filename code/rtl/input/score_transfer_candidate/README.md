# score_transfer_candidate（仅T057独立接收候选）

来源：任务合同`code/docs/M3_曲谱有线传输任务单_安卓BLE后续_2026-10-07.md`。
原公共uart_rx/uart_tx只读例化，运行收据source_manifest锁定本次实际源码SHA。
完整协议见`code/docs/hardware/score_transfer_v1/PROTOCOL.md`。

接口：clk=40MHz；rst_n在clk域同步低有效，不内置PLL或复位同步；
uart_rx_i异步引脚经原UART双FF，uart_tx_o为独立115200 8N1输出。
未分配物理引脚，不占MIDI/STAT，不改top/pkg/CST/SDC。

公开读端rd_req + rd_index[8:0]，下一拍rd_valid和rd_event[63:0]；
rd_event低32位tick，接下来8位type/channel/note/velocity，小端字节映射。
committed_valid/count/score_id及commit_pulse绑定原子发布；last_error为最近处理的错误码。
COMMIT同拍读请求得到旧银行；消费者要锁定发布身份，不允许跨新提交拼接旧/新曲谱。
复位清所有有效标志，不清8192字节双银行数据RAM；无有效标志时不得读陈旧内容。
容量512、DATA<=128，逐字节写入/COMMIT CRC与事件验证；只在完整校验后切银行。

当前8路读口拼64位和帧缓存/响应构造只验证行为，尚未做Gowin资源/时序/BSRAM推断。
M2正式接入时如需改变存储布局/端口/延迟，须另冻结合同并回归；不可直接假定资源占用。
没有自动播放、source_id或视觉映射；公共演奏64位事件不能直接等同本64位文件记录。

一键专项：`python -B -X utf8 code/scripts/run_m3_score_transfer_acceptance.py --repo-gate --publish`。
MUTANT_OFFSET / MUTANT_SKIP_SCORE_CRC仅为验收编译变异，不得用于候选综合或上板。
没有Gowin、PnR或下载；L2/L3不可外推为实际UART电气/无线/演奏通过。
