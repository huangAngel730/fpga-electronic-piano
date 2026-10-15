# 40 MHz 音频 STA 端点准备：本轮分工

日期：2026-10-15。实际工作区：`E:\FPGA\GAOYUNFPGA\team\fpga-electronic-piano`。

用户直接指定复用主对话2、主对话4，不新建多余窗口；主对话3（T052）与主对话5（R04）不在本轮调度内，不向其发送消息。本轮仅实现窗口与其子智能体自审，不启动审核员／预审员流程。M2 最终复核职责不变。

## 输入身份

- 开工 HEAD：`39b2ab2eef49e47f7816dd86b4f1901f96aea3ca`。
- 开工实际 fetch 后 `origin/develop`：`e2200b2571afe3c38807a2d8ee2e4264c5881fd8`；只 fetch，未合并工作文件。
- 最新任务单：上述远端提交中的 `code/docs/M3_并行接管M2_40MHz音频STA端点准备_2026-10-15.md`。
- 用户转交任务单：`E:\FPGA\GAOYUNFPGA\Callback3\chat7\M3_并行接管M2_40MHz音频STA端点准备_2026-10-15.md`；SHA-256 `848aa3e1e892ae1625ff18c8d9ab2f5d4aaea589667331a13e1e3843c9e55831`。
- 原物理 ZIP：`code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1TD_整机PnR_STA_20261015.zip`；实际核对 SHA-256 `17e71ebd5b54743fd0214af5fbfdfd1a4cca4eddbcedab56f7b3df7b3ca521ff`。
- 本机任务单所指 `code/output/m2_m1td_whole_prepare_20261015_06/` 不存在；从上述原 ZIP 读取必要原件，不伪造输出目录或新工具运行。
- 用户本轮补充 FPGA 工具目录：`E:\FPGA\GAOYUNFPGA\138K\tools`。仅记录路径，未运行其中工具；真实定向 STA 仍需 M2 确认工具身份、命令与执行许可。

## 唯一写入所有者

| 窗口 | 工作 | 独占写集 |
|---|---|---|
| 主对话2 | 独立报告验收器、正例及坏报告、实际软件收据、自审 | `code/software/m3_m2td_audio_endpoint_audit_20261015/`，排除 `coordinator/` |
| 主对话4 | 真实网表／报告对象目录、来源片段、定向 STA 提案、自审 | `code/docs/test/m3_m2td_audio_endpoint_audit_20261015/`，排除 `coordinator/` |
| 本总控 | 两方接口适配、最终核对、综合交付与发布 | 上述两个目录中的 `coordinator/` 子目录 |

每个实现窗口自行细分其子智能体的只读／独占文件范围；任何时刻同一文件只允许一个 AI 修改。总控不代改两实现窗口的文件，发现问题退回唯一所有者。仅在开工、必要阻断及完整交付时通信，不进行互相例行汇报。

## 验收与禁区

交付应齐套：实际对象清单、仅文本的定向报告提案、独立软件验收器及四类以上负例、原始 stdout/stderr/命令/退出码与 SHA、限定结论。主对话4的机器清单最后由总控适配主对话2的 schema，不要求两窗口频繁协调。

不改 SDC/CST/LOC、旧报告／物理包／checker、R04 文件、正式 RTL、接口或共享编号／状态表。不运行 Gowin、PnR、真实 STA、ModelSim 或硬件操作。不把综合 `.vg` 误称布局后网表，不将软件解析或合成 fixture 通过升级为新 L5。

`board_release_allowed=false`。本包最多 L0/L1；真实定向 STA 的对象、命令、机器、工具、预算及输出目录待 M2 决定。M2 开工／状态登记以实际回执为准；发给 AI 窗口的消息不等于已通知真人 M2。
