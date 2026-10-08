# T059 目标适配器定点返修隔离验收

依据 D040，批准基线5be92d9。仅main.c和MainActivity.kt是功能例外；原夜间10源清单、
旧capture/runner/证据保持不变，当前另外8功能源仍逐字节核SHA。

```powershell
python -B -X utf8 code/software/score_ble_test_candidate/target_adapter_repair_20261008/run.py --output code/output/m3_t059_target_adapter_repair_NEW
```

使用现有MinGW GCC6.3和Vivado JDK11，不安装工具。runner提取实际main.c中的ms、
gap_event、reset_cb及整个io_task，原样编译到SDK mock宿主，链接真实冻结bridge.c。
模拟读取中/读取返回后锁前交错、相同handle不同epoch、断线/复位/失败连接、近回绕、
正常/部分/空读、旧读取丢弃后恢复和pending/position清理；不把阻塞读取移入mutex。

Android无Kotlin编译器/SDK：仅提取Activity标记区纯JVM函数/字段，经受限且明确的
Kotlin→Java语法适配后由javac编译运行，保留原条件、常数、函数体及Java UTF8编码。
这不是通用转译器，不验证Activity整文件Kotlin语法、API、Android Handler或手机UI。
扫描启动/停止/导出接线另做静态source binding；宿主调度器只测上述同源条件/取消函数。
完整生成的Java/C源、两个旧新源快照、命令/版本/日志/退出码/SHA封存在新output。

正常版真实编译/run退出0；移除UART代次guard、扫描token、扫描取消、改UTF16计量、
漏完整line计量的变异须compile0/run1且出现指定断言。旧C目标函数和两个旧安卓算法
模型亦须特定拒收。编译失败/超时不计反例通过。
UTF8覆盖ASCII/CJK/emoji/混合/多行/非配对surrogate、完整时间戳分隔换行、恰好4MiB、
超1byte/单条过大/饱和/空导出、4线程串行化与真实Protocol.Session在日志满时继续发送。

每子进程≤600s，总专项≤1800s，独立新output拒绝覆盖。发现FAIL留原日志，不改旧包。
无需重复波形/1128事务/RTL/Gowin。新版本的完整ESP-IDF固件/APK、无线、物理UART、
手机回调和整机STA未执行；没有设备权限或SDK下载/安装许可。旧runner的10源冻结
断言不适用两文件修版，不能改旧清单；历史交付只读原source快照核对。
