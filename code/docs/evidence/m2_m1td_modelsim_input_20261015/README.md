# R02：M1真实音色+立体声延迟新板级组合的 ModelSim 输入交接

2026-10-15；本目录只交 **L0静态闭包与可逆副本**，实际ModelSim未运行。

- 自包含 ZIP `M2_138K_M1双音色延迟_ModelSim自包含输入_20261015.zip` 273614 bytes，SHA-256 `9af00c82d6b7a7a0a74bd195c823fc117ece1db0ba67fc2eb620b10c09b619f7`。内容按内部 `MANIFEST.json` 核 91成员、69项仿真文件表和40处路径映射。旧R01中名义/生产 TMDS_PLL 同名；R02只从 `compile.f` 排除生产视频IP，文件仍原字节保留在包内。
- `verify_portable_inverse.py` 只读：在 M1 独立机器运行 `python -B -X utf8 verify_portable_inverse.py`，核 ZIP CRC/源闭包/ROM/include/无重复模块；M2 可附 `--original-stage code/output/m2_m1td_whole_prepare_20261015_05` 额外将40路径恢复，与原84输入字节逐项比对。两种模式在 M2 工作树已实测退出0。`INDEPENDENT_REVERSIBILITY_RECEIPT.json` 是M2本地独立逆向结果的仓库LF换行副本（原忽略目录收据字节未改），不冒称新仿真；此副本SHA按本目录`MANIFEST.json`核。
- M1 只在本包核源/工具/命令且有实际运行授权时解压运行 ModelSim，按包内README及原封存算法差异判断；`vlog/vsim` exit 0 之外还要核 FATAL/指定PASS、真实输入/工具前后SHA与原输出。原失败Icarus `.vvp` 不得用。工具入口单项≤300秒/整体≤900秒仅为**拟议边界**，未替代本机实际审批。
- 新组合当前只静态接线与端口替身 L2；真实M1音色/效果的板级函数、BSRAM推断、新STA和实物均未签收。旧T056 L5/.fs不转移。原真实M1编译90秒超时且伴随分配器Icarus类型断言记录V0329，不回填成功。

本目录文件准备好但本次发布状态以实际Git结果为准；沟通消息见同目录的 `M2_HANDOFF_FOR_M1.md`；通知 M1 须经用户转发，当前尚未送达。