# T057 独立曲谱传输合同 v1

仅新候选；依据 `M3_曲谱有线传输任务单_安卓BLE后续_2026-10-07.md`。
40 MHz 同步低有效复位，115200 8N1，位周期取整为347拍；无硬件流控。
停等：一请求一响应，必须等完整响应再发下一帧。所有多字节整数小端。

帧：`A5 5A | version:u8=1 cmd:u8 session:u16 seq:u16 offset:u16 length:u16 | payload | crc:u16`。
length<=128，CRC仅覆盖version到payload，不含同步字和CRC自身。
唯一CRC算法 CRC-16/CCITT-FALSE：poly=0x1021 init=0xffff refin/refout=false xorout=0；
黄金 `123456789 -> 0x29b1`；同算法用于整份规范曲谱字节。

命令：BEGIN=1 DATA=2 COMMIT=3 ABORT=4 STATUS=5 READ=6 ACK=0x80 NACK=0x81。
BEGIN payload `<IHHHI` = score_id、事件数、总字节数、整曲CRC、sample_hz=48000；
seq=0 offset=0，session非0。事件1..512，总字节=8*事件数。
DATA payload为事件流字节，1..128；seq从1递增，offset必须等于已接收字节数；
支持非8字节对齐分包。COMMIT空payload offset=0，seq为下一个DATA序号。
必须齐套、整曲CRC和每条事件合法才原子切换双缓冲存储银行。
ABORT空payload offset=0，不限制session/seq，取消暂存但保留旧曲谱。
STATUS空payload offset=0；READ空payload，offset为已提交事件索引，session/seq回显。
STATUS/READ不消耗上传DATA序号。两者会替换最后一次成功请求重放缓存，PC上传中不插入查询。

响应回显session/seq/offset，payload为 `<BBBBHIH`：原命令、错误码、已提交有效、
会话有效、已提交数量、已提交score_id、暂存收到字节数；READ成功附8字节事件。
ACK错误码0。NACK：1帧CRC、2版本、3命令、4帧长度/参数长度、5会话、6序号、
7offset、8未齐套、9曲谱CRC、10事件、11容量/元数据、12帧/会话超时、13读索引、14UART停止位。
CRC/事件错误不发布，用户可ABORT或新BEGIN恢复；失败COMMIT使当前会话失效。
重复**最后一次成功请求的全部正文完全相同**则原字节重放ACK，不二次写入或提交。
其他旧包NACK；不依靠CRC相同推断包相同。BEGIN/DATA/COMMIT丢ACK均可有限重试。

帧字节间超时20ms（800000系统拍），上传空闲超时5s（200000000拍）。
帧超时丢弃解析中帧，NACK12；会话超时丢暂存，NACK12且保留旧曲谱。
超长帧立即NACK4并丢弃后续字节直到20ms空闲，再重新寻找同步字；期间不接受嵌入BEGIN。
无可信头部的超时/帧错误响应session/seq可能为解析残值，PC必须验证身份并限时退出。
复位清有效位/会话/重放缓存，存储未初始化内容永不读为有效曲谱。
读端仅返回已提交银行，同步rd_req/rd_index，下一拍rd_valid/rd_event；非法索引rd_valid=0。
COMMIT同拍读请求返回旧银行，随后读请求返回新银行；消费者须以commit脉冲/metadata绑定一份曲谱。

PC ACK默认0.5s、最多重发2次、整次事务总截止30s；NACK立即非零退出，不盲目重发坏包。
保存完整实发/实收字节和收据SHA，上传后STATUS及全部READ逐条核对。
`.mid`导入、自动播放、视觉接入、BLE/App、FPGA球位、综合/PnR、实际UART硬件未属本轮实现。
