# T059 夜间冻结核心压力

只调用冻结 bridge.h/br_* 与 Protocol.java 的公开 API。host.c 与 NightClient.java
是新的桌面包装器，不修改旧核心、host、runner、Activity、协议或既有证据。

仓库根执行：

```powershell
python -B -X utf8 code/software/score_ble_test_candidate/night_stress_20261007/run.py --output code/output/m3_night_ble_NEW
```

`--gcc`、`--java-home` 可指定已有桌面工具；不安装、不下载、不打开设备。
公共执行器复用本轮新增的 night_blackbox_20261007/run.py，不调用旧专项 runner。
每次 host 请求响应至多等待 5 秒；每事务至多 560 个应用请求步骤。
ACK 最多 2 次同字节重试，单子进程 600 秒，整套至多 1800 秒。

固定 seed590710，1056 个上传/取消/断线/ACK超时事务，加 full512 的全部 32 个
DATA 边界各回复前/后断线 64 次，再加 BEGIN/DATA/COMMIT/READ 前后取消 8 次。
合计 **1128 个独立事务**，不是分片写次数。JSON 事件容量覆盖 1/2/511/512，
全量 READ 字节和同 tick 顺序与独立 Python 编码比较。失败后的旧曲谱保持及后续
新 session 恢复由明确的 synthetic SimPeer 建模；不声称真实 FPGA 存储原子性已重验。

真实编译 C bridge 与 Java Protocol；Python 负责驱动和独立 peer/oracle，不替代
候选执行。请求任意 1…20 字节分片，回复重新分成 20 字节 Notify 输入 Java；
另验合包、所有 256 个字节、错 CRC/长度/方向/身份/seq/offset、队列 busy、
双向碎片过期/u32 时间回绕、断线不跨 epoch、应用局部 BUSY、单目标选择门控。
transportWritten 只能输出 TRANSPORT_ONLY；真实模拟对端应用 ACK 才推进 Session。

Notify 不可发模拟为暂不 pop 队列，501ms 后仍检查有界容量和字节保持；这只覆盖
核心队列，不覆盖 main.c/NimBLE 的真实 500ms 待发任务、无线缓存或线程时序。
目标身份的公开 selectedTarget 门控通过不代表安卓两设备实际切换通过。

新 wrapper 反例损坏 UART payload、吞 Notify；编译及 capture 正常退出，再由
独立 checker 拒收特定字节语义。反例发现首个错误后有界结束，不冒称跑完 1128 次。
坏捕获包括空、截断、错计数及改字节，全部非零。

```powershell
python -B -X utf8 code/software/score_ble_test_candidate/night_stress_20261007/stress.py check --capture code/output/m3_night_ble_NEW/normal/checks.jsonl.gz --reference-hash <receipt中的reference_plan_sha256>
```

完整 host 命令/实际回应、断言逐项 expected/actual 在 gzip JSONL 中；参考计划 SHA
独立累计，检查完整尾记录/固定刺激计划/事务身份/覆盖数，不接受只改尾计数。
Git 中只保留轻量收据/摘要/原 stdout/stderr，完整原压缩 capture 在另交 SHA 校验 ZIP。
桌面 L2 不等于 C3 固件、Activity/APK、权限/UI、真实回调、射频或 FPGA 接线通过。
