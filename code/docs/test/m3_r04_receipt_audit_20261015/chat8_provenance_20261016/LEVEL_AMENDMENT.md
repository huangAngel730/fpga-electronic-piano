# RUN_02 验证等级措辞更正

日期：2026-10-16。

原 `RUN_02/PROVENANCE_RESULT.json` 的 `level` 写为 `L0_STATIC_IDENTITY_PLUS_L1_SOFTWARE_READ_ONLY_AUDIT`。按仓库《测试验收标准》，L1 要求 HDL lint／编译；本轮只执行 Python 软件核验，没有执行 HDL lint 或编译，因此原 L1 表述无效。

正确口径为：**L0 静态身份＋软件核验（6 例通过），未执行 HDL L1**。

为保存原始执行证据，本次不覆写也不重跑：

- `RUN_02/PROVENANCE_RESULT.json`：SHA-256 `ad45d1b1bb6e3b58f0a296dd15d3a1cbe2bd6cc254568f9692c76e58b6d88e27`；
- `RUN_02/RUN_RECEIPT.json`：SHA-256 `cfec99220f1081ac33751b4735cc9166c393ca94b3a05db04be485f4647be53d`。

这次只修订当前交接文档、顶层当前结果副本和工具未来输出口径。原核账的 PASS、六流、SHA、253456 沿、A→C 精确绑定、证据边界和 `board_release_allowed=false` 均不变。
