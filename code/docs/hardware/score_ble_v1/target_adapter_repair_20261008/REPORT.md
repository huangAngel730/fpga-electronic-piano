# T059 三项定点返修独立交付（2026-10-08）

依据M2 D040/V0222、批准起点5be92d9，仅main.c和MainActivity.kt是功能修改例外。
原夜间10源清单/旧证据、8其他业务源、T057协议/CRC/session/seq/offset、GPIO4/5/
115200、UUID、公共FPGA/约束/工程及共享登记不改。本阶段不关闭完整T059，待M2复核。

## 实现

- C3在同一mutex保护下于读取前保存connected/epoch/conn，锁外blocking UART read，
  再持同锁比较任一身份变化则丢掉该次n字节。旧pending/position的epoch清理保留。
  不承诺识别断线后才到达物理UART的旧peer数据，原应用session/seq防线继续负责。
- Activity保存timeout Runnable；扫描重启/停止/失败/手动断开/销毁撤销timeout并增加
  generation，timeout同时检查generation/scanning/destroyed。扫描仍10s，不改权限。
- 完整line先包含elapsedRealtime、空格、text、换行，以实际UTF8编码统计增量；
  4194304字节以内追加，超限丢整条/不改旧日志、不递归log。独立incomplete标记在UI
  提示，上传继续；append/export同锁，UI调用集中在main looper，不截断导出的字节。

## 同源验证与真实结果

现有MinGW GCC6.3.0和Vivado JDK11.0.2，未下载SDK或安装编译器。
最终专项`m3_t059_target_adapter_repair_20261008_a5`真实退出0，约6秒：

- 当前UART：提取main.c真实ms/gap_event/reset_cb/整个io_task，原样编译，链接原core。
  SDK/FreeRTOS/串口/BLE为确定性mock；284场景、3379断言通过，compile0/run0。
  覆盖读前离线、读中及返回锁前身份变化、同handle新epoch、reset/连接失败、近回绕、
  正常ACK/部分/0/负返回、丢旧后新ACK恢复、pending和发送位置清理、读操作锁外断言。
- 当前安卓：实际Activity标记区字段/函数的受限Kotlin→Java拼写适配后javac编译；
  287判断、compile0/run0。确定性时钟验证t0开始、t5重启、t10旧timeout无效、
  t14.999仍扫描、t15新扫描结束；另含200次重启、正常结束/手动停/销毁、
  冻结Protocol权限门控；UTF8各种文本/完整line/边界/饱和/4线程串行化及满日志下Session
  继续发送。Activity实际调用位置/生命周期另作静态source binding。
- 5个行为变异：取消UARTguard、扫描token、扫描取消、改UTF16计数、只数text漏line。
  均真实compile0/run1，分别出现UART_GENERATION_STALE_QUEUE、SCAN_TOKEN、
  SCAN_CANCEL、UTF8_COUNT_MATCH_EXPORT等特定断言，不以编译失败/异常超时冒充。
- 旧C io_task函数在相同交错断言中compile0/run1；旧安卓scan条件和log算法的同源绑定
  模型compile0/run1，特定SCAN_LEGACY/UTF8_LEGACY拒收。后两项不是旧APK运行。
- 原批准两源SHA→新SHA另列baseline.json，8其他功能源当前SHA全部原样；旧源码快照
  与新快照均封存，旧10表不改。seal.py仅增加两文件历史身份例外，原检查不删除，旧
  receipt/ZIP/source_SHA不改。历史验证旧source用封存快照，不宣称新adapter跑过旧夜间。

## 未成功的夹具历史

a1：UART及guard反例通过；Android新夹具漏import org.m3.score.Protocol，javac退出4。
a2：当前UART/安卓和新变异通过；旧log夹具漏把Kotlin length属性改为Java length()，
javac退出1。这两项仅新测试适配器编译错误，均保留完整日志，不算行为反例通过。
a3：上述夹具修正后完整通过；a4增加两条冻结Protocol权限门控判断，282判断。
a5追加实际确定性时钟调度检查，最终287判断。此前输出全部保留，不改冻结C/Java核心。

## 仓库门禁记录

gate1退出1：DELIVERY.md末尾空白检查失败，另8项通过；门禁运行中修正文档，
因此该次tracked_inputs_unchanged也为false，不算通过，原stdout/stderr完整封存。
gate2退出0：九项全PASS，120.672秒，4754个已跟踪输入执行期间不变。
gate2早于a5测试夹具/本交付资料的最终整理，不当作最终树门禁；封存后另跑gate3，
最终实际日志、退出码及输入SHA放转发包final_gate/，不倒填gate2收据。

## 验证等级与工具缺口

仅宿主实际编译/运行、自检逻辑范围成立（限定L1/L2）；无ESP-IDF main整文件目标编译、
Kotlin编译/Android API链接、APK/真实Handler、无线/物理UART/手机权限回调/实物/STA。
不把受限拼写适配当Kotlin编译器，不把SDK mock当真实FreeRTOS/NimBLE调度。
本机未发现IDF v5.4.2/RISC-V工具链/Android SDK35/BuildTools34/Gradle8.9/JDK17或
Kotlin编译器；已有Java8/11和桌面GCC不能替代。范围窄查不是证明全盘绝无工具；用户
若已有完整路径先核对，否则只报告缺口，当前没有新安装/下载/设备编程授权。
未重复波形/1128夜间/旧RTL/Gowin，不将仓库公共回归称为新整机STA或音色问题已修。

## 入口与证据

```powershell
python -B -X utf8 code/software/score_ble_test_candidate/target_adapter_repair_20261008/run.py --output code/output/m3_t059_target_adapter_repair_NEW
python -B -X utf8 code/docs/hardware/score_ble_v1/target_adapter_repair_20261008/deliver.py --run-gate code/output/m3_t059_target_adapter_repair_GATE_NEW
python -B -X utf8 code/docs/hardware/score_ble_v1/target_adapter_repair_20261008/deliver.py --verify
python -B -X utf8 code/docs/hardware/score_ble_v1/seal.py --verify
```

后两个命令是证据/源身份校验，不是重复夜间/CJava专项。新raw_manifest按每份stdout/
stderr/源快照/生成CJava/receipt分别列长度/SHA；可执行产物不提交，其SHA保留。
旧FILE_LIST原件也独立封存。当前FILE_LIST只加新阶段/更新批准文件身份，不倒填旧版本。
交付提交身份及是否推送见转发包DELIVERY_STATE.json；M2交接待用户转发，尚未送达。
