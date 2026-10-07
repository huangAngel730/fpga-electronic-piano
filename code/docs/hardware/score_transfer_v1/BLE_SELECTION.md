# 蓝牙选型与采购准备（2026-10-07，T057）

用户最新确认：用于连接FPGA；主用1块+备件1块，合计2块；含运费总预算上限100元，优先50元以内。
状态：**选型准备；未下单、未付款、未到货**。配送城市/平台/付款安排仍待用户回复。
实际硬件修订号/固件版本只在商家确认和到货检查后记录，不编造版本。

## 不超过三个候选

| 项目 | 核实结果及取舍 |
|---|---|
| **推荐询价：微雪ESP32-C3-Zero-M，SKU25532，带排针版本，2块** | 厂商确认C3FH4、4MB Flash、BLE5、板载天线、USB-C和3.3V IO。排针方便独立UART验证。不是预装BLE串口桥，到货后独立MCU桥固件由后续阶段提供。国内人民币报价尚未取得，不把历史淘宝23元当2026现价。 |
| 备选：Seeed XIAO ESP32C3 Pre-Soldered，SKU102010633，2块 | 官方商品页当前显示单价US$5.90、In stock，商品小计US$11.80；运费/税费/结算汇率未知，不能据此承诺人民币含运费<=100元。额外天线/配件按实际商品清单核对，不另购OLED/扩展底板。 |
| 不采购：微雪Pico-BLE，SKU21474 | 预置AT透传、默认115200；但国内官方商品页显示仅定制50件起，与只买2块和100元预算不符，排除本轮。 |

来源与原始购买入口：

- [微雪官方说明：ESP32-C3-Zero-M/SKU25532](https://docs.waveshare.net/ESP32-C3-Zero/)。
- [微雪官方国内商品页（精确型号）](https://www.waveshare.net/shop/ESP32-C3-Zero-M.htm)，商家微雪电子；
  [厂家列出的天猫旗舰店](https://weixuesm.tmall.com/)。商品页有动态/WAF访问限制，本轮未获得有效人民币结算价。
- [Seeed官方预焊排针商品](https://www.seeedstudio.com/Seeed-Studio-XIAO-ESP32C3-Pre-Soldered-p-6331.html)，
  商家Seeed Studio；以上美元价是2026-10-07查询页面显示，不是下单锁价或国内送达承诺。
- [Seeed官方接口/供电说明](https://wiki.seeedstudio.com/XIAO_ESP32C3_Getting_Started/)。
- [Pico-BLE官方国内售卖限制](https://www.waveshare.net/shop/Pico-BLE.htm)。

询价目标不是已取得的价格：两块模块+必要线材+运费尽量<=50元；超过50但不超过100元先回传
具体报价和理由；超过100不得下单。建议不买电池，不需要Pico、不需要USB蓝牙适配器、蓝牙音频板。
排针版不得被卖家替换为裸贴片板、ESP32-C6/S3或无明确厂商的同名SuperMini；需要核对丝印/PCB修订。
收货地址只在结算页使用，不写入Git；不收集密码/验证码/银行卡信息。
当前浏览器核价工具未能初始化，尚未进入用户购物账号或结算页面；不能声称采购已落实。

## 安卓及FPGA链路

安卓GATT客户端 → 独立C3 BLE服务RX characteristic（Write with response）→模块缓存/重组
→3.3V非反相UART 115200 8N1 → FPGA本独立候选；FPGA ACK/NACK/READ →UART→C3
→TX characteristic Notify（安卓需启用CCCD）。无线不是BLE MIDI，也不是蓝牙音频。
先按MTU23对应20bytes特征载荷设计，长帧重组不假定一次write容纳142bytes。
停等及应用CRC/会话/序号/完整提交合同不因GATT写回调成功而省略；安卓必须收到FPGA应用ACK。
断线停止当前事务，新连接ABORT/新session完整重传；不由手机包到达时刻驱动音符。
服务UUID、缓存上限、断线策略和App由有线合同复核后另冻结，本轮不编写无线固件/App。
固件来源拟用[Espressif ESP-IDF NimBLE](https://docs.espressif.com/projects/esp-idf/en/stable/esp32c3/api-reference/bluetooth/nimble/index.html)，
通过独立模块USB编程；不是写板载BL616/JTAG或FPGA固件，本轮未烧录任何设备。
[Android官方GATT API](https://developer.android.com/reference/android/bluetooth/BluetoothGatt)支持特征写及通知订阅。

供电与电平：推荐C3板先用USB-C 5V独立供电，厂商IO为3.3V；**5V电源不等于5V IO容限**。
模块和FPGA UART侧共地，TX/RX交叉接；正式球位/Bank由M2批准，不给R17/U15/V14接第二推挽TX。
不要用USB-C与底板供电未经核实同时反向馈电，不假设FPGA 3.3V引出能承担模块峰值电流。
模块端UART GPIO21/20是厂商默认丝印，后续可选择独立UART引脚避免启动日志；不作为FPGA球位决定。
用户100元授权仅模块采购，不授权为了接线修改FPGA约束/配置或下载。

## 到货验收与采购收口

1. 订单核精确型号/SKU/排针/数量2/含运费总额，保存报价、实际订单与物流；付款未发生不记已买。
2. 两块分别拍丝印/PCB修订和配件，先不接FPGA；USB供电后测3.3V电源及UART空闲/输出高低。
3. 独立USB-TTL/PC对端验证115200双向原字节，避免5V TTL；固件和测试入口另行明确后执行。
4. 安卓独立发现/连接/通知，0..255二进制、142bytes分片、完整4096bytes/512事件，保存手机/串口原字节SHA。
5. 注入坏CRC/漏包/重复/断线/重连/取消，确认模块不报告假FPGA ACK；两个模块分别验证。
6. 有线合同通过、M2引脚和独立工程获批之后才接FPGA；到货或BLE测试不等于上板曲谱/播放通过。

尚缺：国内实际可下单报价、运费、配送城市、采购平台/账号可操作性、付款安排、商家PCB/固件版本
确认和预计发货/到货日期。未取得这些信息前不杜撰总成本或执行购买；采购和订单跟踪仍由M3负责。
