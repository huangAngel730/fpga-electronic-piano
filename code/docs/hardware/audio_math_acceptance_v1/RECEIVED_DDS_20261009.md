# 原封存包接收与真实 DDS 局部回放

2026-10-09，M3，D043/D044 新路径；基于本地 develop `ae06b5b` 后的未提交改动。
这是新增离线 Python 验收代码及局部参考比较，不是完整 A1/A2/T060 通过。
等级：Python 语法／组件执行 L1，已有 capture 的 DDS 部分提供局部 L3 比较证据，
但观察计数口径尚待 M2 复核；没有新 RTL 仿真、Gowin、STA 或实物结论。

## 原输入已收到

只读目录：`E:/FPGA/GAOYUNFPGA/CallBack/M1_138K40_audio_V0208_M2复核反馈_20261009`。
383 个文件、181,945,277 bytes；运行前后全部文件 SHA 清单一致。
此前 DELIVERY/M2_INPUT_REQUEST 的“尚缺原包”是历史状态，本报告取代该缺件判断，不删除旧文档或失败输出。

原 Golden 两文件与仓库已登记 raw SHA 完全一致：

| 文件 | bytes | SHA-256 |
|---|---:|---|
| audio_observation.jsonl | 4,623,773 | d17cf87952ac0c663e681e0b47051e9412af4a2979fb509aaa5d7114d5b32cc5 |
| midi_pcm.capture | 1,046,126 | bd0035de464cb8c757c7e29a132073181e9e8179aa8303ab1ec110c6990042d6 |

收到原 32 JSONL＋14 F＋10 追加反例，没有拿合成例代替。
139 份 gzip/base64 原证据载体的 carrier/raw bytes/raw SHA 全部核对；不运行原 M1 checker。
45 份收到的冻结源码正文与任务 H40 清单一致；9 份只存在已列明的 ROM 路径／include 路径适配。
规范化只用于比较，原文件字节不写回；收据同时记录 raw SHA 和规范化正文 SHA。
7 ROM 均与 M2 原字节清单一致，另与仓库 H40 按 LF 比较一致；lfo ROM 的 CRLF 保留原样。
收到的 observer/TB 是原模板，**并非同次生成后的 capture2 TB/observer**，此来源边界仍保留。

## 同沿日志计数差异：不改数据，不默默放宽

第一轮原入口记录在 `code/output/m3_audio_math_received_20261009_01/`，
真实退出 1、诊断 `D_TICK_GROUPS`，保留不覆盖。
源码依据：`observer.sv.in` 第 12/13 行在一个 posedge 进程中阻塞递增
`observation_cycle`，第 33 行起各 lane 的另一 posedge 进程读取它；
F TB 第 99/100 行在单一 capture 进程递增自身 cycle 后打印。
因此同沿 STATE 可能打印递增前或后的计数，信号仍为 pre-NBA。

当前新 replay 显式按唯一 `(epoch, request_id)` 把四 lane tick STATE 绑定到 D 逻辑沿，
只分类 `D.cycle-STATE.cycle` 为 0 或 1，分别实际 950／1537 组。
默认严格运输比较仍要求 cycle 相同；负向 −1／2 均拒收。
RESET／REQUEST／COMMIT 不使用这一分类，仍逐条原序和 cycle 精确比较。
note_on STATE 也必须唯一绑定 N 的 lane／同沿旧或新计数，并匹配 E 接受事件身份。
无原 capture 重排、过滤、字段改写或数学容差，没有拿 F/D 观测输出回填 expected。
该观察解释交 M2 复核，**a1_complete 仍 false**，不自行升级观察合同。

## 独立数学已接通的边界

由 E 接受事件（不是 U/P 排队事件）恢复 note/source/channel/velocity/generation，
独立计算 note FCW；从控制历史恢复 S；C 仅对 occupied lane 推进自己的 LFO。
PitchMod 使用冻结三 ROM、位宽、算术移位、floor、四舍五入及饱和规则独立计算 F/D。
DDS 独立维护 phase、480/960/1440 亮度窗、pending table、phasewrap。
逐 STATE 先比 pre-NBA，再推进 note_on/tick，覆盖末条记录。

真实正例的比较规模：

- 4 次复位、2,488 请求、2,487 提交，1 个请求在复位时取消。
- 68 接受事件、14 note_on、8,268 occupied LFO launches。
- Q 基准及 S 控制各 9,952 lane 比较；F 最终调制 FCW 9,948 lane 比较。
- 9,964 条 STATE 的 FCW／phase／table 各逐条精确一致。
- H 输出 table 9,948 lane 比较；2,487 事务的阶段间隔精确为
  Q→S 5、S→C 0、C→F 8、F→D 1、D→H 6、H→M 1 cycle。

Q occupancy、N 分配到哪个 lane 是当前 DDS 边界的观测输入，不声称已独立证明
allocator 选择／release／CC64。note_on 与 tick 同沿的组件模型已有合成测试，
但本原 capture 没有这种组合，整条真实路径不能外推为该组合也已覆盖。

## 原反例与自身漏检处理

中间结果保存在 `code/output/m3_audio_math_received_dds_20261009_01/`：
正例局部数学通过，52 拒收、4 未拒收，完整 runner 退出 3。
其中 `wrong_clip.capture` 实际改的是 M.fixture_select 的 0→1，不是 PCM 幅度。
新候选当时只检查 0/1 范围，存在来源身份漏检；只修了本新候选，未改 M1/生产文件。

原 TB 在 sample_edge→accepted_only 段有未记录的 fixture_select 切换。
当前仅在该段外能由冻结刺激顺序证明为 0 的范围核对实际标志；段内明确不可观测，
不从相邻输出猜值。该范围内的 wrong_clip 现在由 `M_FIXTURE_KNOWN_ZERO` 拒收。
`END_wrong_nonzero_count` 的名字与内容不符，实际改 END.total，按真实内容指定诊断。
每个反例记录实际 changed fields/tokens／首处原新差异／SHA、子进程命令及原日志。
导入／超时／缺文件错误不计作反例拒收；新增自洽 F/D/STATE 错 FCW 的合成链
即使运输一致，也由独立 E/control 算术拒收。

最终运行 `code/output/m3_audio_math_received_dds_20261009_02/receipt.json`：
236.172 秒，整体退出 3、`PARTIAL_REAL_DDS_A1_NOT_SIGNED`。
32 项组件 unittest PASS，55 个合成错误输入按指定诊断拒收；原包子进程正例退出 0、
状态仅 PARTIAL，56 个原反例为 53 个指定诊断退出 1、3 个 envelope 反例退出 0 未拒收。
2,485 个 M.fixture_select 可证明为 0，2 个处于未观测切换区段。
九项仓库门禁实际全 PASS、退出 0；源码和原包运行前后 SHA 未变。
源 SHA 和原日志索引见本目录交接与证据清单；
剩余三个 envelope／ADSR level 反例是 A2 未覆盖，**不能宣称 56/56 或完整黄金通过**。

## 后续及禁止事项

下一步 A2：冻结 ADSR 内部状态和定点流水、真实波表同步读、velocity gain、
混音舍入／饱和到 PCM 逐条独立重算，首先闭合三个原 envelope 反例。
五个 END 计数和 fixture 段内切换无足够观测，仍列准确缺口，不伪造完整计数。
T061 尚未开始，不把 Python DDS 比较当作新声部 engine 实现。
M2 可先复核上述观察计数解释和源身份边界，M3 在现有范围内继续 A2 不依赖改生产合同。

本轮未提交／未推送，未改共享状态／看板／登记，统一结论仍由 M2 复核。
未改原 capture、M1 文件、生产算法／RTL／ROM、公共接口、工程或约束；
无安装、串口、烧录、接线或设备动作，旧证据全部保留。
