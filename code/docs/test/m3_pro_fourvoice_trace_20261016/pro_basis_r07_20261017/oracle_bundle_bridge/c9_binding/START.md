# 夜间任务4：R7-C C9 机械桥后继任务单

- 当前目标：依据已发布 C9 的 74 字段 schema、67 公开端口 exports、捕获合同和源闭包，新增独立、可调用的机械桥及待运行用例；保持旧 R7-C 桥、首失败和六个未运行用例原字节。
- 时间盒：优先在 2026-10-17 21:55 前交源码与简短 READY；本轮总时间盒不超过 22:55。
- 实际条件：仓库基线 `16ac226552f6fb65347b229b8fad42146ed45644`；C9 仅有 L0 静态源码、合同和 schema，没有真实 C9 trace、独立 input-plan 映射、真实 lane tick、`audio_stable` 策略或执行许可。
- 独立写集：仅本 `c9_binding` 在 `code/software/.../oracle_bundle_bridge/`、`code/tb/board/.../oracle_bundle_bridge/`、`code/docs/test/.../oracle_bundle_bridge/` 下的三个对应子目录。
- 工具额度：本窗口只做文本读取、JSON 解析、文件大小和 SHA-256 核对；R/S/C/T/H 额度均不增加、不消费。禁止导入或运行候选、功能测试、DSP 黄金、HDL、EDA、设备和子进程型执行器。
- 提前结束：源码、格式、实际输入绑定、独立正负例清单与 READY 的精确 SHA 齐套后结束；不等待真实 trace。
- 受阻转轨：若发布合同缺字段或身份不符，保留静态缺件并停在 `PENDING`；不修改 M1/M2 源、公共 helper、旧桥或共享状态。
- 次晨原件交接：由总控读取本目录 READY；明确 L0/NOT_RUN、旧新差额、真实输入和硬件未验项，不自签 REAL 或板级放行。
