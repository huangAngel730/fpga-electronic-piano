# T059 夜间冻结C/Java核心压力验收

执行日期：2026-10-08（Asia/Shanghai）。M3自审，待M2复核，不签收整个T059。
固定任务cb6e08c及a17803c/4739e39/dd689ec的10项源SHA，开始/结束一致。
只新增night_stress_20261007与本报告目录；核心/Activity/main.c/旧runner/旧证据全部只读。

## 实际编译与事务

GCC6.3.0实际编译bridge.c＋新host.c，`-std=c99 -O2 -Wall -Wextra -Werror`，exit0。
已有OpenJDK11.0.2 `javac --release 8 -Xlint:all -Werror`实际编译Protocol.java＋新NightClient，exit0。
Java stderr的`Picked up JAVA_TOOL_OPTIONS: -Dfile.encoding=UTF-8`为环境提示，已保留。
不是用桌面工具代替C3 main.c或Kotlin Activity目标构建。

seed590710、固定刺激计划SHA `345cdcac46d258f8e5924492753b3d1543d2d98b70b09a85cd4551bc6188e99e`。
**1128个独立有界事务**：528全量上传/读回成功、184实际ABORT ACK取消、240断线失败退出、
176丢全部ACK后按预期ACK_DEADLINE退出；这些失败是明确的期望故障场景，不冒称1128次上传成功。
事件容量1/2/511/512分别462/470/66/130次，full512所有32个DATA边界前后断线均覆盖。
BEGIN/DATA/COMMIT/READ回复前/后取消、部分回复超时/恢复、同bytes丢ACK重试、错误身份/seq/
offset、不跨epoch、CRC/长度/方向拒绝均实际运行。

主capture与checker exit0，两个真实host均exit0。**465,483**项断言、**3,864,298**字节比较，
42586个经过真实C核心UART队列的请求，34540条READ反馈核对，队列峰值2。
所有256字节透传、20字节/随机1…20分片、合包与有界队列busy覆盖；同tick顺序逐条比较。
全部transactions身份与固定计划一致，不把分片/写回调数当事务数。
正常capture40.953秒、整套59.343秒，所有进程/步骤有界，无超时或无限后台。

本地Write回调只记录TRANSPORT_ONLY；peer回复前Session不进下一阶段。
旧曲谱保持/新session恢复由明确的独立synthetic SimPeer建模；在途COMMIT已经应用、
尚未收到ACK时取消不可回滚，测试按已提交曲谱核对，不捏造真实FPGA应用结论。

两新host反例编译0/capture正常0，独立checker各exit1：改UART payload→SEMANTIC
ALL_256_PAYLOAD_BYTES；吞Notify→SEMANTIC NOTIFY_PRESERVE_REPLY。首个语义差异后有界结束，
不宣称反例也完成1128次。空/截断/错计数/改字节capture全部非零拒收。
参考断言计划SHA `0be6569b569912a3371731a85d4971d5468580be797a2726e82b75ed9c11e0c4`。

## 命令/证据

```powershell
python -B -X utf8 code/software/score_ble_test_candidate/night_stress_20261007/run.py --output code/output/m3_night_ble_NEW
```

实际输出 `code/output/m3_night_ble_20261008_002436`。
original_receipt、summary含真实命令、返回码、源/EXE/class/捕获SHA及完整事务身份。
原stdout/stderr已封存。约9MB压缩host/check全文放独立SHA校验转发ZIP，避免把大型临时
压力产物提交仓库。delivery_manifest列新增文件SHA。没有重跑旧T057 RTL或原旧专项。
原stdout/stderr及receipt用.gz.b64和raw_log_manifest逐字节保真；JSON可读视图统一LF，
ignored的原.log随ZIP提供，不误列为已上传Git文件。
九项仓库门禁9/9、exit0；子链历史ROM ERROR另行如实附原日志，不能外推音色正常。

## 目标构建缺口与未测边界

IDF_PATH/IDF_TOOLS_PATH、ANDROID_HOME/ANDROID_SDK_ROOT、JAVA_HOME/GRADLE_HOME均未配置；
PATH未发现idf.py/riscv32-esp-elf-gcc/gradle/adb/sdkmanager。已知用户.espressif、.gradle、
AppData/Local/Android/Sdk根目录另核存在性。只是限定位置探测，不声称遍历整台电脑。
无完整精确离线环境，故 **firmware.bin/APK未构建**，不安装、不下载、不编程、不接FPGA。

若后续明确批准或提供现成离线SDK：先核ESP-IDF v5.4.2的实际git commit、RISC-V工具链
和子模块；安卓需JDK17、Gradle8.9、AGP8.7.3、Kotlin2.0.21、API35/build-tools34.0.0
和依赖缓存。只在新output运行offline build，记录版本/SHA/errors；不得先flash或安装APK。
SDK及依赖下载/展开体积目前未实测，没有将估计数冒充实测；安装方案和磁盘预算需另批。

等级为桌面L2及限定参考比较，不代表NimBLE/main.c的500ms发送任务、实际UART/射频、
安卓权限/UI/系统GATT callback/两设备实际切换或真实FPGA存储验收。
Notify长时不可发只模拟为核心队列501ms不pop，验证有界保持与busy，不证明固件worker时序。
共享状态/编号由M2统一收口，不重复旧A～I等任务。

fetch已看到M2新增5254567/6231470复核：原旧capture24条damage fragment没有原hex，
旧交付补证尚待。本夜间hosts全文对新刺激记录具体command hex，但不冒充恢复旧24条
实发证据。本轮冻结旧源/旧capture，未擅自接手该新增返修；整体T059保持未完成。
