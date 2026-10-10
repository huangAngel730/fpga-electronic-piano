# 曲谱同步 RAM 独立候选

范围为用户送达的 CallBack2 RAM 五新增路径任务单；没有新任务编号。
原 score_transfer_candidate、T057/T059 软件、原 capture/失败构建以及八共享文件不改。
本候选不是正式接入；不生成 PnR/fs，不安装、不串口、不接线或烧录。

## 存储与周期合同

正文为 8 个独立 byte lane，每 lane 1024×8，地址为 `{bank,event_index}`。
一个同步只读 A 口永远归公开读；同步 B 口归暂存写/验证/UART READ。
DATA 的完整 byte offset 经加法后拆 event_index/byte_lane，允许首包1字节后128字节等非对齐分包。
正文没有 reset/初始化循环；复位仅清有效/count/id/session/cache/read_seen 等元数据。
首次有效读之前 read_seen 将未初始化 RAM 输出屏蔽为0。

公开请求在该 posedge 采地址并同步输出，rd_valid 同沿寄存，与原公开一拍合同相同；
可每拍连续请求。COMMIT 同沿 A 口采旧 published_bank，下一沿才读新银行。
UART READ 使用 B 口，不占 A 口，不会偷走公开请求。
无外部 ready，无修改线上 bytes/CRC/序号/ACK/READ 语义或20ms/5s超时定义。

VERIFY 分 issue/use 两沿逐字节计算原 CRC 和事件合法性，最多8192沿（512记录），
增加的内部等待小于115200停等 ACK 截止时间；最终 CRC 完成才原子发布。
UART READ 插入 READ_WAIT/READ_REPLY，两沿后用同步结果组帧；重复成功请求仍原字节缓存重放。
COPY 写入按原主状态机优先级抑制 reset/session timeout/UART frame error 下最后一笔写。

合法 A 读 published、合法 B 写 staging，且写期间二者银行不同；同址跨口读写不在合同可达范围。
B 自身 write-first/read-first 输出不被 COPY 消费；VERIFY/UART READ 前有独立地址发起沿，
不依赖厂商未定义的同址写时读值。元数据提交后下一 BEGIN 才重新选择非 published 银行。

## 验证方式

只对新 RAM 候选运行真实40MHz/115200 UART RTL；原 uart_rx/uart_tx、PC codec、原协议 oracle只读引用。
原685场景继续服务同协议新实现，并加容量1、首包1随后128跨lane边界等46场景。
公开读 Golden 独立由原JSON的 tick/type/channel/note/velocity 组小端64bit，不取 DUT 数组或银行当期望。
公开读在 UART 整帧期间连续轮询；COMMIT 请求定向保持有效索引0，强制检查同沿旧数据。
原独立 check_capture 复算全部实际 TX CRC/payload/metadata、540+新增 READ及公开完整快照。
正常轨迹必须完整 END 且覆盖 COPY/VERIFY/UART READ 并发读、非法/未发布读与至少2次COMMIT旧数据。

两个编译行为反例分别只改 A 读地址和发布银行；必须编译成功且触发指定
`RAM_PUBLIC_DATA_OR_BANK` 断言，编译失败、超时、缺文件不计负例通过。
单独4项 reset probe 用只读内部 FSM 仅定位 reset 注入沿（不是 Golden）：
COPY、VERIFY_USE、UART READ_WAIT、VERIFY最终发布前沿；每项检查3个复位沿无陈旧有效，
随后真实 UART 新上传及公开读恢复。外部合同与元数据和独立事件字节判定恢复，不以清RAM求通过。

第一开发轮因变量声明顺序编译失败；第二轮/第三轮完整串行轨迹，但定向COMMIT旧读覆盖不足，
终验拒绝。旧原日志保留；不能以其 END 或 simulator exit0 当合格通过，最终收据独立。

## 一次综合与限制

任务允许一次新模块综合。必须先模块正负及复位测试通过且源码 SHA 一致，
然后 `synthesize.py` 在新目录执行一次600秒有界 native GowinSynthesis。
器件沿既有精确 L 工程 `GW5AST-138C / GW5AST-LV138PG484AC1/I0`，25ns/40MHz；
只综合接收模块与原UART，不加正式工程/PLL/CST，不布局布线。
原始 hierarchy XML、工具日志/报告/源配置 SHA 与正文 memory 原生映射逐项核对；
只有模块总BSRAM数不够证明正文已进BSRAM，资源失败也不自动换实现重复综合。
M2引用的 f02a2c4 目前不在本机/已取远端历史中，不能声称已读该提交；
其交接要求已按“层级XML＋独立SHA＋原生正文映射”落实，不借用旧资源数字作为本轮结果。

结果、实际命令/耗时/退出码及未验项见 DELIVERY；本文件不预先声称仿真或BSRAM推断成功。
整机声音共存/CDC/复位集成、40MHz物理STA、实际FPGA上传/无线/板测仍由 M2 另安排。
