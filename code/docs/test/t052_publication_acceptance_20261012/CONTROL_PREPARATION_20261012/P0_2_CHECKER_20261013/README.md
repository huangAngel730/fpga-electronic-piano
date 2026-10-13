# T052 P0-2：真实 capture checker 软件后继

本目录记录 2026-10-13 的静态／软件交付。它与
`P0_1_DRIVER_20261013/combination_manifest.json` 组成同一份 P0 静态组合，
不构成 RTL 捕获许可，也不声明 T052 完成。

## 结论

- `checker.py` 在读取观察轨迹之前，先由固定输入计划和冻结
  `publication.py` 生成完整 128 沿义务：6 次接受、3 次发布、3 次取消、
  `open=0`。
- 当前 schema 的完整全零 ready/valid 反例以
  `SOURCE_CALENDAR_PINS:0`、exit 1 拒收，不会降级成 UNKNOWN。
- 当前 schema 的完整伪来源 SHA 反例以 `SOURCE_META:controls`、exit 1
  拒收。
- M2 `RAW_EVIDENCE.zip` 中两份原始反例按原字节读取、不转换 schema；
  它们因旧 META 缺少完整时间／来源字段而以 `SOURCE_META:controls`
  拒收。这只能证明旧来源不兼容，功能缺口闭合由上一条的新 schema
  等价完整反例证明。
- fixture 只允许 `HANDWRITTEN_SOFTWARE_FIXTURE`，结果固定
  `RTL_verified=false`。actual 模式必须同时绑定外部 manifest SHA、实际
  run receipt SHA、approval SHA、源和工具前后身份、快照、命令、日志和
  四轨迹 artifact SHA。

## 实际执行

```powershell
C:/Users/songdongkuan/miniconda3/python.exe `
  -I -S -B -X utf8 `
  code/software/t052_publication_acceptance_candidate_20261012/rtl_capture_precheck_20261012/successor_20261013/run_checks.py `
  --output code/output/m3_t052_p0_2_20261013_04
```

当前整合终验结果为 `T052_P0_2_SOFTWARE_PASS`、exit 0、耗时 0.453 秒；24 项单测、
正常软件轨迹和两份当前 schema 完整反例均符合预期。总预算 300 秒、
单步预算 90 秒。第一次 `_01` 运行因 runner 对全零反例的预期索引写成
2、实际诊断为 0 而失败，原失败收据保留；子智能体修正后生成 `_02`。
主代理随后只补每步失败收据、输入漂移和最终预算拒收：沙箱内 `_03`
因临时目录权限失败并保留原日志，同源码在普通本机环境运行 `_04` 通过。
本目录的 `SOFTWARE_RECEIPT.json` 保留子智能体 `_02` 的历史状态，当前整合
结论以 `_04/receipt.json` 和组合交接为准，不回填旧收据。

工具绝对路径来自拟议组合 manifest，仅在软件运行时核其字节／SHA，
本轮没有启动 `iverilog`、`vvp` 或其他 HDL/EDA 工具，也没有安装工具。

## 未验证边界

- 没有真实 RTL capture 或实际 run receipt；P1-2 仍待 M2 精确许可。
- 没有执行旧数学、声音 RTL、Gowin、布局布线、时序或设备操作。
- 旧 4207 长窗口完整性仍为 UNKNOWN；T052 保持 PARTIAL。
