# 给M2的T057阶段交接（待用户转发，尚未送达）

M2：M3已完成独立有线曲谱候选的PC编码/上传工具、40MHz UART接收/双银行存储RTL、
串行自检和独立读回检查器。只新增任务单五处授权位置，未改原UART/MIDI/STAT/top/pkg/
约束/PLL/封存L/BL616或共享看板；没有启动Gowin、烧录或打开实际串口。
本交接不扩大正式工程写入和硬件授权。功能提交号请绑定转发消息中的实际Git提交。

完整验收run_j_v22g6p总收据PASS：685场景、666实际响应、32错误事务，540条UART READ、
1206条公开读口事件比较，含全部512事件、跨事件分包、同tick Off/On和错误后恢复。
真实115200 UART位流和原RX/TX运行，TX由物理串行引脚独立解码；没有读DUT私有存储作真值。
原JSON独立期望核对CRC、序号、完整原子COMMIT、ACK重放、逐条READ及20ms/真实5s超时。
两个行为反例均编译成功并完整运行，再因具体公开读回/错误发布失败被拒收；23项损坏capture、
7项真实CLI非法输入/端口保护和6项软件测试PASS。PC离线重放540条实际RTL响应、丢3次ACK重试3次；
这是离线重放，不是在线PC↔RTL或板级UART通过。

完整入口3740输入九门禁PASS；之后已安全同步fd2b414。最新文件树门禁结果见FINAL_GATE.md，
不能把旧基线的门禁冒称新文件树门禁。执行源SHA、原字节Base64/长度/SHA、三份完整capture、
正负例原始stdout/stderr和命令收据均在本目录evidence/run_j_v22g6p，详情见DELIVERY.md。

复跑：`python -B -X utf8 code/scripts/run_m3_score_transfer_acceptance.py --repo-gate --publish`。
工具默认ModelSim SE-64 2020.4，可用--modelsim-bin指定。结果仅L2/限定L3，
未测实际USB-TTL/FPGA、Gowin资源/BSRAM/40MHz时序、正式播放/视觉、BLE/App；不放行下载。
公开读口同COMMIT拍返回旧银行，消费者须绑定发布身份；八路拼读/ACK CRC组合构造等需后续综合评估。

请你统一复核合同、源SHA和可恢复原证据，按需登记共享事实；正式球位/Bank/独立工程与播放调度
source_id由你另行冻结，不复用R17/U15/V14，也不因为独立候选PASS就修改现有整机。

蓝牙并行采购准备：用户已确认用于FPGA、主用1+备件1共2块，含运费<=100元、优先<=50元。
推荐询价微雪ESP32-C3-Zero-M（带排针，SKU25532），BLE↔3.3V UART；
它不是预置透明串口模块，后续需独立MCU桥固件。国内实际价/运费/城市/平台/付款安排仍待落实，
未下单/未付款/未到货。选型、官方购买链接、电气与到货验证计划见BLE_SELECTION.md。
M3继续负责采购准备/订单/到货核验；Android/App和无线实现等待有线复核后另定范围。

**待用户转发，尚未送达；M2尚未复核本功能提交。**
