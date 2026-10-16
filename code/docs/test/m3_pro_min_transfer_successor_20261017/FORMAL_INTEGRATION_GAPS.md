# E3正式接入差异与下一责任人

隔离后继score_transfer_e3_successor沿原候选接口：clk/rst_n、uart_rx_i/uart_tx_o、rd_req/rd_index[8:0]→rd_valid/rd_event[63:0]、committed_valid/count[9:0]/score_id[31:0]/commit_pulse/last_error[7:0]。仅新目录提供模块，正式top/pkg/PLL/公共协议/CST/SDC均未编辑。固定40MHz同步低有效复位、115200 8N1；没有新增时钟或跨域路径。

NACK8修复按冻结v1书面合同第26行，在EXEC的COMMIT错误4/5/6/8清会话及缓存，下一拍响应active=0；VERIFY9/10清会话的既有实现保留。错误版本、帧CRC等前置解析策略不在此次修复范围，不宣称所有无效协议版本同样处理。旧RTL及其旧分歧永久保留，不能以新候选替写旧签收结论。

一份真实文件仅证明Type0/单轨/默认tempo的44条记录存储运输，文件时长8秒是事件时间范围，并未播放8秒音频。无自动播放、PCM、音色、BLE、多设备或编辑器结论。新候选仍是行为RAM，未签BSRAM推断/资源/40MHz物理时序；既有BRAM后继文件未改，也未将本修复默认为已移植到BRAM版。

- M2：复核新RTL最小差异、失败COMMIT/重放缓存生命周期及输入/工具/捕获SHA；确定正式采用原行为版还是已签BRAM后继，并迁入获准正式工程，核UART球位/Bank/电平与实际时钟复位、完整STA、精确Pro码流及下载准入。生产侧读银行生命周期仍需约定，存储READ不等于播放消费者已安全接入。
- M3现场：得到一份精确获准Pro码流和安全有线链路后，用封包同一300字节.mid及352字节records做实体上传、ACK和44条完整READ逐字节核对；保设备/命令/实发实收/时间/首失败，不迁用旧PG484或下载次数。
- 当前没有实物/仪器、正式Pro源码/ROM/top/trace/码流与UART准入原件，以上环节PENDING。SESSION_TIMEOUT=50ms仅隔离参数测试，生产默认5s未在本轮重复验；FRAME_TIMEOUT=20ms按原参数实际执行。

整体E3=PARTIAL；离线新后继限定L2及软件L1完成。board_release_allowed=false。由夜间总控统一Git发布及M2/M1真人交接，子窗口未提交/推送。真人回执待用户转发，尚未送达。
