# T059桌面验收边界

真实执行对象：GCC编译的C桥、javac编译的Android共用Java协议核心。
GATT/UART/FPGA设备由桌面模拟，不是本轮RTL，不是实际无线或手机。
原T057 660对有效请求/真实RTL封存回复只读SHA核验后逐字节回放，不重跑原RTL。
模拟FPGA参考只用于此软件阶段（记录/原子提交/重复ACK）；它不能代替完整正式FPGA协议验证。

入口为 `code/scripts/run_m3_score_ble_acceptance.py`。输出唯一目录，进程300秒、流程1800秒，
超时终止本runner自己的子进程树。完整capture收集exit0，然后独立checker比较、反例exit1。
两个C行为反例是取消CRC拒绝、GATT片段提前发UART；拒收不能用编译错或超时顶替。
正向8522桥检查，7357 Java/C联合模拟检查，512/4096B完整读回，660对原回复回放。
权限/蓝牙/双目标测试只测共同Java门控函数，**Android系统callback/UI本身未运行**。
