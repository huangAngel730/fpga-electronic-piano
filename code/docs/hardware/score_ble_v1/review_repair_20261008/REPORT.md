# T059损坏分片24条原始字节补证（2026-10-08）

按M2 V0215反馈和用户本轮授权，只改测试与交付证明。C/Java业务源、旧capture/receipt/
证据ZIP、旧夜间验收均不改。原24条标签日志仍只能证明旧输入计划，不是旧实发hex。
这里交的是新版桌面真实执行证据，不追认旧capture，也不代表无线/设备通过。

## 修改

- acceptance.py在MISSING_FRAGMENT、DUPLICATE_FRAGMENT、OUT_OF_ORDER场景，直接把
  实际传给C子进程stdin的`G 0 <hex>`命令写入capture，不再写damage fragment标签。
- 独立新增commands.jsonl，逐命令封存Process实际调用和返回（含最后Q），与capture绑定。
- 旧公开参考计划SHA保留于原源码快照，新计划SHA固定为
  `bf83514bc7a7d4cde2b3073d912cfd0ca55e0c01423ba6e9ef13a72c94924441`。
  新摘要仅体现24个command字段改为具体字节，expected/actual和其他8498条全相等。
- 新audit.py用独立struct/binascii CRC生成三个损坏流，逐片对照实际hex及命令记录；
  每一条另做合法十六进制单字节篡改，公开CLI必须按PUBLIC_REFERENCE_PLAN_CHANGED拒收。
- seal.py --verify区分原执行源快照与新执行收据，不改旧source_sha256或旧证据manifest。

## 实际执行

`m3_score_ble_review_repair_20261008_a2`桌面入口退出0，真实MinGW GCC6.3.0 C99
`-Wall -Wextra -Werror -pedantic -O2`编译0；现有JDK11.0.2 javac
`--release 8 -Xlint:all -Werror`编译0，Java/C桌面真实执行（FPGA/GATT对端模拟）。

- 正向8522桥检查及660对封存T057回复回放通过，不是本轮新RTL/实体UART。
- Java/C联合7357检查、512事件/4096字节完整读回通过。
- 24条具体损坏分片：missing7、duplicate9、out-of-order8；实际命令与独立字节参考相等。
- 原25个其他执行源身份全部保持；另外8498条capture记录与旧正例逐字典全等。
- 8522条实际命令/回复与新版capture绑定，Q为第8523条记录。
- 两行为反例均真实编译0/完整capture8522运行0，checker以CRC_REJECT和NO_PARTIAL_UART
  各退出1；5原损坏capture均拒收；新增24条命令字节损坏逐条公开CLI退出1。
- fragment_audit独立入口退出0，原证据ZIP全部成员原件SHA复验，不改原archive。

第一轮a1桌面通过后补独立实际命令sidecar，再用同一业务源完整执行a2；不把a1标FAIL，
也不把a2新增字段或原件倒填进a1收据。两轮输出均保留，不重复夜间1128事务任务。

## 复现

```powershell
python -B -X utf8 code/scripts/run_m3_score_ble_acceptance.py --output code/output/m3_score_ble_review_repair_NEW
python -B -X utf8 code/software/score_ble_test_candidate/review_repair_20261008/audit.py --run code/output/m3_score_ble_review_repair_NEW
python -B -X utf8 code/docs/hardware/score_ble_v1/seal.py --verify
```

新evidence以gzip/base64保留receipt、capture、实际命令、Java/C联合trace、所有编译/运行/
拒收stdout/stderr和原acceptance.py快照；FILE_LIST对应新版本，旧清单/DELIVERY另封存。
源/产物SHA及精确命令见新receipt，DSP/STA无新增结论。

最终门禁`m3_score_ble_review_repair_20261008_gate2`九项全PASS、exit0；本轮7份Python
另做AST检查通过。既有辅助ROM readmemh ERROR日志保留，不因总门禁PASS宣称已修复。

未执行：ESP-IDF固件/APK目标构建、Android系统权限/UI/真实回调、无线、两块实体身份、
物理UART/FPGA存储/播放/接线/安装/烧录。本阶段仍桌面L2/限定协议参考，不关闭整个
T059；完整SDK缺口和安装许可保持，M2统一复核登记，M3不改共享状态。
