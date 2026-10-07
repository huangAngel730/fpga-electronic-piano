# GATT独立候选v0.1（待M2复核，不是T057协议变更）

| 项 | UUID／口径 |
|---|---|
| Service | 761e0001-6ccd-4aa4-9e21-104647415031 |
| RX | 761e0002-6ccd-4aa4-9e21-104647415031；Write with response，1～20B |
| TX | 761e0003-6ccd-4aa4-9e21-104647415031；Notify，1～20B，只有真实UART合法回复 |
| LOCAL | 761e0004-6ccd-4aa4-9e21-104647415031；Read/Notify，本地状态，不是FPGA ACK |

LOCAL为6字节：`version=1,error,epoch_low,epoch_high,to_uart_count,to_ble_count`。
error 0正常、1CRC、2格式/方向/串口错误、3队列忙、4超时、5离线。
错误累计计数和完整32位epoch留在核心，LOCAL只给低16位诊断；不作为session身份。
LOCAL不走T057帧重组、不携带提交成功字段。若Notify缺失，ATT失败/请求deadline亦须失败，
不把本地传输接受视为FPGA接受。连接变化、未订阅或队列满不允许继续一次旧上传。

T057 v1帧头/128B payload上限/CRC/score记录不变；需要安全认证/多用户/大MTU优化时另定。
当前候选无加密绑定和授权认证，只适用于受控实验，**不是生产安全方案**。
尚未批准FPGA电气连接、不扫描连接实物、不自动编程设备。
