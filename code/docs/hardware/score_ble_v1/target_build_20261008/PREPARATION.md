# T059 下一阶段：真实目标构建条件与准备方案

日期：2026-10-08（Asia/Shanghai）。本阶段只是条件核查／配置／复现资料，未安装、下载新工具、
目标编译、安装APK、flash、打开设备串口或接FPGA；完整T059不关闭。旧证据保持。
本轮真实收据记录本机 develop 为 `a0ba3d6666a1bc0abfffbf031e9f621733271ed0`，
包含 `6c8e0b83ac0e83f516386b7b06abcbdca4fe98e2` 的M2已签D040及8e43022登记。
没有自行pull／编辑共享状态；不把本地远端缓存说成实时GitHub，业务源按10源表核身份。

## 已核清的条件

实际路径／版本／缓存、原始命令和缺项见 C3、APK 各自 RESULT.json 与封存receipt。
检查范围是PATH、环境变量、显式规划路径及常见SDK目录，不是全盘穷举。若另有现成环境请提供路径。

| 项目 | 已冻结要求 | 本机实际情况 |
|---|---|---|
| IDF | v5.4.2，commit f5c3654a1c2d2a01f7f67def7a0dc48e691f63c0，完整子模块，ESP32-C3/NimBLE | 完整源码ZIP已下载，未展开；无已导出IDF环境 |
| C3 GCC | tools.json推荐 esp-14.2.0_20241119，GCC14.2.0 | 未找到已安装交叉编译器 |
| CMake/Ninja | 官方清单3.30.2／1.12.1 | PATH未找到 |
| IDF Python | 独立虚拟环境，依赖检查通过 | 未找到；本机Python不能代替已配套IDF环境 |
| JDK | 17，java与javac | Temurin17.0.20.1+1 ZIP已下载，未展开；PATH仍Java8u181 |
| Gradle | 8.9 | ZIP已下载，未展开；无已安装入口 |
| Android SDK | API35、BuildTools34.0.0、min26/target35 | 压缩包已下载，未展开；无现成SDK配置／许可记录 |
| AGP/Kotlin | 8.7.3／2.0.21 | Gradle源码已锁定；未发现项目插件／传递依赖缓存 |

JDK／Gradle／SDK／IDF共7个原下载包当前重新核SHA与长度，合计1,959,290,341bytes。
6 ZIP中心目录解压文件长度合计2,564,307,580bytes（约2.39GiB），是成员逻辑长度，不是实际磁盘占用。
IDF源码ZIP不是完整已安装工具链，4.6MB online安装器也不是完整离线SDK。
Android无新增自定义res文件，真实资源入口是现有Manifest及框架theme；不伪造资源编译结果。

AGP8.7官方表要求Gradle8.9/JDK17/BuildTools34.0.0，最高API35，与配置一致。
Kotlin2.0.21完全支持表的AGP上限8.5，8.7.3超出该表；Gradle8.9有官方脚注支持。
这仅是兼容风险，不是确定源码失败；冻结配置不升级，真正目标编译错误原样交M2。
来源：[AGP官方兼容表](https://developer.android.com/build/releases/agp-8-7-0-release-notes)、
[Kotlin官方兼容表](https://kotlinlang.org/docs/gradle-configure-project.html)。

## 分项下载与空间预算（没有实施安装）

从已经校验的IDF v5.4.2 ZIP内tools/tools.json读取，不跟随最新工具版本：

| C3官方工具包 | 精确版本 | 压缩下载bytes |
|---|---|---:|
| RISC-V GCC | esp-14.2.0_20241119 | 677812937 |
| GDB | 14.2_20240403 | 27942579 |
| CMake | 3.30.2 | 45404613 |
| Ninja | 1.12.1 | 275425 |
| OpenOCD | v0.12.0-esp32-20250422 | 2988858 |
| ROM ELF | 20241011 | 3540038 |
| 合计 | 官方C3／通用工具组 | 757964450（722.85MiB） |

完整URL、SHA保存在新receipt.downloads.idf_win64_tools，无需重新下载现有1.83GiB包。
GDB/OpenOCD只列官方工具组，不运行设备调试；不需要QEMU、esp-clang、模拟器、NDK或大型IDE。
另缺IDF独立Python及wheel，粗估200～600MiB；安卓AGP/Kotlin传递依赖粗估0.5～1.5GiB。
这些是工作预算，不是已经测得的清单总量；需实际解析后计量，不能承诺固定总下载量。
新增下载建议上限5GiB，E盘预留20GiB（原包展开、工具、缓存、两次构建等）；超预算先停。
本轮E盘约99GiB可用、C盘约14GiB，精确检查值见新receipt.disk，不将快照当实时保证。

## 可执行准备顺序（必须另获安装／下载及许可授权，当前不执行）

1. 优先提供已经安装好的SDK目录；若确实没有，再授权仅写 E:/FPGA/SDKs，保留原包与现有FPGA工具。
2. JDK ZIP展开到 E:/FPGA/SDKs/java/jdk17，使bin/java.exe直接位于该根下；Gradle展开到
   E:/FPGA/SDKs/gradle/gradle-8.9。只给子进程JAVA_HOME/PATH，不改系统Java8/VivadoJava11。
3. SDK命令行工具放到 android/sdk/cmdline-tools/13.0；由用户阅读接受Android许可后，
   使用同一JDK17下 sdkmanager --sdk_root=E:/FPGA/SDKs/android/sdk 安装
   "platforms;android-35" "build-tools;34.0.0"。可复用已核原包，不能自动yes接受许可。
4. 在独立复制工程中联网准备AGP8.7.3/Kotlin2.0.21及全部传递依赖，缓存固定
   E:/FPGA/SDKs/cache/gradle；只用现有Google/MavenCentral/GradlePluginPortal，禁第三方镜像。
   这需要额外下载许可。缓存准备后全新副本 `--offline assembleDebug` 才是本阶段真实目标证明。
5. IDF完整ZIP展开到短ASCII路径 E:/FPGA/SDKs/espressif/esp-idf-v5.4.2；核精确tag/commit/子模块。
   获授权后在独立Python环境按该tag `install.bat esp32c3` 或官方工具安装流程准备工具／依赖，
   IDF_TOOLS_PATH仅该环境设为 E:/FPGA/SDKs/espressif/tools；不复用Codex基础Python装依赖。
6. 按原tag export.bat/export.ps1导出环境，在新目录分别执行run.py c3/apk，详见新runner README。
   不运行 set-target 清理正式工程，不运行flash、monitor、adb、设备serial或APK安装。

官方依据：[ESP-IDF v5.4.2 Windows环境说明](https://docs.espressif.com/projects/esp-idf/en/v5.4.2/esp32c3/get-started/windows-setup.html)、
[Gradle离线缓存说明](https://docs.gradle.org/current/userguide/dependency_caching.html)。

## 交付边界

C3和APK独立出包。当前两者都阻塞在工具／缓存，不存在bin/elf/map/APK，不能写“目标编译通过”。
配置核查、压缩包身份、runner基础设施自检和仓库门禁可以交付，不替代真实目标执行。
未来目标报错保存原命令、源码／配置SHA、stdout/stderr、退出码及最小修复说明，先交M2批准，
不先改main.c／MainActivity.kt或其它冻结源。目标成功也不签无线、物理UART、实体或完整T059。

初期入口调试曾遇WindowsApps Python别名无法执行、sandbox临时目录权限及
采集子目录命名不符合入口prefix；这些是新runner基础设施问题，不是业务源码编译结果。
旧输出不删除，最终 `m3_t059_target_prepare_20261008_final2` 的新收据才是本轮交付依据。
