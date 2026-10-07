# 目标构建下一步（仅准备，无安装）

冻结候选要求ESP-IDF v5.4.2/ESP32-C3 RISC-V/NimBLE，以及Android SDK35、
build-tools34.0.0、Gradle8.9、AGP8.7.3、Kotlin2.0.21、JDK17。
版本来自当前候选README/Gradle配置/夜间任务单，不自行升级。

现有桌面工具GCC6.3/JDK11已用于本轮实际测试，不能替代上述目标工具。
20261008夜间只读窄范围检查中，IDF_PATH/ANDROID_HOME/ANDROID_SDK_ROOT/
GRADLE_HOME/JAVA_HOME未配置，用户常见.espressif/.gradle/Android/Sdk目录不存在。
这不证明全部磁盘没有SDK；若用户已安装，优先提供准确路径再检查，不重复安装。

下一阶段先确认可用工具路径/许可/磁盘空间与离线依赖缓存；完整环境成立后，在新的
独立output目录执行已有runner的目标build选项，封存版本/SDK commit/工具链/源/产物SHA。
如果环境不完整，先向用户报告具体缺口及安装范围/下载量，获得许可后再安装；当前
没有对下载量做在线核算，不虚构空间或耗时保证，也没有获准大型安装/下载。

只做build仍不能安装APK、烧录C3、开设备串口或接FPGA。目标API不兼容若导致FAIL，
先保留原输出/最小复现，冻结main.c/Activity需得到明确返修授权后才改。
