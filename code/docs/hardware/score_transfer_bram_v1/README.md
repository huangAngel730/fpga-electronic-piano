# 独立曲谱 RAM 候选入口

2026-10-10 主对话4新结构已通过**独立模块40MHz物理STA（L5）**：
25ns、Setup1ns/Hold650ps保护，Setup+7.654ns/Hold+0.001ns，TNS/违例0。
当前交付见[CACHE_REVISION_DELIVERY_20261010.md](CACHE_REVISION_DELIVERY_20261010.md)，
新授权/旧05主动终止说明见[CACHE_REVISION_AUTHORITY_20261010.md](CACHE_REVISION_AUTHORITY_20261010.md)。
这是同步请求缓存/内部流水及实际Hold端点修复后的新源，不是旧04/05的时序结果。
正式整机STA/真实I/O/设备均未放行。用户现已明确要求上传GitHub，
本次仅发布RAM授权范围，发布边界及原始收据身份见
[CACHE_PUBLICATION_20261010.md](CACHE_PUBLICATION_20261010.md)。

以下为旧CRC分拍修版的历史入口，原报告与证据不回填：

旧CRC分拍修版的说明见[TIMING_DELIVERY_20261010.md](TIMING_DELIVERY_20261010.md)，
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
