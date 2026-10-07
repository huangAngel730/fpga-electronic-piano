# T059 Android最小候选（APK未构建）

版本固定：AGP8.7.3、Kotlin2.0.21、Gradle8.9、JDK17、compile/target35、build-tools34.0.0、min26。
无Jetpack/云端/账号/后台/音频。没有签名密钥、Gradle wrapper二进制或SDK副本。
已执行Java11 javac `--release 8 -Xlint:all -Werror`编译/运行Protocol.java与Harness，
**没有编译MainActivity.kt/Android资源，不代表APK可安装或设备UI通过**。

导入严格v1 JSON（262144字节上限、拒重复key/小数/布尔数值/乱序/越界），保留同tick顺序。
扫描10秒，最多16目标，名称和完整地址显示给用户手动选；不给第一台自动连接。
需用户实际授予API31+SCAN/CONNECT或旧版定位权限；拒绝/蓝牙关闭不绕过系统。
前台销毁关闭连接，不申请后台权限。协议门控桌面测过，安卓权限交互尚未实测。

所有GATT Write串行、每片20字节；其callback只记TRANSPORT_ONLY，不能完成FPGA事务。
TX和LOCAL分别订阅后才ready；本地桥错误与FPGA NACK分离。
单事务，每个请求最多2次相同原bytes重试，2秒ACK期限、总180秒；不按通知或到包时点播放。
每次上传先ABORT、再新的非零session（应用持久化递增），BEGIN/DATA/COMMIT/STATUS和
全部READ逐条比较。旧session/seq/offset回复忽略，CRC坏/形状坏/NACK失败。
取消用独立seq65535 ABORT，当前完整帧发送完后再发送ABORT，真实ACK才显示取消。
断线清发送队列和重组，重连必须重新开始整个事务，不续接旧碎片。

原bytes日志SAF导出，上限4MiB，超过上限停止追加（UI继续显示），不声称超限日志完整。
一次操作只修改App状态，无任何FPGA演奏触发。设备身份与实际权限流程仍未验证。

已有完整SDK/依赖缓存时可执行（不会联网下载、安装APK或接触设备）：

```powershell
python -B -X utf8 code/scripts/run_m3_score_ble_acceptance.py --output code/output/m3_score_ble_NEW --gradle C:/existing/gradle-8.9/bin/gradle.bat --android-sdk C:/existing/Android/Sdk --java17 C:/existing/jdk17
```

官方依据：[AGP8.7兼容表](https://developer.android.com/build/releases/agp-8-7-0-release-notes)、
[Android BLE权限](https://developer.android.com/develop/connectivity/bluetooth/bt-permissions)。
