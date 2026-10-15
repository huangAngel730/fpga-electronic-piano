# R04 覆盖矩阵与缺口清单

## 1. 结论与边界

本文件只对封存的 R04 ModelSim testbench 做**静态 L0 覆盖复核**。复核结果是：

- TB 确实给出了从 MIDI 串行输入，经共享事件握手、四声部状态、PCM 提交、I2S 串行活动、第五音场景、处理周期上界到复位清理的一条有界正例链；
- 多数判据是计数下界或 DUT 状态量，足以拒收“链路完全不工作”等明显故障，但不能独立证明事件字段、每个声部的音高／包络／贡献、PCM 数学、I2S 协议字、抢占身份或物理时序；
- `status_max_processing_cycles < 834` 是 TB 对 DUT 汇总状态量的直接阈值检查，不是 TB 自己按请求 ID 重建的逐帧日历；
- 本包未运行 `vlib`、`vlog`、`vsim`，没有产生真实编译或仿真结果。真实 ModelSim 的精确输入组合、机器／工具身份和执行预算仍须先由 M2 确认。

覆盖矩阵后的新增断言、monitor 和反例均为**建议项**，是否修改后续 TB 由 M1 决定。本次没有修改封存 TB、算法 RTL、模型、正式接口、ROM 或封存证据。

## 2. 精确输入身份

| 输入 | 字节数 | SHA-256 | 本次用途 |
|---|---:|---|---|
| `code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1双音色延迟_ModelSim自包含输入_20261015.zip` | 以仓库原件为准 | `1101f1af0809530a150143456aab8ff9a1c66373e9ccbc174c6459e8c916b3bf` | 唯一 R04 静态输入封包 |
| ZIP 内 `MANIFEST.json` | 14402 | `015bf0199c5118ecfe7ec96bfd0b216d8f195daaf4989ec6bc08779def180815` | 91 个受清单约束成员的长度／SHA |
| ZIP 内 `PREPARATION_RECEIPT.json` | 41946 | `866e5fba237090f9a32be3e193b214839de2498eb809a68d5ade4d5628cc0f91` | 准备状态、69 个编译单元、40 个可逆路径替换及来源身份 |
| ZIP 内 `README.md` | 854 | `5468b35d36c84cec3ca1310078d7fa327420bdb4559a0108120dc89d04381d8e` | 执行边界和预期命令 |
| ZIP 内 `inputs/compile.f` | 2203 | `99279bbab257786467495ba95ee311b969ed72f94ffe458e1e935a5f29bfd2bb` | 69 个编译单元清单 |
| ZIP 内 `inputs/tb_m2_m1td_real_chain.sv` | 3485 | `6325f8f0e332e30cb32d573080c5191b7a516b821a3e08bb531a1b53f9148ee6` | 本覆盖矩阵唯一 TB 源码 |
| `code/docs/M1_完赛任务单_2026-10-15.md`，提交 `5f41a44d29611636aae407e2a30899c32cd69949` 中的原件 | 以该提交原件为准 | `2467de1756e4c3d66bdc03302fb22a1de4718f29345aa3c49ac0daf04cdf2f81` | R04 验收范围和执行许可边界 |

补充口径：ZIP 实际共有 **92** 个条目，其中 `MANIFEST.json` 自身不列入自己的 `members`；`members` 中有 **91** 个受长度和 SHA 约束的成员。`PREPARATION_RECEIPT.json` 声明原 M1 双音色／延迟封存 ZIP SHA-256 为 `5c18926ae307301e91ec0e44dcf4a48b2fb57adec71ad46c494b14df59913b06`；本次只核对该声明与 R04 封包，没有另取原 M1 ZIP 重算。

封包状态为 `PORTABLE_MODELSIM_INPUT_PREPARED_NOT_EXECUTED`，`simulator_run=false`，因此下面所有结论都是源码覆盖能力，不是已经发生的仿真结果。

## 3. 判定口径

- **直接检查**：TB 直接比较信号或计数并在不满足时 `$fatal`。
- **间接证明**：被比较量来自 DUT 内部汇总状态、层次计数或“至少 N 次”活动；它能证明链路有进展，但不能唯一推出更细的功能语义。
- **未覆盖**：该 TB 没有独立 observer、黄金模型、协议解码或精确账本来检查。

源码行号均指 ZIP 内精确 TB `inputs/tb_m2_m1td_real_chain.sv`。

## 4. 覆盖矩阵

| 项目 | 激励与直接观察 | TB 实际拒收条件 | 能直接说明什么 | 只能间接说明／不能外推什么 |
|---|---|---|---|---|
| 启动与复位静音 | 初始 `sys_rst_n=0`；500 ns 观察 `pa_en`（31 行） | `pa_en !== 1` → `M1TD_AMP_NOT_MUTED_IN_RESET` | 仿真该时点功放使能处于静音电平 | 不证明 FPGA 配置前 IO 默认态、板级电平、模拟爆音或真实 PLL 行为 |
| PLL／配置启动 | 1500 ns 后释放外部复位，再等 4000 ns；观察 `pa_en` 和 `config_count`（32–33 行） | `pa_en !== 0` 或配置握手次数不等于 1 → `M1TD_CONFIG_OR_PLL_STARTUP` | 仿真模型中复位释放后功放打开，M1 配置握手恰一次 | `config_count` 是层次化握手计数；没有核配置字段读回、锁相品质或硬件启动时间 |
| MIDI 串行接收 | `midi_byte` 以 32 us/bit 发送状态字和数据字节（23–29、34、38–39、45–46、51 行） | 没有逐字节即时断言；通过后续 `accepted` 等判据拒收 | 实际驱动了 UART 形态的 MIDI 字节，不是直接灌事件结构体 | 只从共享 FIFO 输出握手数推知接收链有进展；未核每个事件的 kind/channel/source/note/velocity/program、顺序、延迟、parser 错误或 FIFO 水位／溢出 |
| 首个钢琴音到 PCM | 发送 NoteOn 69/100，等待 220 us（34–37 行） | `accepted<1`、活动声部 `<1`、提交 `<3` 或非零提交 `<3` → `M1TD_REAL_PIANO_EVENT_TO_PCM_MISSING` | 至少一次共享事件握手，至少一个活动声部，至少三次提交且至少三次左右声道之一非零 | 没有核 note69 最终属于哪个声部、440 Hz、速度增益、包络、精确 PCM 或左右声道分别非零 |
| Program Change 与第二音 | 发送 Program 1，再发送 NoteOn 64/80，等待 220 us（38–42 行） | 累计 `accepted<3`、活动声部 `<2`、提交／非零提交 `<10` 或串行 1 位 `<5` → `M1TD_REAL_PROGRAM_EVENT_TO_AUDIO_MISSING` | 到该检查点至少三次共享事件握手、两个活动声部及持续音频／串行活动 | 未直接核 Program 事件字段、Program 1 是否真正选择目标音色、音色差异、延迟效果或第二音是否独立贡献 |
| 四音同时活跃 | 再发送 NoteOn 60/95 和 67/85，等待 220 us（43–49 行） | 活动声部数不严格等于 4、累计提交 `<20` 或非零提交 `<20` → `M1TD_FOUR_SIMULTANEOUS_VOICES_MISSING` | 指定时点 `status_active_voice_count==4`，并有持续 PCM 提交活动 | 活动数是 DUT 汇总状态；未核四个身份／频率分别为 69、64、60、67，未核四路都对 PCM 有非零贡献，也未核提前抢占、重复分配或相位独立性 |
| 第五音与四槽上限 | 保存计数后发送 NoteOn 72/110，等待 220 us（50–56 行） | `accepted` 未增加、活动数不等于 4、帧／提交未各增加至少 3，或最大处理周期 `>=834` → `M1TD_FIFTH_STEAL_OR_833_CYCLE_DEADLINE_FAIL` | 第五次 NoteOn 后共享握手有增加、活动数仍为 4、帧和提交继续前进 | 不直接证明 note72 已占槽、究竟抢占谁、抢占策略／身份代次正确、旧声部已终止；“第五音被接受并正确抢占”只获部分间接证据 |
| PCM 提交 | 在 `dut.g_polyphonic.m1_commit` 上累计 `commits`，并在 `produced_left!=0 || produced_right!=0` 时累计 `nonzero`（13–20 行） | 各场景以累计下界拒收 | M1 提交脉冲实际出现，且若干次提交的左右声道至少一边非零 | 未核请求 ID=提交 ID、一请求一提交、取消／HOLD、提交精确时点、PCM24 数值、舍入／饱和、clip、左右一致性或独立数学参考 |
| 音频帧推进 | 对 `dut.i2s_frame_tick` 累计 `frames`（20、50、53–55 行） | 第五音场景要求帧数比快照增加至少 3 | I2S 帧 tick 在场景中持续出现 | 未核帧间隔的 833/834 分布、帧与 PCM 一一对应、欠载为 0、重复播放语义或长程稳定性 |
| 串行输出活动 | 在 `i2s_bclk` 上升沿、外部复位已释放且功放打开时累计 `i2s_din===1`（22、41 行） | Program 场景累计高位 `<5` → `M1TD_REAL_PROGRAM_EVENT_TO_AUDIO_MISSING` | DIN 不是始终为 0，且 BCLK 有足够边沿让观察过程运行 | 没有 I2S/PT8211 解码；未核 BCLK/LRCK 比例、相位、16/24/32 位槽、符号扩展、左右顺序、帧边界或串行值与提交 PCM 一致 |
| 处理周期上界 | 第五音检查时读取 `dut.status_max_processing_cycles`（53–56 行） | `status_max_processing_cycles>=834` → `M1TD_FIFTH_STEAL_OR_833_CYCLE_DEADLINE_FAIL` | DUT 的累计最大“请求接受到提交”状态值小于 834 | TB 没有独立重建请求／提交日历；未核每个请求的周期数、834 边界反例、欠载计数、在所有输入组合下的服务上界，也不是物理 40 MHz STA |
| 运行超时 | 独立 initial 在 6,000,000 ns 触发（65 行） | `M1TD_REAL_CHAIN_TIMEOUT` | 获准运行时若 6 ms 仿真时间内没有结束会失败 | 这是仿真时间上限，不是宿主进程 300 s/900 s 的墙钟预算，也不是连续运行稳定性 |
| 尾段复位清理 | 拉低 `sys_rst_n`，等待 1000 ns；观察 `pa_en`、活动数、buffered L/R（60–62 行） | 功放未静音、活动数非 0、任一播放 PCM 非 0 → `M1TD_SHARED_RESET_NOT_CLEAN` | 该复位时点的四个公开／层次观察量清零或静音 | 未核 FIFO、pending、请求／提交 ID、clip／underrun、配置状态、ADSR/DDS/延迟历史全部清空；未做复位后再次释放和重新发音 |
| 总 PASS 标记 | 所有前述检查后打印（63 行） | 任一 `$fatal` 或 6 ms timeout 都到不了此行 | 将来的真实日志必须出现 `PASS M2_M1TD_REAL_CHAIN_BOARD_FUNCTIONAL_ONLY` | PASS 只覆盖本矩阵，不代表独立数学、资源映射、PnR/STA、板级或完整 T052/T060/T061 通过 |

## 5. 建议补测与新增断言（仅供 M1 决定）

以下不是本次验收条件，也没有写入封存 TB。若 M1 决定采用，应复制到新的受控后继并由 M2 重新核定输入身份和执行预算；不要回写原封存包。

### 高优先级

1. **共享事件精确账本**：在 `shared_event_valid && shared_event_ready` 时记录完整 64 位事件，逐项核状态／数据字节对应的 kind、note、velocity、program、source_id 和顺序；把累计下界改为预期事件序列检查。
2. **四声部身份与贡献**：在公共可接受的 observer 上核四个不同 note 身份同时存活，并为每个声部提供独立频率／相位或静音变体贡献证据；不读取算法私有寄存器冒充公共行为。
3. **第五音抢占账本**：明确 note72 的新代次、被替换的精确 victim、活动集合仍为四，以及旧代次结果不能再提交；目前只有“握手增加 + 活动数仍为四”。
4. **请求／提交 ID 与帧预算**：独立记录 request accept、cancel、commit ID 和周期；核一请求最多一次提交、旧 ID 拒收、`max<834` 与独立最大值一致，并直接断言 `audio_underrun==0`。逐帧 833/834 间隔及摘要可交 `frame_budget_offline` 分析器处理。
5. **I2S 协议 monitor**：解码 LRCK/BCLK/DIN，核时钟比、相位、槽宽、左右顺序、符号扩展，并把解码样本与成功提交的 PCM 对齐。当前 `serial_ones` 只能证明“有 1 位”。

### 次优先

6. **Program／音色／延迟的可辨行为**：核 Program 1 的配置真正作用于目标声部；以独立参考或定向输入验证音色和一采样延迟配置，不用“非零 PCM”代替。
7. **左右与 clip**：分别要求左右有效，加入不等左右的定向输入，核 clipping 标志与饱和端点；当前 `left!=0 || right!=0` 无法发现单边断路或左右交换。
8. **复位完整性与恢复**：复位前制造 FIFO/pending/延迟历史，复位时核所有公开状态清理，再释放复位并完成一次新的 MIDI→PCM→I2S 事务。
9. **协议和容量负例**：加入坏 MIDI 状态／截断字节、FIFO 背压／溢出、第五音身份错接、提交 ID 错接、I2S 左右交换和 deadline 边界行为反例，确认各自被指定诊断拒收。
10. **长程覆盖**：在实际获准预算内增加 NoteOff、Release、CC64、panic、重复 note、取消、帧欠载和多次抢占；不把短窗正例外推为长期演奏。

## 6. 自动静态自检

### 最终实际命令

在仓库根目录，用 Windows PowerShell 5.1 执行以下等价检查：

```powershell
$ErrorActionPreference = 'Stop'
$zipPath = 'code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1双音色延迟_ModelSim自包含输入_20261015.zip'
$expectedZip = '1101f1af0809530a150143456aab8ff9a1c66373e9ccbc174c6459e8c916b3bf'
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath).Hash.ToLowerInvariant() -ne $expectedZip) {
    throw 'ZIP_SHA_MISMATCH'
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
$z = [IO.Compression.ZipFile]::OpenRead((Resolve-Path -LiteralPath $zipPath))
try {
    function Read-ZipText([string]$name) {
        $e = $z.Entries | Where-Object FullName -eq $name
        if ($null -eq $e) { throw "MISSING_$name" }
        $sr = [IO.StreamReader]::new($e.Open(), [Text.Encoding]::UTF8)
        try { $sr.ReadToEnd() } finally { $sr.Dispose() }
    }
    $manifest = (Read-ZipText 'MANIFEST.json') | ConvertFrom-Json
    $memberProps = @($manifest.members.PSObject.Properties)
    if ($z.Entries.Count -ne 92 -or $memberProps.Count -ne 91) {
        throw "ENTRY_OR_MEMBER_COUNT_$($z.Entries.Count)_$($memberProps.Count)"
    }
    if ($manifest.status -ne 'PORTABLE_MODELSIM_INPUT_PREPARED_NOT_EXECUTED') {
        throw 'BAD_MANIFEST_STATUS'
    }
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        foreach ($p in $memberProps) {
            $e = $z.Entries | Where-Object FullName -eq $p.Name
            if ($null -eq $e -or $e.Length -ne [int64]$p.Value.bytes) { throw "MEMBER_$($p.Name)" }
            $s = $e.Open()
            try { $actual = ([BitConverter]::ToString($sha.ComputeHash($s))).Replace('-', '').ToLowerInvariant() }
            finally { $s.Dispose() }
            if ($actual -ne $p.Value.sha256) { throw "SHA_$($p.Name)" }
        }
    } finally { $sha.Dispose() }
    $receipt = (Read-ZipText 'PREPARATION_RECEIPT.json') | ConvertFrom-Json
    if ($receipt.status -ne 'PORTABLE_MODELSIM_INPUT_PREPARED_NOT_EXECUTED' -or
        $receipt.simulator_run -ne $false -or $receipt.compile_units -ne 69 -or
        $receipt.mapped_literal_count -ne 40 -or
        $receipt.m1_archive_sha256 -ne '5c18926ae307301e91ec0e44dcf4a48b2fb57adec71ad46c494b14df59913b06') {
        throw 'BAD_PREPARATION_RECEIPT'
    }
    $tb = Read-ZipText 'inputs/tb_m2_m1td_real_chain.sv'
    foreach ($needle in @(
        'M1TD_AMP_NOT_MUTED_IN_RESET', 'M1TD_CONFIG_OR_PLL_STARTUP',
        'M1TD_REAL_PIANO_EVENT_TO_PCM_MISSING', 'M1TD_REAL_PROGRAM_EVENT_TO_AUDIO_MISSING',
        'M1TD_FOUR_SIMULTANEOUS_VOICES_MISSING', 'M1TD_FIFTH_STEAL_OR_833_CYCLE_DEADLINE_FAIL',
        'M1TD_SHARED_RESET_NOT_CLEAN', 'M1TD_REAL_CHAIN_TIMEOUT',
        'PASS M2_M1TD_REAL_CHAIN_BOARD_FUNCTIONAL_ONLY'
    )) {
        if (-not $tb.Contains($needle)) { throw "TB_MARKER_$needle" }
    }
    'PASS R04_COVERAGE_REVIEW_INPUTS archive_entries=92 manifest_members=91 compile_units=69 mapped_literals=40 simulator_run=false'
} finally {
    $z.Dispose()
}
```

### 实际结果

| 轮次 | 结果 | 退出码 | 说明 |
|---|---|---:|---|
| 首轮身份脚本 | FAIL | 1 | 脚本错误地把“91 个 manifest 成员”当成 ZIP 总条目数，实际读到 92；没有发现封包损坏，也没有执行 ModelSim。 |
| 修正后最终自检 | PASS | 0 | `PASS R04_COVERAGE_REVIEW_INPUTS archive_entries=92 manifest_members=91 compile_units=69 mapped_literals=40 simulator_run=false`；逐个核了 91 个成员的长度和 SHA，并核了九个关键 TB 诊断／PASS 标记。 |

第一轮失败是本静态检查命令的计数口径错误，修正为“92 个归档条目 = MANIFEST 自身 + 91 个 manifest 成员”后通过；失败事实保留在本表，不回写原封包。

## 7. 样例解读（不是仿真结果）

若将来同一身份的真实日志出现：

```text
END REAL_M1 accepted=<n> active=4 commits=<n> nonzero=<n> frames=<n> serial=<n> max_cycles=<n>
PASS M2_M1TD_REAL_CHAIN_BOARD_FUNCTIONAL_ONLY
```

只能结合原始 `vlog/vsim` 日志、退出码、无 FATAL／无超时、输入前后 SHA 和 M2 批准的执行收据，解释为本矩阵的指定正例走到 PASS。不能仅凭这一行断言 PCM 数学正确、I2S 协议正确或物理 40 MHz 达标；尖括号内容是占位符，本次没有填造任何运行数值。

具体矩阵样例：`M1TD_FOUR_SIMULTANEOUS_VOICES_MISSING` 没有触发时，可直接说明检查时点的 `status_active_voice_count==4` 且累计提交／非零提交达到下界；仍不能说明四个声部各自是 69/64/60/67，也不能说明四路分别有独立 PCM 贡献。

## 8. 适用范围与未验证项

### 适用范围

- 仅适用于上述 R04 ZIP、精确 TB SHA 和精确任务单身份；任何 TB、source、ROM、compile list 或路径适配变化都必须重做身份核对和增量覆盖复核。
- 可作为 M1 决定是否补 TB 的静态输入，也可作为 M2 审核将来一次真实 ModelSim 回执时的“TB 实际承诺”清单。
- 本交付自身为静态 L0 文档和输入身份自检，不提升 R04 的功能等级。

### 明确未验证

- 未运行 `vlib`、`vlog`、`vsim`，未核 ModelSim 10.7 二进制／依赖身份、编译兼容性、真实 PASS、墙钟预算或退出码；
- 未独立重算 DDS、ADSR、音色、延迟、混音、舍入、饱和、clip 或 PCM24 数学；
- 未证明每个活动声部的音高／相位／包络／身份和独立 PCM 贡献；
- 未解码 I2S/PT8211，未证明左右声道、BCLK/LRCK、槽宽、相位和串行 PCM 一致；
- 未证明请求／取消／提交 ID、HOLD、旧结果拒收、欠载、长期演奏和所有 833/834 边界；
- 仿真 PLL 模型只产生名义时钟和 lock，不证明真实 PLL、CDC、MTBF 或板级复位；
- 未运行综合、BSRAM/DSP 映射、PnR、STA、码流下载、板级电气、DAC／功放、模拟录音或端到端延迟；
- 不把既有物理 L5 报告与本次静态复核拼接成同版功能／物理整机通过；
- 完整 T052、T060、T061、138K 正式整机与生产四／多声部仍不因本文件自动关闭。

## 9. 将来真实执行的许可边界

本工具包不会启动 ModelSim。将来真实执行仍应先向 M2 提交并确认：精确源码／ROM／TB/`compile.f`/manifest SHA、ModelSim 10.7 工具与依赖 SHA、执行机器、`cwd`、全新输出目录、每工具不超过 300 秒、整轮不超过 900 秒、FATAL／超时／PASS 标记合同和单次执行额度。批准后才能按封包 README 中的命令执行，失败保留首失败原件，不自动重试、换工具或提高预算。
