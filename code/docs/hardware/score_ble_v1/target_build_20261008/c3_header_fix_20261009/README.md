# C3 单行头文件修版：新身份与执行入口

授权依据：M2 D041/V0232，develop ce5df51，用户已在本会话转交授权。
业务补丁仅 main.c 在 host/ble_hs.h 后新增 host/util/util.h；LF 8643→8671 bytes。
旧 SHA 1c93e0eb4b40cdb857821086ce9fd6641a28a11486f97259d5ea0a8453bd2f12；
新 SHA c7e46b813e9f51cbaefcc658912bd629bd45d74f8ad18f85b1aa330ba5d97a17。

原 D040 baseline.json、旧10源表、原失败 c3_01、原 APK 收据、profile 和封存不修改。
run.py 默认仍使用 d040 旧身份，不能接受新main。新执行必须显式指定
`--source-profile c3_header_fix_20261009`：校验批准记录固定旧/新SHA、其它9源及去新增行的旧字节身份。
不从当前源随意收SHA当批准值；不关闭任何旧检查。新receipt保存profile/授权/runner/前后输入SHA。

在实际已导出的固定 ESP-IDF v5.4.2 环境、仓库根目录执行一次；输出目录必须全新：

```bat
"E:\FPGA\SDKs\espressif\tools\python_env\idf5.4_py3.11_env\Scripts\python.exe" -B -X utf8 code\software\score_ble_test_candidate\target_build_20261008\run.py c3 --source-profile c3_header_fix_20261009 --output code\output\m3_t059_target_20261009_c3_header_01 --idf-root E:\FPGA\SDKs\downloads\20261008\esp-idf-v5.4.2\esp-idf-v5.4.2 --idf-tools E:\FPGA\SDKs\espressif\tools --idf-python E:\FPGA\SDKs\espressif\tools\python_env\idf5.4_py3.11_env\Scripts\python.exe --timeout 1800
```

工具版本、SDK/submodule、真实编译/器件/配置/产物校验仍走原流程。禁止自动重试构建、
改sdkconfig.defaults、函数参数、协议、GPIO、告警策略或工具版本；新编译错误交M2另批范围。
SDK Windows ZIP的执行位差异只通过本次子进程Git core.fileMode=false忽略，内容检查保留；
这不写SDK配置或系统环境。构建与仓库门禁的日志/退出码/原输入及产物另封存。

runner隔离测试包含原6项与7项新profile测试；旧版/精确新版、额外行/业务变更、移位include、
其它9源逐个变更、错误expectedSHA和未知profile均独立核对。该测试不启动目标编译、无线或设备。
不重新跑APK、波形、1128桌面压力；不安装、flash、打开设备串口、接FPGA或做整机STA。
目标构建成功仅增加精确固件的目标编译证据，完整T059及实体/无线验证仍未关闭。
