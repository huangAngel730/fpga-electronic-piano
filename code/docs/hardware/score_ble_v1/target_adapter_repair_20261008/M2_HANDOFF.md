# 给M2：D040三项定点返修交接

待用户转发，尚未送达。提交号/是否推送以最新交接消息与包内DELIVERY_STATE.json为准。

M2，已基于批准起点5be92d9完成D040两文件三项返修：main.c绑定UART读取前后
connected/epoch/conn身份；MainActivity.kt取消旧扫描timeout并校验代次/销毁状态，
按完整UTF-8日志行计量4MiB上限。未修改协议/CRC/session/seq/offset、8个其他冻结源、
原10源清单、旧证据、共享登记、FPGA/工程/约束；未重跑波形和1128夜间事务。

新同源隔离专项a5实际退出0：UART284场景/3379断言、安卓同源JVM287判断通过。
5个新行为变异及3个旧缺陷复现全部编译退出0后运行退出1，被指定语义断言拒收；
早期两次夹具编译失败另保留，不计反例通过。详见REPORT.md及evidence/raw_manifest。
门禁最终结果请核对包内final_gate/receipt.json和stdout/stderr；gate2九项PASS只是
整理前记录，不替代最终树门禁。请复核后统一登记，完整T059仍不关闭。

新main.c SHA256：
`1c93e0eb4b40cdb857821086ce9fd6641a28a11486f97259d5ea0a8453bd2f12`。
新MainActivity.kt SHA256：
`8f2b3baab7a327ecc0205f02077f3b2b301228b8bc283a74aa01f4462cf37f38`。
两旧新SHA及8源未变详见baseline.json；seal.py仅增加批准两源历史身份区分，
未把旧receipt/运行改标新adapter通过，旧FILE_LIST原件另封存。

本次是实际宿主编译运行与目标源码绑定逻辑验证；Kotlin→Java受限拼写适配不是
Kotlin编译器，SDK/Handler mock不代表目标调度。缺完整ESP-IDF/RISC-V、Android SDK/
Gradle/JDK17/Kotlin环境，未构建C3固件/APK，未安装/烧录/接线/无线/整机STA。
后续请确认已有完整目标工具路径；正式集成与新整机STA仍由M2负责。
