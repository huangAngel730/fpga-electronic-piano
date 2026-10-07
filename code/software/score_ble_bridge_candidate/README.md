# T059 C3桥独立候选（未做目标固件构建）

固定 ESP-IDF **v5.4.2** / NimBLE / ESP32-C3。实际SDK commit、RISC-V工具链SHA须由
后续目标构建收据取得；本机尚无此SDK，不声称firmware.bin存在。桌面GCC只编译
`core/bridge.c + host.c`，不代替ESP-IDF编译`main/main.c`。

唯一应用UART：UART1，115200 8N1，C3 GPIO4 TX / GPIO5 RX；仅为C3端候选，
**不批准任何FPGA引脚或接线**。USB Serial/JTAG用于调试，应用数据不写USB日志。
BLE名称`M3-Score-<BT-MAC末3字节>`；设备完整地址仍须用户明确选择、逐块核对。
单连接，20字节GATT Write-with-response，MTU23即可；不申请较大MTU。

核心有双向142字节重组缓存、各2帧有界队列，合法完整请求才进入UART队列，
UART worker一次写入完整帧，不把无线分片间隙搬到UART。命令/字段/CRC均为T057 v1。
UART回复只能是对端合法ACK/NACK，按20字节Notify透传；不生成FPGA ACK。
CRC/长度/方向错误后隔离至静默期限；BLE片段2秒、UART片段20毫秒。
断线清双方缓存和队列，增epoch；在途已发UART字节不可撤回，App用新session、ABORT
然后全量重传，旧回复不能跨session推进。队列忙报本地错，不冒成功。

`main.c`由mutex串行保护状态；回调不无界阻塞、UARTworker可用有限30ms发送等待。
一个待Notify回复保留当前位置、最多500ms重试；FIFO/缓存满/奇偶/帧错清接收并报本地错。
实际无线时延、控制器缓存/NimBLE回调时序和UART溢出仍待目标构建及实物验收。
不提供自动flash或端口选择脚本，NVS异常不自动擦除。

GATT候选合同见 [GATT.md](../../docs/hardware/score_ble_v1/GATT.md)。准备好的构建入口：

```powershell
python -B -X utf8 code/scripts/run_m3_score_ble_acceptance.py --output code/output/m3_score_ble_NEW --idf-root C:/existing/esp-idf
```

必须先有已导出的准确v5.4.2环境。runner只build，不安装工具、不flash。
官方基础API：[ESP-IDF v5.4.2 NimBLE](https://docs.espressif.com/projects/esp-idf/en/v5.4.2/esp32c3/api-reference/bluetooth/nimble/index.html)。
