# M2两批原件限定复核证据（2026-10-17）

输入仅ad2de2169230dc8fd9f4b6f8157d384306c2479a和8b9d11e5368b6db45a1d3090d45f9e4f754132f2。新414e1a9/5aa4959不在签收范围。

ARCHIVE_VERIFICATION是原件CRC/大小/SHA及Git闭包；INITIAL保留原始CRLF与Git LF直接比较的差异，后续精确重构已解释。D3_COUNTEREXAMPLE为静态反例，CLI未执行。

VERIFY_ARCHIVES_SOURCE.py.txt保存实际核验方法源码原文；原执行路径是code/output/m2_m3_limited_review_20261017/verify_archives.py，根目录相对该原位置计算。它不是此处可直接运行的入口；如需复现应使用独占输出并核ROOT，不覆盖这些原件。

仅文件核验及已有日志/控制流审阅，没有新RTL/EDA/硬件执行。C/C2、D/D2 L1，E1/E2/E3隔离L2、E4短窗L3/尾段L2按原范围接受；D3待返修，board_release_allowed=false。原始总ZIP本体已在两次输入提交中，无需重复提交。见code/docs/M2_M3_Pro离线两批交付限定复核_2026-10-17.md。
