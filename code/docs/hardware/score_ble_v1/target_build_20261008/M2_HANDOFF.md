# 给M2：T059目标构建条件与独立实测准备

M2，按下一阶段任务单已完成第一步构建条件核查，并准备第三步实测方案。
真实本机develop为a0ba3d6，包含已签6c8e0b8／8e43022；10冻结源身份通过，
两份D040业务源、其余功能源、旧runner／旧证据和共享登记均未改。

C3和APK分别交付条件包。真实preflight及C3/APK入口都exit2、BLOCKED_MISSING_ENVIRONMENT，
未调用ESP-IDF／Android目标编译器，没有bin/elf/map/sdkconfig/APK新产物，第二步未完成。
C3缺展开的IDF5.4.2和配套RISC-V GCC14.2.0／CMake3.30.2／Ninja1.12.1／独立Python依赖；
APK缺展开的JDK17／Gradle8.9／SDK35/BuildTools34.0.0、SDK许可及AGP8.7.3/Kotlin2.0.21完整离线缓存。
本轮只读检查PATH、显式路径和常见SDK根，不声称整盘不存在其它安装，请提供准确已有路径。

7个已有下载包重新核SHA/长度通过，合计1,959,290,341bytes，不需重下；
IDF原tag官方工具组尚缺757,964,450bytes，Python/wheel及安卓插件传递依赖另有估算预算，
不是实测总下载量。建议准备下载预算5GiB、E盘预留20GiB；具体路径/步骤/来源见PREPARATION.md。
保留Kotlin2.0.21＋AGP8.7.3超出完全支持表的风险，不升级源码配置，后续按冻结配置实际构建后再判。

新增target_build_20261008目标专用入口、基础设施测试、采集/封存工具及文档；不重新做1128压力／大量损坏capture。
真实6项runner自检PASS，当前工作树九项仓库门禁9/9、exit0、168.859s；
5318追踪输入及3份新runner在门禁前后SHA稳定。完整命令、stdout/stderr、退出码、SHA、
冻结源身份和缺项均在两包新收据／manifest中。当前仅条件准备与入口自检，不声称目标构建分支已实跑。

独立实测步骤明确两块C3逐块完整地址/固件身份、Android权限/10秒scan/连接/断线恢复、
4MiB完整UTF-8日志、桥接收发与模拟对端ACK/真实FPGA ACK分级。本阶段只写步骤，未安装、
下载新载荷、flash、打开设备串口、接FPGA、扫描无线或做新STA。完整T059保持未关闭。

本轮新增文件尚未提交／推送；请复核条件与方案，并提供现成SDK/缓存路径，
或由用户另行明确工具准备安装／下载许可后再推进目标编译。M2统一共享登记。
待用户转发，尚未送达。
