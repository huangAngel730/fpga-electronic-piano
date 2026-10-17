# 夜间任务5 task-day：到件身份审计完成，真实 Pro 同版仍待件

本次限定身份审计完成（L0 静态事实 + L1 Python 审计自检），状态 `DONE_INTAKE_AUDIT__PENDING_PRO_SOURCE_OR_TRACE`。没有新增 RTL 仿真、EDA、完整时序或板测结论。B1/B2 真实 Pro 链与 E2/E3 正式接入仍 PENDING/PARTIAL，`board_release_allowed=false`。

机器入口为 `INTAKE.json`、`SOURCE_LOCATIONS.json`、`SUPPLEMENT_SOURCE_LOCATIONS.json` 和 `MISSING_ITEMS.json`。对 52 项文件现场取原始字节 SHA，89 个收据指向的文件身份 MATCH，7 个已交封包 CRC PASS，59 份原件副本逐字节核同。9 项自检包含真身份、错 SHA、错大小、缺文件拒收、旧/隔离文件不准入、原件副本、CRC、收据冲突与审计前后稳定性，全部通过。

执行命令（仓库根 cwd）：`C:/Users/songdongkuan/miniconda3/python.exe -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017/run_audit.py`。子命令/机器/Python版本与EXE SHA、PID、源前后SHA、UTC、原始双流和退出码见 `ROUND_01/LAUNCH.json` 与 `RECEIPT.json`；audit 子进程退出0、无超时、0.781秒。只消费本窗口1/2轮，夜间任务2的4轮份额不动；旧包次数全部只读。成功后不再运行功能审计；封存仅复制、哈希与ZIP元数据核验。

## 到件与边界

| 输入 | 实际可见 | 不能推导的结论 |
| --- | --- | --- |
| C/C2 | toy 独立输入/日历、19帧、四lane、取消/背压/epoch；旧M1参考和ROM已发布且可读 | 最低空闲slot、lane=slot、NoteOff立即释放不代表真实Pro Release/分配；旧M1不是缺发布，而是缺Pro同版适配 |
| D/D3 | 诊断PCM/串行、来源拒收入口及原件 | C/D按epoch内序号对应，非同次真实执行时间轴、非音符→PCM算法 |
| 上午被动monitor | 5062沿正常CSV、公开29列、3正22负自测和原封包 | 人工端口刺激，不是新Pro DUT；BCLK/WS/DIN留原值但该monitor未串行解码 |
| M2新Pro五个授权目录 | 本机指定目录全部不存在 | 不代表其它机器未开发；只说明本轮没收到精确source/ROM/top/trace绑定 |
| M1 Pro successor两个目录 | 本机指定目录不存在 | 旧R05/R06模型已可用；不可把旧参考重命名为Pro黄金 |
| `code/rtl/138K_Pro` | 顶层仅两个官方原理图PDF与引脚参考CST | 原理图/引脚候选不构成音频源、工程source list、ROM或真实公开捕获 |
| E2 | 历史5849采纳原文、隔离桥/固定左波形源码、3/6成功停止及封包 | 历史/回放数据不是新Pro PCM，不升级完整raster/TMDS/CDC/STA/实屏 |
| E3 | 真实300B MIDI、352B/44记录、隔离UART→RAM源码和完整原件；6/6耗尽 | 存储READ不代表播放/声音；50ms测试不签默认5s或实体UART |

审计范围为 task-day 原件、任务指定目录和明确引用的本机仓库文件；没有读取其它项目/成员机器、没有声称远端此刻出现新Pro交付。开工及审计 HEAD 和本机 origin/develop 均 `414e1a9d3ee0617c5e8ba72dd4b22c36122c9926`；fetch由总控执行，本窗口未fetch/改Git。

## 两个关键合同的源码位置

1. PCM：旧 `i2s_tx.sv:194–195` 给出 `frame_start/frame_tick`，`:327–329` 在 `frame_start && valid` 装载采样值；旧正式top `:614–621` 的valid常1，输入是buffered左右PCM。候选 `pcm_frame_observer.sv:23–28` 在同一frame_load沿采pre-NBA PCM并增加独立adoption ordinal；E2 wrapper `:26–30` 接旧bridge，bridge `:43–48` 接observer。这里可核旧合同，尚无新Pro公开端口映射及同执行trace，不能把sample_tick、预测帧或未来NBA值当实际采纳。
2. UART：冻结协议 `code/docs/hardware/score_transfer_v1/PROTOCOL.md:30` 是默认5秒；E3 successor `:7–10` 给出40MHz/115200、FRAME_TIMEOUT=800000和SESSION_TIMEOUT=200000000，`:170–175` 为执行点。E3 TB `:3、14` 明确改为2000000拍=50ms隔离配置。正式Pro UART球位/Bank/复位、行为RAM或BRAM版本、默认5秒新验证均待M2确认，不消费旧E3额度。

E2历史PCM SHA `23e823c46638f87574616c9ab1de70c594acbd595188783d2e3b54ade0bdcfe4`；真实MIDI SHA `c0a8cb9f1ba3496a00367786a2b4ee5e0580be7b4bfbf0891b75e3b7475f634c`；records SHA `fc5f4a54f6662dfb5f164608fa09c481941ab17fba20d18ff4bab53eb4793b78`。这些本体均随新审计封包的 INPUT_ORIGINALS 保存，旧封包也按原字节保存，没有仅交SHA代替本体。

## 自审、止损与接手

主窗口自审与只读子智能体核E2/E3合同和审计脚本，执行前补齐真实MIDI/records、E2 PACKAGE_STATUS的ZIP/manifest身份及收据冲突拒收；运行后检查9项PASS、89个MATCH及七目录缺件。没有重跑既有C/D/monitor/E2/E3专项或复制它们实现。发现过的只读检索路径错误（不存在code/sim、错把software的D/ingest/README定位到docs/test、rg的Windows通配路径未展开）均改为已存在明确路径，没有功能轮失败或权限消费。

交总控：供夜间任务2/3只读引用身份清单；总控统一汇合、门禁与发布，本窗口未暂存/提交/推送、未改共享状态。只向已获用户授权的夜间任务1回传一次结果，AI收到不等于真人M2签收。M2需交新Pro source list/目标/top/ROM及公开端口映射和同执行trace；M1交同源黄金适配；M3随后在新有效许可内接B1/B2。E2/E3按正式优先级后续准入。真人M2最终限定复核和状态登记：待用户转发，尚未送达。

当前限定任务无剩余必做项，缺真实Pro输入不能由本窗口消除，提前收工；不为耗满4小时等待或恢复旧工具额度。
