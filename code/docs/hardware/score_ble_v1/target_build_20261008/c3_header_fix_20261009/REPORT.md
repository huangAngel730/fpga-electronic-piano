# D041 单行修版已实施；唯一 C3 构建环境失败

2026-10-09。本轮业务源码精确补丁及新身份绑定完成，13项runner基础设施/身份测试通过；
唯一真实C3 build失败，不能交付成功固件，不能签目标编译L1或关闭T059。
本次失败源于M3代理的构建启动准备，不能归因于M2授权错误或业务代码的新缺陷。

## 实际改动

main.c仅在host/ble_hs.h后新增host/util/util.h一行，原8643→8671bytes，LF SHA
`c7e46b813e9f51cbaefcc658912bd629bd45d74f8ad18f85b1aa330ba5d97a17`。
去新增28字节后SHA恢复旧`1c93e0eb4b40cdb857821086ce9fd6641a28a11486f97259d5ea0a8453bd2f12`。
其余9功能源逐项匹配M2授权值；D040 baseline/旧profile、旧失败c3_01和APK结果不回填。

run.py/test_run.py按批准范围增加显式新profile读取、精确SHA及单行位置/去行身份核对，
仍默认d040、仍拒绝新版main冒充旧身份。新profile.json固定授权文档SHA、旧/新SHA及其余9源；
没有从当前任意文件生成批准值，没有删除旧源/工具/SDK/配置/拷贝/目标器件/产物检查。
新receipt保存profile/授权/runner和前后源配置身份。invoke.py只采集新自检、门禁及单次C3命令，
不安装、联网下载或操作设备。

13项自检真实exit0；覆盖旧profile接受旧版/拒新，新profile接受精确新版/拒旧，
额外空行、额外注释、函数参数变化、重复include、移位include、其它9源逐个变更、
错误expectedSHA和未知profile，原版本/非零/超时/缺工具不得启动目标编译的检查保留。
它们是runner及身份检查，不是重新执行旧桌面协议压力或固件行为实测。

## 唯一真实构建结果

实际本机develop HEAD ce5df51（业务修版/runner仍为本地未提交改动），明确启用
`--source-profile c3_header_fix_20261009 --timeout 1800`，新实际输出在
`code/output/m3_t059_target_20261009_c3_header_01/m3_t059_target_20261009_c3_header_build_01/`。
完整原命令见receipt.steps/c3_build，不修改其路径或时间。

ESP-IDF v5.4.2/PINNED_IDF、clean/递归子模块、GCC14.2.0、CMake3.30.2、Ninja1.12.1、
Python3.11.2及依赖前置检查均exit0。新main拷贝SHA和单行身份通过。
idf.py build实际exit2、runner exit1、未超时；build19.313秒、runner总28.078秒。
source_config_unchanged=true、runner_profile_unchanged=true、target_build_passed=false。

新终止错误来自SDK usb_serial_jtag_connection_monitor.c.obj.d依赖文件无法打开：
本次启动器多嵌套了一层输出目录，该绝对依赖路径273字符；CMake已经给出250字符对象路径警告。
长路径是有日志和实际路径长度支持的原因判断，尚未通过短路径重新构建验证。
同时，启动器只手工拼工具PATH及IDF环境，没有执行完整官方export，漏ESP_ROM_ELF_DIR，
导致gen_gdbinit.py环境异常/CMake警告；它不是本次Ninja终止的同一错误。
本机esp-rom-elfs/20241011已经安装，不需要为这个缺变量重新安装SDK。

新输出没有main.c.obj、没有完整应用bin/elf/map。不能因为未出现旧隐式声明报错就说
main已编译成功；本次甚至尚未完成该编译项。中间sdkconfig/compile_commands/对象存在不等于固件。
原stdout SHA `9c81c1464abd98d9c6882bba9323b581516e2da0a9585783aa028b90a4d84fd7`；
原stderr SHA `42371ad3c2170c159960a2ff34706bc229affe8c3a69067991d7638f9ae1c28b`。

## 最小后续范围：仅申请，不重试

唯一一次授权构建已经消耗；没有自动重试、修改源码/SDK配置/工具版本或关告警。
请M2确认可再追加一次1800秒构建，仅纠正启动环境和新输出路径：

1. 先在子进程执行既有SDK官方export.bat完整导出，核ESP_ROM_ELF_DIR和实际工具路径；
   不手工漏项，不改SDK文件或系统PATH，不安装/下载。
2. 将真实runner输出直接放新`code/output/m3_t059_target_20261009_c3_header_02/`，
   不再套第二个长目录；日志收据另存，不移动/覆盖此次失败输出。
3. 单行修版、新profile和所有冻结检查保持；若新业务/编译错误再另报，不继续修源。

仓库门禁为另行真实执行，原日志、9PASS计数、退出码及追踪输入前后身份见交付包gate记录；
不沿用旧245.766秒的历史门禁。没有提交/推送；共享看板/当前状态及编号由M2收口。
APK目标编译已M2限定签收，本轮不重跑APK、波形、1128压力、RTL/Gowin专项。
未安装APK、flash、打开设备串口、接FPGA、扫描无线或做整机STA；完整T059未关闭。
