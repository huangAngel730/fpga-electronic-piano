# 四包实际派发与单写者边界

日期：2026-10-15。总控工作区：`E:\FPGA\GAOYUNFPGA\team\fpga-electronic-piano`。
派发前实际HEAD与fetch后的origin/develop同为 `874c097d34140b120d52eaadd9748dd6ae8d5894`。

依据完整读取的《M3_四项并行主责授权_2026-10-15.md》《M3_R05真实链限定复核与隔离接入任务单_2026-10-15.md》及用户指定两个实现窗口的直接指令执行，不创建新T/V/D编号。

R05精确原件：`code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1TD_R05_XSAFE_ModelSim输入_20261015.zip`，实核SHA-256 `dcf15f5d3ded1a0b160f55eab43066c728f80b3c329c44ea9f099c63f178696a`。

## 分工

| 工作包 | 唯一实现窗口 | 写集／排程 |
|---|---|---|
| A R05真链与隔离接入 | 主对话2 | `code/software/m3_r05_functional_integration_20261015/`、`code/tb/board/m3_r05_functional_integration_20261015/`、`code/docs/test/m3_r05_functional_integration_20261015/`（排除coordinator/）；基础优先 |
| C 48k PCM/I2S／数字延迟独立证据 | 主对话2及其独占子任务 | `code/software/m3_40mhz_pcm_i2s_latency_20261015/`、`code/tb/audio_out/m3_40mhz_pcm_i2s_latency_20261015/`、`code/docs/test/m3_40mhz_pcm_i2s_latency_20261015/`；先独立夹具，后接A实际capture |
| B 40MHz真实音频端点／定向物理后继 | 主对话4 | 上轮软件／文档任务目录的`successor_R03/`子目录；物理输出只用全新`code/output/m3_m2td_endpoint_probe_20261015_*/`。上轮72561ce原件不覆盖 |
| D 双滑块最小隔离候选 | 主对话4及其独占子任务 | `code/rtl/input/m3_dual_slider_138k_candidate_20261015/`、`code/tb/input/visualizer/m3_dual_slider_138k_candidate_20261015/`、`code/docs/test/m3_dual_slider_138k_candidate_20261015/`；准备并行，正式验收在基础后 |
| 共同整合／交付／Git发布 | 本总控 | 本coordinator目录；不代改实现窗口文件，问题退回单一所有者 |

主对话3（T052）、主对话5（原R04）本轮不联系、不调度、不写其目录；用户若直接为它们安排任务，不由本总控改写。用户本轮明确将新任务指定给2、4，因此A优先在2推进，不向5追加任务。

## 通信与自审

已通过项目对话工具分别向主对话2、4各发送一次完整派发。发送成功仅证明消息送达，不把收到消息或计划写成已运行。开工边界／必要阻断／完整交付才回报，常规细节落在各自README及原始收据；不例行互相发消息。各实现窗口可用自己的子智能体，必须划独占文件或只读自审；不启审核员／预审员流程。

各窗口不得Git写入，由总控检查并发修改、统一门禁和普通发布。M2真人的复核／共享状态更新由用户转发交接，不冒称已经通知。

## 实际执行与止损

- A：仅在ModelSim10.7身份与精确R05输入核同、不可覆写预检／一次消费／独占输出／进程树限时齐套后，允许一次真链vlib/vlog/vsim；每工具≤300秒，总≤900秒，首失败停。工具缺失则BLOCKED_TOOL，交软件成果，不以合成日志代真实运行。
- B：仅在相同Gowin V1.9.11.03 Education、完整同版_06输入和实际对象齐套后，允许新隔离副本一轮≤1800秒定向物理核查。工具／输入／对象不足即PENDING，不猜路径、不盲试、不改旧LOC或放宽约束。
- C／D：仅新隔离候选的有界软件／模块仿真，保留原始失败和正负例。不重跑已签旧组，不恢复旧消费许可。
- 四包都不改正式顶层、公共接口、正式CST/SDC、M1黄金或原封存。正式共享树变更按流程，码流、Flash、设备与未知电气不在本轮自动授权内。
- 原始命令／双流／退出、实际输入工具输出SHA、源前后身份、验证等级和未验项为交付条件。缺公开轨迹的deadline记UNKNOWN；数字延迟不是模拟端到端≤10ms实测；D下落命中闪光已知FAIL仍暂缓。

总控最后逐包核对，不将四份局部PASS拼成正式整机或实物通过。整体未闭合时保持PARTIAL及`board_release_allowed=false`。
