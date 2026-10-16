# 夜间任务2 A恢复批次：PARTIAL / 三组功能额度耗尽

本轮正常提升审批已放行，固定ModelSim SE-64 2020.4及原EXE/已知静态依赖SHA不变。旧封包、已暂存文件、R05算法/ROM/时钟/正式top/约束均保持只读。本窗口无Git写、无实物。

## 实际结果

- RUN01：源码快照Windows长路径准备失败，无任何ModelSim进程、无功能消费。原异常被旧恢复runner误覆盖的缺口如实保留；新诊断在独立目录复现，之后用平面快照映射避免路径超长，且保留原异常。
- RUN02（功能组1）：vlib通过、vlog观察信号声明顺序FAIL，vsim未启动。新FIX01只前移config观察线声明。
- RUN03（功能组2）：vlib/vlog通过，vsim在12.5ns聚合公开未知值拒收，未进入业务采集；不能据此声称具体字段或算法问题。
- RUN04（功能组3，最后组）：总控接受分段startup合同后，vlib/vlog通过、vsim在1587500ps以`R05_STARTUP_OVER_64_EDGES`拒收。**两份真实startup原件各64连续沿，音频`clipped`在每沿均为Z，其余音频公开字段已知；主capture为0个TICK。** 未生成STARTUP_BOUNDARY/READY，无成功业务capture。

每组固定argv/cwd、独占源本体/原始双流、退出码、耗时、EXE/静态依赖、source before-after及一次消费标记见对应RUN_RECEIPT。工具/源身份未变；平面快照map为`source_snapshot_files`，每个repository-relative key绑定真实snapshot路径/大小/SHA。动态加载完整闭包未额外测量，不冒称已证。

当前功能消费3/3、剩余0，**没有追加第4组**。准备失败编号RUN01不当作功能消费。实际命令均为本目录软件恢复runner；监督保持原Windows Job suspended-start、NUL stdin、原始双流，单工具≤300s、组≤900s；日志中的fatal虽可能伴进程exit0，也被原判据拒收。

## 根因边界与静态建议

原首沿“复位初始化”只是假设，后续逐字段原件纠正为持续观察线Z。新board在generate内将frame-core公开`committed_clip`接到`night_committed_clip`，但该wire在generate结束后才于外层声明，符合早期generate局部隐式net与外部未驱动同名wire分离。无需读取内部寄存器即可看到源码连接风险及原始端口Z事实。最小建议为把新增观察线明确声明在generate首次使用前；不改算法、输出数值或强制内部状态。

收到总控最后“只读、不实施新修复”消息之前，已经生成`FIX_03_PENDING`及diff，只有声明前移；未运行/未编译，仅L0静态候选，**不能写修复通过**。新限制到达后无继续改源/启动，原件保留并如实交接。

## 交付与未验项

- 总回执：`NIGHT_RUN_RECEIPT.json`；原始失败prefix及逐字段统计：`FAILED_PREFIX_INSPECTION.json`；阻断标记：`CAPTURE_BLOCKED.json`。
- 真实失败原件：`RUN_04/stage/inputs/STARTUP_CAPTURE.jsonl`、`STARTUP_INPUTS.jsonl`、`REAL_CAPTURE.jsonl`、`REAL_INPUTS.jsonl`。前两者是失败诊断原件，后两者无业务TICK，不得供C签成功真链。
- 新隔离合同/精确schema已固定并保留，供后续获新许可后使用；不能把分段或C的软件guard通过签作真实A通过。
- 等级：FIX02实际编译通过L1；真实仿真执行但FAIL，不签L2；后验原始prefix解析只作软件诊断；FIX03_PENDING仅L0。逐请求期限、PCM→串行逐样本、真实输入数字延迟均UNKNOWN；first-valid未公开，模拟≤10ms/PLL/HDMI/新物理STA/实物均未验，board_release_allowed=false。

最终封包及SHA在`SEAL_RESUME_FAILURE/SEAL_RECEIPT.json`。未提交、未推送；夜间总控统一发布，M2最终限定复核。总控直通信授权已有效，消息发送不等于对方处理；真人交接仍待用户转发，尚未送达。
