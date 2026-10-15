# 138K C 四声部双音色＋立体声延迟：M2 私有整机候选

## 当日新增物理后继（晚于下述静态与 Icarus 失败）

新隔离拷贝 `_06` 已由 M2 用 Gowin 单次 `run all` 完成完整综合、PnR、STA；工具退出0，Setup +1.736、Hold 0、Recovery +1.410、Removal +0.492 ns，Logic27879/FF9582/DSP50/BSRAM28。专用新组合报告复核通过原平台检查中的引脚、时钟、CDC及四类时序判据，旧 L 两条内部音频定点路径和旧 DSP/BSRAM 相等判据仅对旧网表有效。证据与精确 SHA 见 `code/docs/evidence/m2_m1td_physical_20261015/README.md`。**真实 M1 全链在新板级的 RTL 仿真仍未通过/未重试，ModelSim R04 增量输入仅静态准备；这份新 `.fs` 不是可下载版本。**以下小节保留构建前历史状态，不作为最新阶段结论。

2026-10-15。此候选只从 T056 `L_locations_guard065` 一次完整构建已验精确工程与 M1 封存包生成，不改冻结 L、公共包、原 ROM、正式顶层/CST/SDC 或生产码流。**当前完成静态接线核验；新整机功能编译 FAIL_PARTIAL，未仿真、未综合/PnR/STA、未上板，不能当新 L5 或可下载工程。**

阶段封存证据包：`code/docs/evidence/m2_fourvoice_timbre_delay_stage_20261015.zip`（SHA-256 `90fb74ae1782cb3810a425ce4f357d7f519cd4294fe707ec76d32709711debce`），含按包内manifest校验的实际源码快照、收据与M1/M3待转发回执；包内生成期“未提交”仍为历史时态。

## 冻结输入及分支区别

- T056 L 原输入 56 项适配 SHA 逐项核对；器件 `GW5AST-LV138PG484AC1/I0`，50MHz板载输入经现 PLL 产生40MHz音频域，25MHz像素域保持。旧 L 构建、.fs、pin 与 40MHz STA 只证明旧精确组合，不借用到本候选。
- M1 包 `M1_双音色与立体声延迟完整链_20261014.zip` SHA `5c18926ae307301e91ec0e44dcf4a48b2fb57adec71ad46c494b14df59913b06`。该包 `m1td_timbre_delay_chain` **四声部事件→两音色→一次混音→左右延迟**；入口需 event_valid/data、frame_tick、sample_req+ID，输出 PCM24 L/R+结果ID+左右 clipped。另一个 `m1td_stereo_delay` 只是对 N32 已混音 PCM 做后处理，不能让 N32 再经过四路 mixer。本候选只采用前者。
- M2 `premixed_frame_adapter` 以 request_valid/ready/ID 绑定 M1 calc_ready、frame 取消与结果 ID/PCM/clip，成功 frame-buffer commit 才累计一次 clip。L 顶层原 MIDI/按钮 FIFO、PT8211 LSBJ I2S、PA_EN、复位/PLL、显示和状态 UART 的既有路径保持。新的 `m2_fourvoice_timbre_delay_frame_core.sv` 是唯一新增音频连接壳。
- 新顶层为 staged 私有 `m2_fourvoice_timbre_delay_board_top`，板外端口与 L 原顶层逐字一致。配置只在 reset 后发送一组候选测试常数（enable=1、delay=1、dry=32767、wet=16384、feedback=0）；**正式用户运行时配置切换尚未接入**，M1 独立模块中的切换测试不能代替此工程。Program 音色事件是否由 L MIDI parser 全链转换，尚需新组合 RTL 验证。不能因结构静态通过宣称完整双音色实测。

## 独立准备及实际失败

```powershell
python -B -X utf8 code/scripts/prepare_m2_m1td_138k_whole_20261015.py --output code/output/NEW_PREPARED
python -B -X utf8 code/scripts/check_m2_m1td_wiring_20261015.py --prepared code/output/NEW_PREPARED --output code/output/NEW_STATIC
python -B -X utf8 code/scripts/check_m2_m1td_138k_whole_20261015.py --prepared code/output/NEW_PREPARED --output code/output/NEW_COMPILE
```

输出目录必须新建，原源码只读，receipt 记录源码/工具 SHA、退出码和错误。_05 准备实际 exit0：84 staged 输入、69 工程文件、18 文件仅路径及 macro guard 适配；原 L 旧 DDS 辅助模块同名，故从新 GPRJ 排除（原字节仍保留供回退）。CST 中旧四声部 FF INS_LOC 2 条、SDC 旧音频定向端点 2 条在**新副本**注释，**尚未映射新网表，物理准入锁闭**。独立静态 checker `_02` exit0、69文件 SHA、15结构判据、错左右/错clipped 两定向软件变体均拒收；这不是 RTL 仿真。

编译失败原件分别在 `code/output/m2_m1td_whole_compile_20261015_02`（旧 include 绝对路径）、`_03`（同名 sine_wavetable_1024）、`_04`（NOTE_PITCH_SV 宏保护碰撞）和 `_05`：对前 3 项只在 staged 副本做路径/宏适配并保留失败。`_05` 的 Icarus 实际运行 90.031 秒后按上限终止，返回非零，stderr 另含 `m1td_voice_allocator_4.sv:37` 的变量类型报错与内部 elaboration 断言；源及工具执行前后 SHA 一致，未运行 `.vvp`，不自动重试或提高超时。M1 原独立 ModelSim 正例与本次 Icarus 新整机工具不等价；**目前没有新的整机功能通过证据**。M2 需和 M1 核该精确源/工具兼容或在明确新许可下用可用正确工具独立编译仿真，再对成功的新组合做资源推断/40MHz新 STA，不能借历史 L。

## 增量板级连接仿真（音色链替身；严格限域）

独立 `code/tb/board/m2_m1td_board_contract_20261015/tb_m2_m1td_board_contract.sv`
在**名义 PLL/DVI 模型**下以 M1 公开端口替身连接私有整机候选；Icarus只编译
板级输入/复位/FIFO、M2帧适配与PT8211发送，**真实 M1 音色/延迟源没有编译/运行**。

```powershell
python -B -X utf8 code/scripts/run_m2_m1td_board_stub_20261015.py --prepared code/output/m2_m1td_whole_prepare_20261015_05 --output code/output/NEW_WIRING_RUN
python -B -X utf8 code/scripts/run_m2_m1td_board_stub_20261015.py --mutant --prepared code/output/m2_m1td_whole_prepare_20261015_05 --output code/output/NEW_MUTANT_RUN
```

最终正例 `_02` compile0/sim0，总6.109秒：真实31250bps MIDI NoteOn 经共享FIFO接受1，
配置握手1，54帧54提交、9帧非零、零欠载、I2S输出72个采样1，复位关功放并清PCM；
左右样本与替身的约定 L=131072/R=-65536 对应。变体只在全新输出内交换新顶层
`committed_left/right` 两条线，compile0/sim1，指定
`BOARD_STEREO_COMMIT_WIRING_MISMATCH` 非零拒收；runner判断变体被拒后总退出0。
源码/工具执行前后 SHA 一致，各工具独立上限90秒、总300秒，失败不自动重试。
这不是M1算法、历史RAM效果、正式N32或新整机STA片段通过。

## 资源/交付状态

M1 延迟双缓冲历史声明 2×1024×24=49152 bit，仅理论存储位数。`m1td_delay_effect` 对全数组使用异步复位和同步整片 flush，**实际是否推断 BSRAM UNKNOWN**；不能从旧 L 的 20 BSRAM 或 M1 独立 L2 推断新资源。未生成新 `.fs`、新引脚报告或新恢复码流。完整 T052/T061 与生产双音色/延迟验收保持各自 PARTIAL；实物许可未发。所有 `_01` 到 `_05` 失败/成功目录保留，不回填旧证据。