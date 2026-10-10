# 独立曲谱 RAM 候选入口

当前源的时序修复说明见[TIMING_DELIVERY_20261010.md](TIMING_DELIVERY_20261010.md)，
用户追加权限见[TIMING_AUTHORITY_20261010.md](TIMING_AUTHORITY_20261010.md)。
最终实际时序、工具原报告、仿真和复核数据随新TIMING_EVIDENCE封存；不要仅看综合Fmax。
本修版实际终态为INCOMPLETE_PHYSICAL_STA：仿真与综合通过，但04布线1800秒限时未完成，
无最终物理STA；不能宣称40MHz已通过。进度采样证明CPU活动，不证明收敛。
新证据校验：`python -B timing_package.py verify`（在本目录，纯离线，无设备操作）。

DELIVERY_20261010、IMPLEMENTATION_20261010、M2_HANDOFF_20261010、EVIDENCE_20261010
是27e1fb2的历史交付，原综合估算时序失败；package.py/review.py也只针对该历史原件，
不能对当前修版直接执行其seal/review模式。旧证据不删除、不回填成新结果。
新timing_build.py先要求当前精确仿真PASS，再执行有界独立综合/PnR。

此候选不属于生产顶层；虚拟I/O的独立40MHz时序不等于整机STA或板级许可。
所有.fs只在隔离code/output保存，禁止下载/烧录，不打入转发包。
正式接入、真实I/O/CDC与新整机STA、共享状态/编号由M2负责。
