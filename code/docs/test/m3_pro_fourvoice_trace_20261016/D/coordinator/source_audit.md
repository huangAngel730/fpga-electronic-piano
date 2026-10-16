# Pro 夜间任务来源差额自审（2026-10-17）

本报告仅为 **L0 原件身份、静态接口与来源缺口核查**。读取基线为 `ca4859abc28e3a5f7fdd0250e9f2cd43de39a8c0`，本机 HEAD 与本机 `refs/remotes/origin/develop` 均为该 SHA；未 fetch，不能据此证明实时远端。未运行测试、编译、EDA、工具预检或 Git 写命令，未访问硬件，未联系其他对话；唯一写入为本文件。没有审阅其他窗口正在实现的 C/D/双滑块代码。末节为总控另行指定的 D3 入口静态自审。

## 1. 用户原包与任务版本

原包实际位置是 `E:/FPGA/GAOYUNFPGA/night_task/10.17/M1_M2_M3_Pro夜间任务与并行窗口_20261016/`，不在仓库内。以下均由现存文件原字节计算 SHA-256，六份任务文件均与 MANIFEST 声明一致。

| 文件 | 字节 | 实测 SHA-256 |
|---|---:|---|
| MANIFEST.txt | 888 | `1713b2edbf917cf61f849004f3becf0dbeec16a51a26f8c7bfc6577dcfa4d8e7` |
| M1_夜间五小时_Pro四声基础_2026-10-16.md | 6761 | `fde5829bfb3a5c6d15a8aded4a7c146603d8a04c213f2f661ff4d2eaa2d1e3ee` |
| M2_夜间五小时_Pro四声基础_2026-10-16.md | 7407 | `3d0d7f73fbad2bf8d856185f9ee1fc971b0baad19d01f3db37cb88739e628c73` |
| M3_夜间五小时_Pro四声基础_2026-10-16.md | 12780 | `4f0dc770c438aea18b5e4e552f3d2058dbdd23831710ed8271485c331014a0a3` |
| M2_并行拓展双音色窗口_2026-10-16.md | 3415 | `1dce191b111d6a85368529cffe65659236f28a30d82dd6ba86d6e398edc4745d` |
| M3_并行拓展双滑块窗口_2026-10-16.md | 3191 | `367d5e6472cf2cdf1ba48bafc6e3d703f23be3add1272bf325ba67358fa49028` |
| 夜间任务通用执行规范.md | 6987 | `f07e0a6c2fb62b56e1887a15860f3c98c0c95522a0dade970e3235c6dcb0680b` |

MANIFEST 声明来源提交 `627cc60bc11b8c0c023cc98082ee3d1efb7c6cae`、未推送及当时 9/9 门禁；本次仅验证包内字节，不代核该提交、门禁运行或发布。包中引用的三份完赛任务单“首页 Pro FPG676 执行卡”未出现在本机基线对应首页；基线仍写 PG484/R05/旧现场优先级。今夜按用户直接指定的新包隔离任务执行，不从旧首页恢复 SRAM、ModelSim 或 EDA 额度。

仓库 `code/docs/夜间任务通用执行规范.md` 为 6252 字节、SHA `b257424df3217a5f09016282369172e6ead3c08f7728d0beee6eb60561b89c57`，与用户包有实质内容差异。包新增每独立包最多 6 轮、新队列顺序；不是换行差异。新 M3 主单为最多 5 小时、C/D 各最多 6 轮新隔离自检，共用实际验证时间上限 4500 秒；Python 每组 90 秒、已核 Icarus 每组 240 秒。ModelSim/Gowin/PnR/STA/设备均无新额度。此 L0 审计消耗上述实际验证轮数 **0**。

## 2. M2 Pro 精确源与 M1 黄金：当前缺件

以下 M2 新单指定目录在本机工作树均不存在；在指定基线也未找到对应候选源：

- `code/rtl/board/m2_138k_pro_fourvoice_candidate_20261016/`
- `code/constraints/m2_138k_pro_fourvoice_candidate_20261016/`
- `code/build/138k_pro_fourvoice_candidate_20261016/`
- `code/tb/board/m2_138k_pro_fourvoice_candidate_20261016/`
- `code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/`

因此未取得 **Pro 完整器件、top、编译顺序/宏/参数、PLL/IP、ROM 原字节及 source-to-trace 映射**的同版合同。已有 `code/rtl/138K_Pro/` 是原理图、参考 CST、静态引脚报告及生成脚本，不能充作可运行 Pro top 或 ROM 清单。静态报告保留 GW5AT-LV138FPG676A 原理图旧符号与 GW5AST 工具命名差异；完整 Part/步进仍待 M2/实物确认。

可复用的静态板级依据包括 4072 核心板 50 MHz P16、PT8211 BCLK E22/WS F24/DIN G24、XPT4809 H17 高工作/低掉电；参考 CST 本身没有 P15/N16/H17。此处仅引用仓库既有 L0 报告，不新签实物电平。旧 PG484 低有效功放、旧码流和五 pair STA 均不能映射成新 Pro 功能/物理通过。

M1 以下五个目录本机均不存在，指定基线亦无目标 oracle 目录；其 `pro_successor_20261016/` 自然未到件：

- `code/model/m1_r05_pcm_oracle_20261016/`
- `code/docs/test/m1_r05_pcm_oracle_20261016/`
- `code/model/m1_visual_audio_guard_20261016/`
- `code/docs/test/m1_visual_audio_guard_20261016/`
- `code/docs/test/m1_fourvoice_night_candidate_20261015/`

基线 M1 任务单 P0 明确要求发布上述五目录，旧交付记录为本地包/未提交未推送；任务总览记录工具门禁 7 PASS/2 FAIL 阻断。仓库里的 M2 限定复核文字及包 SHA 可作为查找线索，不能代替黄金源、ROM、输入和结果原件。结论仅为 **该基线及当前本机未取得可消费黄金**，不推断 M1 其他机器没有成果，也不否定既签数学结果。当前可推进独立合成事件/串行夹具；实际 Pro DUT 逐样本数学核验为 `PENDING_PRO_SOURCE_OR_TRACE` / `PENDING_M1_GOLDEN`。

## 3. 已有正式接口及夹具必须保留的边界

| 项 | 当前可核事实 | 新夹具边界 |
|---|---|---|
| 统一事件 | `audio_defs_pkg.sv` 64 位：event_type3/source_id4/channel4/note_number7/velocity10/expression10/control_id8/control_value12/reserved6；reserved=0。MIDI velocity 映射 `{v7,v7[6:4]}`，零力度 Note On 在公共 FIFO 前归一 Note Off。 | 不把 scene、lane、generation、epoch 私塞 reserved；这些是旁路证据字段，需要独立合同。 |
| 事件接受 | `event_valid && event_ready` 同系统上升沿握手；反压时数据稳定；FIFO32；同 source/channel/note 重触发。 | 外部输入握手不等于核心应用；应用顺序、FIFO 入/出同拍规则、slot/lane 选择及所有 lane_tick 需 M2 精确源合同。不能按 DUT 波形反推“独立”事件日历。 |
| PCM | signed24，范围 −8388608..8388607，左右共用 valid；真正缓存 valid/ready 表示 commit，非 frame consume。 | 绑定 req_id 和 epoch；完整 frame_tick 与左右 WS 半帧不可混用。`i2s_tx.ready` 是 legacy direct-input indicator，不能充作正式 `pcm_ready`。 |
| 缓存/期限 | `pcm_frame_buffer.sv`：请求由 frame_tick 且 calc_ready 触发；32 位 request ID 每帧推进；ready 还要求非 frame_tick、无 pending、ID相等；复位清空 pending/held/计数。 | 下一完整帧边界前交付；边界同拍提交不能当本帧输入。超期/取消、复位截断、尾部完整性需逐请求证据，不能仅数最终 commit。 |
| 数学与 DAC | 冻结 DDS×ADSR signed33 乘积算术右移15，左移8成 PCM24；至少32位混音饱和。DAC 为 `clip16((pcm24+128) >>> 8)`，加偏置前先扩展符号位。 | M3 可检查 DAC 量化与输入域，不独立重写 M1 四声数学黄金；负半LSB按现规则向正方向，不用语言默认银行家舍入。 |
| LSBJ | WS低右/高左；BCK上升沿采样，MSB first；每声道32沿的后16位有效，最后沿为LSB；64BCLK/48kHz。 | 真实串行须由物理 BCLK/WS/DIN 解码；L=R不能证明左右映射。合成 L≠R 可检消费者，但不能提升为实际 Pro 串行证据。 |
| 时钟 | 包要求40MHz核/48kHz及833/834拍。正式公共包 `BOARD_CLK_HZ=50MHz`、默认 BCLK step `527765581` 是旧50MHz配置。 | 不直接在40MHz套默认参数；需 M2 top 明确覆盖（32位翻转累加器40MHz候选步长659706977）及PLL/reset/相位起点。833/834来源应是真实帧边界，不能独立固定833调度。 |
| 复位/功放 | 正式模块 rst_n 低有效、异步拉低/本域同步释放；新包 PA_EN 高有效。 | PA_EN 高有效是 Pro 候选要求；旧 top 反极性不可继承。需要记录锁定/稳定、复位、PA_EN 原始沿及未知值，不用合成常量伪装观测。 |

最少还需到件的字段/身份（不要求扩大公共接口）：

1. **M2 身份清单**：完整器件/封装、top 与端口、source list 顺序/宏/参数/IP、每个 ROM 源路径/运行映射/字节/SHA、核心及串行时钟参数、观察器源 SHA；真实 capture 与运行收据绑定这些原件。
2. **时基合同**：cycle 原点/采样沿与 NBA 前后相位、RESET/PLL lock/stable/epoch 变更、同拍记录顺序、启动 X 与尾部终止规则；只写40MHz不够。
3. **独立演奏输入**：scene、event_seq、完整64位事件或全部字段、注入/接受/实际应用 cycle 与顺序、source/channel/note/generation、lane/slot 分配规则，所有 lane_tick，包括未活跃声部；C 规则来源不能是 DUT 内部 wave/env/phase。
4. **请求生命周期**：epoch/req_id、frame_id、request/accept/return/commit/consume/cancel 的 cycle，反压、效果接受/取消/配置、PCM左右及clip、pending/held/underrun。只有 RETURN 没有 commit/consume 不能签完整链。
5. **串行及安全原件**：连续 BCLK/WS/DIN、公开PCM/ID与同次frame映射、rst_n/lock/stable/PA_EN；左右不等、负值/边界及跨帧复位覆盖。字段缺失必须 UNKNOWN/REJECT，不生成替代值。
6. **M1 黄金原件**：冻结算法/ROM身份、四独奏与四音同时输入、逐样本左右PCM/clip/效果历史合同与原始运行收据；source0/channel0旧合成结果不能覆盖任意新输入身份。

## 4. 本次关键仓库读取身份

以下为工作树原字节 SHA-256。对接口规范/公共包/tx/buffer/三份完赛单，`git diff --name-only <基线> -- <这些路径>` 无输出；读取没有发现这些文件相对基线修改。其他窗口新文件不纳入此比对。

| 文件 | SHA-256 |
|---|---|
| code/docs/模块接口规范.md | `5bcfd9d355fb76aafb798104ea517bc047534d0740273b78df74c0d16758f8e5` |
| code/rtl/common/audio_defs_pkg.sv | `833076283882bae79af3f54c40e6cd6ae4a9ff5638a90e4f0afc3e2b3861d064` |
| code/rtl/audio_out/i2s_tx.sv | `6c703e31064e5943df4e310b3baddd8935362a1c028828d8e11f8f3c016267ad` |
| code/rtl/audio_out/pcm_frame_buffer.sv | `f8bc454a2e627809c2f9f9029c1e5128acf2fd543d7fcc2d3d83b50685f40997` |
| code/docs/M1_完赛任务单_2026-10-15.md | `64379b4f6fd204c4c407c904917da479bff1d541db2914fc8995f73ae0c2c4d0` |
| code/docs/M2_完赛任务单_2026-10-15.md | `a1b192e5eb6cbcd18c8e1808989b5224f7afb1b7cae44586757e6cc2eea52a35` |
| code/docs/M3_完赛任务单_2026-10-15.md | `860b77b41f00f1ed88053dd9ed80098bbdb165d5d83778d50cab14c24a78370d` |
| code/docs/138K四声部后续集成任务总览_2026-10-15.md | `b24ef8e56f3134c165326a655e07072a55dd13cd36423fe2ebaa54dc6c564b0a` |
| code/rtl/138K_Pro/tang_mega_138k-pro_pins.cst | `f647104f7b74800890d0283a438b226301bff3a3429a04ec0f6df63c9026e8ba` |
| code/rtl/138K_Pro/Pro_引脚核对_CST_R02_20261016/M2_待用户转发_尚未送达.txt | `563782631e0d878ef210dfd1f1c5e76374f57e5fe2b460b1c8e7689c1644b615` |

最后一份现存文本为4230字节；旁边历史 manifest 声明4254字节/SHA d43aadb...。本报告采用实测原字节 SHA，不冒称历史清单与当前检出字节一致；未追查差异来源或修改历史包。

## 5. 总控 D3 intake 首轮前窄范围静态发现

仅阅读 `code/software/m3_pro_fourvoice_trace_20261016/D/ingest/ingest.py`（SHA `131a94806a706a97477509c5d1c220ee46aa250facf51f93d8e8e0c760af53b6`）和 `run_selftest.py`（SHA `a56d359f06d885d534000425326fdf980b219f75de8de11c94089653fdef9dbf`）。以下针对这次读到的字节，不评价后续修改或测试结果；未执行入口/自检。

- **期限/复位可洗掉未消费返回**：`intake()` 的 FRAME 仅阻断 REQUESTED/ACCEPTED，RETURNED 可跨多个帧未 CONSUME，再由 RESET 静默取消。保留另一个合法 consumed 请求时最终条件仍可能通过。另外 RETURN 若恰在下一FRAME同cycle但行序在前，可先变RETURNED，绕过“严格帧前提交”期限。最小修法：记录 return_cycle；在对应截止FRAME要求 return_cycle < frame_cycle，登记该边界必须结清的CONSUME；离开该cycle前/下一FRAME或RESET前拒收未结清。RESET只能截断尚未越过截止边界的事务，不能追认已经漏消费的事务。不要把多个同cycle记录的序号当成实际早一系统沿。
- **超时缺原件且组预算没有硬停止**：runner `subprocess.run(...,timeout=...)` 未捕获 TimeoutExpired；发生时后面的双流、COMMAND_RECEIPT 和 RESULT 均不会写出。`max(0.1,85-elapsed)` 在预算耗尽后仍继续逐例，不能形成整体90秒上限。最小修法：捕获并保留异常 stdout/stderr、exit_code=null/timeout原因、当轮FAIL；达到组截止时停止启动剩余case并标NOT_RUN，finally封总收据。无需扩大测试额度。

来源等级本身目前保持 `pro_dut_pass=false`、`board_release_allowed=false`，DECLARED_REAL 分支也仅 `INTAKE_STRUCTURE_ONLY_PENDING_M2`，未发现直接把来源声明升级成Pro DUT通过的路径。不过该入口的 source/rom 是身份附件、contract 明示 identity_only，calendar 仅req日历；它不核真实源码语义、完整演奏日历、物理串行或M1黄金。PA行也不是强制出现，因此即使修完上述阻断，所得仍仅限定入口/合成夹具核验，不能称完整D期限/功放覆盖或真实Pro链通过。

本文件未提交/未推送；最终统一封存、发布与所需 M2 接收由总控负责。

### 5.1 首轮后的修复增量与原件绑定（只读复核）

总控首轮后提供的当前入口 SHA 为 `042ba83051d681eac83c6ffbbd0b8cf5d918b473474b2e20d3f7371105c7ab5e`，runner SHA 为 `bb372c9c1f032668ca0f9cb1576d9f310b37f29fd1a77148fdba75b50eed1704`。`D/ingest/ROUND_01/RESULT.json` 实测 SHA `05eb2f18c349e57048535fe80099d70d3ab1d93fd093077f84b7133c3eb3ed2a`，其中 source/runner 身份与当前文件原字节一致。

收据记录16个 CLI 例（1正15负）、1.5940000000009604秒、1轮；正例exit0，其余exit1且各首失败符合该例期待。此次只读计算结果清单所列128个输入/双流文件的字节数及SHA，全部一致；抽读正例和 `return_on_deadline` / `reset_after_missed_consume` 双流，后两例确分别为 `RETURN_NOT_STRICTLY_BEFORE_FRAME` / `RESET_UNCONSUMED_DUE_FRAME`，没有把入口拒收作为正例接受。没有重新执行这16例。

严格帧前RETURN与RESET不掩盖已到期返回的指定路径已修；runner已有85秒启动前停止条件、TimeoutExpired/OSError双流及null退出留痕、出错终止后续且总结果要求全部case齐套。此次收据没有发生超时，故超时路径仅静态读取，未实测。

**仍有同类阻断，未代修或申请新额度**：当前 `ingest.py` 的 CANCEL 分支（162–164行）只核 REQUESTED/ACCEPTED/RETURNED，仍可将已经由 FRAME 写入 `due_cycle`、应在该帧消费却漏 CONSUME 的 RETURNED 改成 CANCELED，绕开下一帧及RESET检查。关键反例是在某请求下一FRAME后省略CONSUME，加入该req的CANCEL，再保留另一条正常消费保证 `consumed>0`；原schema与独立req日历仍可匹配，但未履行消费义务被抹去。最小修法是 CANCEL 同样拒收已有 `due_cycle` 的请求，并明确允许取消的期限/原因合同；如本夜无验证余量则封存为此入口的静态已知缺陷，不能用已通过16例冒称完整期限闭合。首轮原件继续保留。

### 5.2 CANCEL 修复与第二轮增量终核

本次只读增量确认5.1所报“已到期后CANCEL抹掉消费义务”路径已修：CANCEL要求 `due_cycle is None`；记录 `cancel_cycle`，随后实际下一FRAME要求 `cancel_cycle < frame_cycle`，同cycle的行序不能把显式取消变成提前一拍。后一个同cycle检查仅静态核读，本轮五例没有直接执行该反例，不扩大测试覆盖声明。

当前入口和 ROUND_02 源码快照 SHA 均为 `3217f97e57daec534306a213c64566fa111e3116f15a15967ca881847c218e07`；当前 runner及快照 SHA 均为 `a7b9f49a8a210791422b584b583885b2e21fbfe8026986a6f46e9beeae353254`。ROUND_02/RESULT.json 实测 SHA `016f52d07f90a821e00a70570cc64278d799ecc01a1fdf8b2d4dd75c47e6e783`，记录源/runner与当前字节对应。ROUND_01/source_snapshots 两文件分别仍为5.1记录的 `042ba830…ab5e` / `bb372c9c…1704`，未以新源码替代第一轮身份。

第二轮原收据为5个CLI例、2正exit0/3负exit1，0.7180000000007567秒。40个列明输入/双流文件的实测字节数/SHA全部匹配。三个负例原stderr首失败为 `RETURN_NOT_STRICTLY_BEFORE_FRAME`、`RESET_UNCONSUMED_DUE_FRAME`、`CANCEL_AFTER_DUE_FRAME`。新late_cancel原件有另一个已正常消费请求，以及req8在1677请求、1712返回、2510下一FRAME、2511取消，正对应本次修法；cancel_before_due正例将取消放1713、下一FRAME2510，能接受有效提前取消，并非一概拒绝CANCEL。

本次修复增量与上述五例绑定范围内未发现新阻断；这是限定入口自审，不代签完整期限、真实Pro trace、物理串行或数学黄金。两轮运行收据合计 **2轮、2.312秒**，未把第一轮16例重新算成最终新版全回归。总控已说明D/D2保留最多4轮，共享总6；本次核查自身新增测试轮数0，未运行任何入口/测试/EDA，未修改实现。`pro_dut_pass=false`、`board_release_allowed=false`及真实Pro待件边界保持。

## 6. 来源刷新：M1旧R05原件现已发布恢复

**本节优先于第1/2节关于本机当前缺件的表述；保留原始ca4859审计及测试身份，不回填历史。** 总控经系统127.0.0.1:7892代理fetch并fast-forward至 `b6f289110a0b7341f1f9234c945bcb8d31d95aff`；本次只读 `git rev-parse HEAD` 确认为该SHA。本子任务未执行fetch/merge。

总控已封 `D/coordinator/SYNC_INTAKE/SYNC_INTAKE.json`（当前SHA `75da3f42ac8ca22c4d3d8a22f60221ee0f2e0e6b8c3ed37f40f271c54ab79bd9`），九份新来源原件包括M1 oracle/合同/依赖/ROM与更新任务文档；本次按指定范围只读清单，不重复核全部九份。M1旧R05五目录现已发布并在本机恢复，不能再称五目录未发布或旧黄金原件全面缺失。M2新Pro source仍缺，M1 Pro successor/新Pro同版数学适配仍待；已有旧R05原件不自动满足新Pro slot/Release、lane_tick采样相位、效果接受/取消/配置和精确source/ROM/top/trace合同。

## 7. C最终来源补件及独立日历窄范围自审

只读C的LATEST_RECEIPT、原RESULT、SOURCE_REFRESH_01/RESULT与SOURCE_REFRESH.json、ROUND_02/RUN_RECEIPT、calendar.py/cases.py/check_calendar.py及其必要输入/双流/合同；未执行源码、自检、旧303数学或其他测试，未修改C文件，未评价D未完成代码。

| 阅读对象 | 当前SHA-256 |
|---|---|
| C/LATEST_RECEIPT.json | `c965d3308ad74501f1943d1f244e0181461d16eb3552ce41e76a4fd63d059a94` |
| C/RESULT.md | `f0a2213f1f54aa7de5678bc06c7ac4914ebbf2f57671f19f6aab8379a8f361bb` |
| C/SOURCE_REFRESH_01/RESULT.md | `0208030169f5ec6f6006d16002595e89d4297de6960d1a366e2dc89028cbc908` |
| C/ROUND_02/RUN_RECEIPT.json | `636a793ddf61aebc6f245ec8851de7bfa6c7880a9db650abbb9d8e174495a255` |
| C/calendar.py | `9fc87b036410add695e464fa2b4813e8ee3ad8a05dd086ddf5a7dcef3b6852b1` |
| C/cases.py | `55b044c4900840e1d579f0c279783b98c3514a638f15f65f1bfdea157de01f8d` |
| C/check_calendar.py | `b67d8ca0f5818c4bbf751cacf47710d21d991ca47b7ffd6e40ab177c0ed709a3` |

79项身份条目（源码前后、固定计划/日历/合同、19例输入、原双流及LATEST引用文件/包）实测字节数/SHA全部匹配。本次检查包本体SHA，未重新解包逐成员审核。当前三份源码与ROUND_02源码前后身份一致；positive输入与冻结CALENDAR.jsonl同SHA `7e0de3ef9ae263fa230c88b3bd6610a508f4e9553de96d4995dcffce9288c747`。19例直接读取原stdout和收据退出码，确认1正exit0、18负exit2，预设拒收码及首差异索引全部对应，不把负例拒收写成正例接受。

`cases.hand_anchors()` 用固定手算表核19帧每帧ACCEPT/LANE_TICK的lane恰为[0,1,2,3]，包括inactive及后续取消的工作；四独奏60/64/67/72、合奏lane音高与逐放表、背压接受cycle10868/req54、复位后IDs[1,2,3,4]及总计76tick/75发布/5取消/71消费均有明确锚点，未从DUT phase/env/wave取得期望。checker除了生命周期检查还逐记录严格JSON编码比较冻结计划，类型差异、漏lane、尾部和错误scope不能靠Python bool==int等值混过。其V1只接受单一冻结toy计划，不能据此宣称可直接解析任意真实Pro日历。

NoteOff立即释放、最低空闲slot、lane=slot、每lane抽象RETURN/PUBLISH/CONSUME和833/833/834帧安排均明列为夹具假设；RESULT与来源补件明确真实NoteOff进入ADSR Release、真实slot回收/效果配置及时基仍缺。来源补件已更正旧RESULT中的“M1黄金未到”历史表述，LATEST同时绑定原包与新补件，不把旧R05恢复当新Pro映射完成。

**本次限定阅读范围内未发现具体假通过或错误等级阻断。** 可接受结论仍为C/C2固定合成夹具L1、1正18负符合预期；真实Pro映射PARTIAL/PENDING，board_release_allowed=false。收据记录两轮墙钟4.140秒，来源刷新新增功能调用0；本次子任务也新增测试轮数0。此结论不代签M1数学、真实服务期限、PCM/clip、串行或板级通过。

## 8. 双滑块冻结首轮窄范围只读自审

范围为 `m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/` 的新RTL/TB、ROUND_01原件，以及理解FIFO/控制CDC/帧状态所需的既有visual_event_bridge、visual_control_bridge、visual_mailbox_cdc、live/score tracker局部与M2接入合同。未运行编译、仿真、测试或工具预检；未修改该包任何文件，未要求重跑。

- 新RTL `dual_slider_pro_parallel.sv` SHA：`c0bbcc715edb573a160ce54c4d01982f15881dd311bdd38131d379059a48fc70`。
- 新TB `tb_pro_parallel.sv` SHA：`02337b8db37f849fdbe1b4c8a3f1200a117ea0a0e60ce7c15a1f923325823d9c`。
- ROUND_01/NIGHT_RUN_RECEIPT.json SHA：`e222e545b87fa865263ddf066ef46d236ac93d53bfb1a5b79a67a0305c24bdee`。

只读核before/after输入身份、6次调用12份原双流和13份stage源码与原源逐字节身份，共67项比较均匹配；未重复哈希整套工具依赖。stage为copyfile后相同SHA的实际编译输入。原positive.stdout有487条CHECK和最终PASS；compile/positive退出0，四mutation分别退出1，无timeout。总收据为passed=true、100.28199999999924秒、1轮，不把预检计作另一轮成功仿真。

静态连接与原日志支持以下限定结论：

1. 显示事件FIFO参数传32；桥实际为32排队项加1个在途mailbox，TB核33个有序输出、满32水位、第34个溢出drop=1、desync清空显示及复位清计数。满队列不产生音频ready反向连接。
2. mode/score分别经可靠mailbox；98位score在等待ready期间整体保持，8槽满、第9项mailbox占用、第10项源保持与最终10项身份恢复均有对应原日志。mode请求按toggle奇偶累计，只在frame_start锁存；同沿mode_pulse使用旧request值、下一帧生效，与M2合同及原CHECK对应。此处未声称所有score字段仅在frame边界才入队；score载入和模式锁存不是同一语义。
3. 共用异步复位断言、各域同步释放；TB含在途mode/score/event复位无ghost、队列及溢出清零。真实Pro失锁复位来源和跨域物理payload时限仍待新集成/STA，仿真不能证明亚稳态或板级时序。
4. 音频侧确接 `pcm_frame_buffer` 与 `i2s_tx`，PCM由TB按req_id合成，显示没有audio ready/PCM输出。满显示队列/暂停消费期间仍有frame和commit增长、无underflow；40MHz/48k音频帧833/834与25MHz 800×525两个完整帧间隔均在原日志被检查。这不是M1算法或PCM→串行逐样本数学比较，也不是新Pro完整音画同版。

四反例都是真实仿真信号故障，不是仅伪改文本：mutation1强制目的域mode_pulse直取源mode_valid，触发MODE_CDC_DELIVERY；mutation2屏蔽accepted_to_dut，触发EVENT_LOSS；mutation3强制display_mode=0，触发MODE_SWITCH_STALL；mutation4把音频calc_ready错误接到显示暂停使能，触发AUDIO_DISPLAY_BACKPRESSURE。四份stdout的首个FATAL均与收据/代码对应。mutation1证明该受控相位下错误跨域脉冲被拒，不能概括为覆盖所有CDC相位。TB force仅用于故障注入，不作为正常公开端口观察证据。

**此次限定源、绑定与四故障范围内未发现具体阻断。** 保持收据等级 `L2_ISOLATED_DEFAULT_GEOMETRY_FIFO32_FIXTURE`；正式Pro来源、mode/score生产者与帧零点/epoch、新STA及实屏均PENDING。命中闪光在新RTL明确禁用，原 `KNOWN_FAIL_DEFERRED_NOT_TESTED` 保留，不能升级为完整命中交互或旧闪光FAIL修复。当前仅审冻结首轮，不对仍在生成的最终封包作结论。
