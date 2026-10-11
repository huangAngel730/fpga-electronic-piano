# T060 最小补采代码：静态预检交付

2026-10-12，M3，交接 M2。对应 V0288 规格及最新统一回执。

## 当前结论和边界

薄 TB、只读 observer、独立源码日历 oracle、严格解析器及两组输入计划已实现。
当前只交 **L0 静态准备／L1 软件检查**，不声称新音频 RTL 的编译、仿真或数学验收通过。
本轮新音频 RTL 编译 0、捕获运行 0、综合／PnR／STA／设备操作 0。
发布所需仓库九门禁中的原有短 RTL 基础检查另列，不作为两组新捕获。

旧机器 scope、PARTIAL/exit3、unsupported 异常、原封存与失败记录均不改。
已签数学／路由与两计数的 REUSED 绑定沿 95e8bc2 的机器 scope；本轮不重放 capture2、
56 个旧反例、B2M 原 16 步数学或旧 12 自检。完整 T060/T061 均保持 PARTIAL。
按本次规格不写共享表，由 M2 复核后统一登记。

## 精确基线和依赖

唯一基线为原封存 **H_pll_core40_route2**，40 MHz／48 kHz；不换 L、N32 或新 RAM。
原 ZIP SHA：`cdc196fef2635c8fc5b245d88a157e742a492c7bed89cb3ca1ce50517476e994`。
内层输入清单 SHA：`6705f3c6a184d07aaa21477a83b7653a076cd9043c1417f89186f2619de232c9`。

portable 保留全部 56 份原输入及原清单，按原 candidate_SHA256 逐字节核验；
未来仿真只准备 19 份功能源（allocator 单独 lowering）、原 ROM 和 include。
业务源唯一适配是原绝对 ROM/include 根变为包内路径，逐文件差异见 generated_path_only.diff；
原件另存 original_H，不覆盖。

复用的 router_model.py、envelope_model.py、dds_model.py、strict_capture.py 原字节和
SHA 固定在 prepare.py；新软件的实际静态 import 闭包、全部运行源执行前后 SHA 见
run/receipt.json 和 portable/manifest.json。包内不需要 GitHub 或工作树模型。
新 checker 显式选择包内模块并检查实际 __file__，-I/-S 隔离执行。
本说明的更新不回填上一阶段 README 中当时“尚未完成”的历史状态。

## 生成来源和仿真口径

原 run_platform_audio_capture.py、tb_midi_pcm.sv、observer.sv.in 只读复制，未执行旧生成器。
generation_origins.json、thin_tb_vs_generation_origin.diff、observer_vs_generation_origin.diff
列出旧生成依据到新薄包装的全部差异，并保留原字节。

新包装实例化原 H 的 bank→gain→commit，不改生产端口或文件，不强制内部状态。
它在公开事件层注入一个 source1/channel0/A4、velocity900、零 Pitch/Mod 的槽；
不宣称覆盖 DIN/UART、任意事件、四槽并发或 N8/N32。
原 core 没有外部消费者背压端口，故 B 组仅在 TB 连接处同时屏蔽 bank.result_ready
和 commit.result_valid；enable=1 时恢复原链路连接。这是待 M2 预检的仿真夹具适配，
不是生产背压接口变更或已经验证的整机行为。

所有驱动在 negedge 生效；一个 posedge 过程独占 cycle/epoch、计数、日志写入，
只读 observer 在 NBA 前记录；未知 X/Z 不能形成合法 JSON，严格 checker 拒收。
输入文件由独立模型生成固定时刻，TB 不读 DUT phase 选择取消点。
观察 phase、FCW、ADSR、PCM 只做比较，不反填期望。

## 独立源日历和待采计划

source_calendar.json 按原源 SHA 绑定唯一行锚点。原 FSM 为
CAPTURE→四次控制读取→数学 launch→七个 age→消费→ADVANCE→四拍 settle→SNAPSHOT→
首次 HOLD→bank 握手→PCM 寄存→commit。首次 valid 与实际握手分开观察。
frame 同沿抑制 lane_tick，已执行的 DDS／ADSR／LFO 推进不回滚；取消数学 token 后排空。

A 组保持 833/833/834 拍节奏和 RELEASE_SAMPLES=4800。
先 NoteOff 自然释放到 Idle/release_done、真实退休清 occupied，再同身份新 generation 分配；
随后单独短段 CC64 down→接受 NoteOff deferred→真正握手接受 ALL_NOTES_OFF→实际 Release 衰减。
不缩短释放，不加速 tick，不用 reset/force 代退休，panic 作用域沿原 GLOBAL 源合同。

B 组四点由源码日历推导，以下只是**软件预测**，不是实际 RTL 命中证据：

| 点 | pre-NBA 周期 | 旧请求 | 软件预计阶段 | 预计恢复 commit |
|---|---:|---:|---|---:|
| 数学启动前 | 105 | 1 | SETTLE | 新 ID2，136 |
| ADVANCE 同沿 | 424 | 3 | ADVANCE，tick=0 | 新 ID4，455 |
| 已推进／SNAPSHOT 前 | 725 | 5 | SNAPSHOT，先前推进保留 | 新 ID6，756 |
| HOLD 背压 | 1033 | 7 | HOLD，valid/ID/数据已稳定四沿 | 新 ID8，1064 |

旧未提交结果不能在 frame 新接受；之前合法提交的 pending PCM 可以依法转 held 播放。
checker 核对完整边沿、严格 flag 类型/值、身份/运输、END 唯一及尾后无记录；
软件域以外事件拒收，不扫窗口，也不用 flag 选黄金。

## 已运行的软件检查

新 22 项软件自检包括 4800 tick 自然退休、panic 接受及衰减、四点取消、
非回滚、held 稳定、完整正/坏轨迹、严格类型/END/重复键、包外 import 拒收、
observer 字段/格式参数静态一致及 quiet-skip 与逐拍执行一致。
A 软件轨迹 24583 条 EDGE；B 软件轨迹 1595 条 EDGE。它们明确标注
SYNTHETIC_SOFTWARE_TEST，默认 RTL checker 会拒收该来源，不冒真实补采。

四份完整软件损坏轨迹保留正常 END：退休复用 generation 错、接受 panic 漏 off、
frame 旧结果接受、推进回滚，分别按指定身份／释放／旧 ID／数学诊断非零拒收。
包内 -I/-S 新进程重验 B 正例、四反例及合成来源拒收，原 stdout/stderr/退出码齐套。
新软件检查总上限 300 秒、单步 90 秒，真实时长及执行 SHA 以最终 run/receipt.json 为准。
另有封存依赖缺失、未重签篡改、重签坏依赖三项拒收检查，见 verification.json。

首轮静态打包因 DRAIN 锚点同时匹配 frame 和 default 两行而拒收；修为唯一含
resume_requested 的完整 frame 分支锚点。first_failure 保留当时原源、日志、收据和轨迹，
未改业务 RTL 或数学模型，不把首失败改为成功。

## 复现及下一步权限

在仓库中运行新增软件检查（全新目录，拒覆盖）：

```powershell
python -I -S -B -X utf8 code/software/audio_math_acceptance_candidate/t060_minclosure_20261011/run_preparation.py --output code/output/t060_precheck_new_run
```

封存包可独立解压；STATIC_PRECHECK.zip 内 run/portable 自带原 H 输入、软件闭包、
输入计划、来源差异、日历锚点。合成软件轨迹位于 run/software_fixtures。
不联网也可在外部目录执行包内 checker（路径按解压位置替换）：

```powershell
python -I -S -B -X utf8 run/portable/code/software/audio_math_acceptance_candidate/t060_minclosure_20261011/check_minclosure.py --capture run/software_fixtures/normal_B.jsonl.gz --plan run/portable/plan_B.json --software-fixture
```

future_commands_NOT_AUTHORIZED.json 仅为 M2 预检数据，不会由准备脚本执行。
两组各有隔离 future_group_A/B，TB 拒绝覆盖已有 capture。
未来建议 lowering/compile 各 90 秒、capture 各 300 秒、软件单步 90 秒／总 900 秒；
工具实际路径/版本/SHA、这些额度如何组合及原源适配需 M2 确认。
下一步仅申请 M2 静态预检，确认后再明确放行这两组实际 RTL 补采及对应四个完整坏 capture；
本交付不提供执行许可，不自动重试或提高超时，不自行综合/PnR。

交接状态：待用户转发 M2，尚未送达。无新的 M1 代码代做或通知事项。
