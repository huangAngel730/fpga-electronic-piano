# 最终同步文件树门禁

2026-10-07，develop基线 fd2b414eede5767f3c7e487c4355a4fb073a5547。
命令：python -B -X utf8 code/scripts/run_m3_score_transfer_acceptance.py --repo-gate-only。
实际目录code/tb/input/score_transfer_candidate/runs/run_f2bbq1wn。

结果PASS：3873个输入逐字节复制/核验，原check_repo.ps1实际exit0，130.859秒，九门禁全PASS：
必需路径、Git空白、禁止提交产物、Python语法、官方引脚一致性、DOCX结构、
T007顶层仿真、T019公共包仿真、参考摘要标注。隔离副本内跑，原正式工程没有新增运行产物。
候选执行源与完整专项source_manifest的12份SHA仍一致，远端新提交未改原UART或候选。
该次仅仓库门禁，不新增T057功能/硬件验收；功能PASS以run_j_v22g6p为准。

门禁输入摘要文件gate_sources.json SHA256：
8e0fb14454cb7adad1153ca86687f5f468287c97fc748fa3d3244b2c3c1ac083
完整输入表保留在上述唯一运行目录；收据、原始stdout/stderr的可恢复版本见
evidence/run_f2bbq1wn/，raw_manifest记录原字节长度及SHA。其收据SHA256：
f0f6ef707971b726e4bcf697957a1d4c352ac96a41a2b4d081bd2262fd8be2be

门禁后只新增本说明及其3份日志Base64/清单，未再改变代码或已核验交付资料；
提交前另核对Git暂存空白、范围、原字节SHA及远端状态。证据本身不启动任何FPGA工具。
共享编号/看板/当前状态由M2统一复核登记，M3不代改。未编程、未真实硬件传输。
