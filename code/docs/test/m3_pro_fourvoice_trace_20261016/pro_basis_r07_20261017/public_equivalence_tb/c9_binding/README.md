# R7-B C9 静态后继

本批只完成 L0 源体、两路同输入装配框架和交接封存；实际编译、仿真、软件用例、B 等价比较均未执行。声明输入基线为 `16ac226552f6fb65347b229b8fad42146ed45644`，本窗口未执行 Git 同步、暂存、提交或推送。旧 B 的 166 件 FILE_SHA 原件逐件核同；旧 15+4 例结论只保留原版本范围。

## 实际装配

`SOURCE_BINDING.json` 绑定 182 件实际文件，均在 `SOURCE_STORE/`，不是只有路径清单。M2 C9 原 ZIP、decision、exports、schema、contract 在 `INPUT_ORIGINALS/`，原 ZIP SHA 为 `d458ab16277bd46751318ac368b22df1b21b35c4867c47942e7bff7d27fc3aa2`。86 件 decision payload 的大小和 SHA 已静态核同。

C9 的 audio_candidate、polyphonic_envelope_bank、polyphonic_event_router、timbre_delay_chain 四个 M1 模块与冻结原实现同名、字节不同。直接把旧 `dual.f` 与 C9 平铺会冲突；共用 C9 M1 又会改变原实现基线。本批保留两套独立编译/仿真空间，不改模块名、不改生产源。原路 72 个编译单元，C9 观察路 74 个编译单元（C9 基包 72 + 原 driver + 新 TB）；这两个数量不能相加后作为单个 closure 编译。

未来装配输出的 `original/`、`observer/` 分别作为 cwd，各使用本地 `compile.f`、顶层 `tb_c9_original` / `tb_c9_observer`。每路含完整头文件、9 ROM、两个裸 ROM 字节别名及原四份输入。M2 仍需批准精确工具、库隔离、argv、窗口和监督收尾，不把本清单当编译准入。

两路固定同一个 50 MHz 外部时钟、40 MHz 模型时钟计划及同 SHA 的 driver/bytes/reset/ready/plan。driver 的 event_ready 是输出，只接未使用线；event_valid/data 输入固定零，不回驱 DUT ready。固定 `key_n=11`，13 位公开输出映射见 TB。观察路 67 个公开 obs 口全部直接连接，没有读取 DUT 私有层级。

公开输出逐 40 MHz 沿在 PRE_NBA 采样，比较窗口默认 cycle 1200..12000000，time_ps=12500+(cycle-1)*25000；事件流用 postponed `$fstrobe`，保留窗口锚点和沿间变化。结束等待 1 ps 仅用于冲刷 postponed 写入，LANE_END 记录实际最后采样沿时间，不移动采样相位。这些是源码定义，尚未经 elaboration/仿真证实。

## 后继入口（只记录，当前不执行）

独立封存包 `C9_TWO_LANE_ASSEMBLY.zip` 解压后含本目录清单/源体、`tools/c9_pair.py`、`tools/selftest.py`、`tools/equivalence_frozen.py`。ZIP 身份见 `ASSEMBLY_ARCHIVE.json`，最终所有入口身份见 `READY.json`。SOURCE_STORE 也留给总控纳入 C9 补充 ZIP；本窗口不决定 Git 暂存范围。

未来获得精确授权后，使用 `c9_pair.py assemble --input SOURCE_BINDING.json --binding-sha <READY中的SHA> --output <不存在的新目录>`；它核每件大小/SHA并复制两路，绝不启动 HDL。CLI 正常准备结果也返回 3，不能据此签等价 PASS。

两次隔离捕获各留 trace/events/原始 stdout/监督 receipt。trace 列固定为 cycle,time_ps,rst_n,midi_rx,key_n,pins；events 列为 time_ps,pins。监督 receipt schema 为 `M3_R7B_C9_LANE_RECEIPT_V1`，必须绑定三份流 SHA、input_plan_sha256、source_binding_sha256、exit_code=0、normal_exit=true、timeout=false。正常 stdout 各仅一条对应 LANE_END。receipt 的真实性、工具/命令/资源/清理证据由 M2 监督原件证明，本适配器不能鉴真。

`JOIN_INPUT_TEMPLATE.json` 说明 future join JSON；它要求提供实际 input_plan/source_binding 文件并核 SHA，检查两路计划绑定。`c9_pair.py join --input <冻结JSON> --output <新目录>` 流式核两路 cycle/time/外部输入逐沿相同、行数完整及事件锚点，输出 combined.csv、combined_events.csv 和适配 marker。输出 marker 不是工具原 stdout，原两份输入和收据仍按 SHA 留存。引脚差异保留原值交既有 B，不由 join 抹平；两路缺行、时基/输入不一致或异常收尾直接拒绝，失败输出保留。

下一步仅复用 `INPUT_ORIGINALS/equivalence_frozen.py`（归档 tools 中同字节）的 `compare` 和 `compare_events`；默认窗口与本 TB 一致时也可用其旧 CLI `--csv combined.csv --stdout combined_stdout.txt --events combined_events.csv --output <新结果>`。比较器和 join 都不签生产者真实性或完整整机通过；join 固定 real_equivalence_pass=false。旧 run_once.py/dual.f 不适用于本次隔离架构，不能直接复用启动。

## C9 语义及 A 依赖

B 另留 19 字段二进制诊断原行，含 kind/mask/router seq/valid、config_take/payload 和 upstream/effect/feedback 三个独立 clip；X/Z 保留原 bit-string，解析未知为 null 并记原因。kind1/2 同 seq 多阶段逐行保留；kind3/4/8 的零 data/seq、valid0 是无来源哨兵；kind0 空闲持有值不当输入事件。config_payload 只在 take=1 且已知时解释，拼接为 1+16+15+15+15。advance_frame_req_id 是请求 tag，四 lane 推进取真实 advance_mask/lane_tick，不能当 FRAME F。

`companions` 入口是有界批量诊断（输入最多 64 MiB）；不能用它处理默认全窗的巨大 companion 文件，也不能据此宣称流式全窗采样就绪。全窗伴随流处理、输出磁盘/资源预算和执行窗口都待 M2 精确冻结。公开引脚 trace/events 的 join 已写成流式实现，但当前没有运行验证。

唯一 canonical 74 字段采样仍归 A。`A_DEPENDENCY.json` 和 `INPUT_ORIGINALS/A_DEPENDENCY/` 保留 A 新公开观察器/TB/codec/映射/源包的实际静态字节，来源为 A 的 c9_binding，不用 B 的 19 字段诊断替代。A 的实际窗口、独立 RESET_EDGES、端到端集成尚待冻结；其 64 MiB codec 限制按 A 原文保留。没有生成第二个 FRAME 生产者。

独立 input-plan→接受映射、apply_event_seq、audio_stable 仍为 null/PENDING；router seq 只作 epoch 内路由序号，回绕不能当全局键。M1“note_on 前一沿”文字勘误不作为固定延迟期望；不填 accept+1、不补零、不按 seq 去重。无真实 trace、数学/PCM/I2S 及硬件升级。

## 自审和未验项

`PENDING_CASES.json` 列出 13 个可执行函数级用例定义，覆盖重复 seq、无效哨兵、reset/资格、config、三 clip、X/Z、时基/输入/timeout 反例。候选仅在未来显式调用 selftest.run_case 时按指定源码 SHA 从字节加载；不走 pycache。全部 NOT_RUN，未分配组号，不增加或恢复 R7/R08 额度。

本批实际只做 Node 文件读取、JSON/ZIP 载荷/SHA/字面文本检查、源体封装，以及只读静态自审。无候选导入、Python/HDL 编译、功能测试、EDA 或设备操作；对应命令、退出码、原双流均为 NOT_RUN。M2 接手精确执行/库隔离/资源与窗口决定，M1 接手算法文字及独立映射/audio_stable 定义。R29/S50/C42/H54、T20+9 等旧消费不变，余下 T27 与旧 R7-C6 仍 NOT_RUN。board_release_allowed=false。
