# T059 真实目标构建准备／独立入口

仅新增本目录和 `code/docs/hardware/score_ble_v1/target_build_20261008/`。
原 runner、两份 D040 adapter、其余冻结源、旧证据、共享登记均只读。
新入口不先跑桌面协议压力，不把宿主逻辑通过写成完整 T059 通过。

## 运行入口

在仓库根目录，用实际可运行的 Python 3.10+ 执行。当前 PATH 的 WindowsApps/python.exe
别名无法启动；本轮使用 Codex 自带 Python 的绝对路径，**不作为 IDF 虚拟环境**。

```powershell
$taskPython = 'C:\Users\songdongkuan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $taskPython -B -X utf8 code/software/score_ble_test_candidate/target_build_20261008/run.py preflight --output code/output/m3_t059_target_NEW_preflight --timeout 120
```

退出码 0 只表示请求阶段成功；2 表示环境缺项，不是目标编译成功；1 表示身份、配置或实际命令失败。
每次 output 必须不存在，固定在 `code/output/m3_t059_target_*`。没有安装／下载／设备命令。
压缩包只读，核 SHA／大小和版本标记；本轮不重做之前全 ZIP CRC 检查。

环境已具备后，在已导出的准确 IDF 环境执行（路径须换成真实路径，不要照抄占位符）：

```powershell
& $taskPython -B -X utf8 code/software/score_ble_test_candidate/target_build_20261008/run.py c3 --output code/output/m3_t059_target_NEW_c3 --idf-root E:/FPGA/SDKs/espressif/esp-idf-v5.4.2 --idf-tools E:/FPGA/SDKs/espressif/tools --idf-python E:/FPGA/SDKs/espressif/tools/python_env/ACTUAL_ENV/Scripts/python.exe --timeout 1800
& $taskPython -B -X utf8 code/software/score_ble_test_candidate/target_build_20261008/run.py apk --output code/output/m3_t059_target_NEW_apk --java17 E:/FPGA/SDKs/java/jdk17 --gradle E:/FPGA/SDKs/gradle/gradle-8.9/bin/gradle.bat --android-sdk E:/FPGA/SDKs/android/sdk --gradle-cache E:/FPGA/SDKs/cache/gradle --timeout 1800
```

C3 核精确 tag/commit、子模块状态、GCC14.2.0/CMake3.30.2/Ninja1.12.1、Python依赖，
从真实工程逐字节复制到全新 output，实际编译 main.c，要求 bin/elf/map/sdkconfig 等存在。
APK 核 JDK/javac17、Gradle8.9、SDK35/BuildTools34.0.0，使用 `--offline`，禁 SDK／JDK自动下载。
真实 Activity、Protocol 和 Manifest 全部复制；验证 Kotlin／资源任务及 APK 内 Activity/Protocol。
依赖目录存在不代表传递依赖全齐，缺缓存时原样 FAIL，不自动安装。

日志逐命令保留原 stdout/stderr、退出码、超时标志与SHA。超时仅终止该次构建的进程树；
若系统拒绝树清理，保留错误、只终止直接子进程，不能声称所有后代已清理。
默认预算1800秒，上限3600秒；清理另有最多15秒等待。目标成功也始终 `complete_t059_passed=false`。
工具本身的厂商构建分支尚未在本机执行，不能把 runner 自检当成目标入口已验证。

## 本阶段采集与封存

```powershell
& $taskPython -B -X utf8 code/software/score_ble_test_candidate/target_build_20261008/collect.py execute --output code/output/m3_t059_target_prepare_NEW
& $taskPython -B -X utf8 code/software/score_ble_test_candidate/target_build_20261008/collect.py seal --output code/output/m3_t059_target_prepare_NEW
```

`execute` 只用于当前缺环境的阶段1：6项runner自检、preflight/C3/APK缺项检查、九项仓库门禁。
不跑1128事务、不新增损坏capture、不调用 flash/adb/串口。`seal` 写新证据子目录并分别打两个小包，
拒绝覆盖旧封存。后续真实成功构建需另建收据／产物清单，不复用“环境缺失”的结果。
