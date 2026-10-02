# V3低音拍频研究候选：阶段交付

2026-10-02。冻结源码已验证，真实RTL仿真、Gowin综合及本次PnR/STA通过，V3研究试听.fs已生成；**低音改善未达标，听感NOT_ACCEPTED，未烧录、未上板实测。**
本候选不是已修复版，不替换现用正式版本。50 MHz时序余量极小，保留原约束边界和PR1014警告。

## 实际结果

| 检查 | 实际结果 |
| --- | --- |
| 独立振荡器整数黄金比对 | PASS：79170行、158382检查，覆盖88键、重触发、低/高音切换及复位 |
| 真实四声部核心/CC64生命周期 | PASS：246624检查；61646帧黄金比对，包络最大差1 LSB、波形差0、PCM24最大差512 LSB（限1024） |
| 四声部能力回归 | PASS：296654检查、107364样本；最大音高误差0.153 cent；丢音/忽略力度反例被拒绝 |
| MIDI→正式顶层→PT8211解码 | PASS：真实50 MHz/31250 baud，真实采样帧1041/1042周期；加速音频Note及CC64回归通过，损坏串行LSB反例被拒绝 |
| 同条件模型音频 | 八组V1/V2/V3原始及RMS匹配WAV，共48份；ROM/常数重新生成逐字节一致 |
| Gowin实际综合 | exit 0，产生加密.vg；27955 Logic、7074寄存器、12 BSRAM、0锁存器 |
| 实际PnR/STA | PASS（原SDC范围）：50 MHz，Fmax 50.150 MHz，Setup/Hold违例0/0；最小余量0.060/0.001 ns |
| 码流/上板/听感 | .fs已生成并SHA核查；未烧录、未上板、听感NOT_ACCEPTED，不能宣称消拍成功 |

Gowin 1.9.11.03 Education，目标GW5AT-60B-PBGA484A-1，料号GW5AT-LV60PG484AC1/I0，顶层electronic_piano_top。上述综合行保留前阶段r2报告；本次IDE自动补跑综合后PnR，最终28366 Logic、7074寄存器、12 BSRAM、28/118物理DSP（PnR报告实际值），0锁存器。

## 研究试听码流交付（不烧录）

- [.fs（RESEARCH_NOT_ACCEPTED）](E:/FPGA/GAOYUNFPGA/pop_repair/v3/output/bitstream_v3_research_20261002/electronic_piano_v3_RESEARCH_NOT_ACCEPTED_427f3d3_20261002.fs)
- [SHA与完整溯源manifest](E:/FPGA/GAOYUNFPGA/pop_repair/v3/output/bitstream_v3_research_20261002/manifest.json)
- [构建、时序、边界和操作记录](E:/FPGA/GAOYUNFPGA/pop_repair/v3/verification/PNR_DELIVERY.md)

SHA256：d561c10eee9de55355ff6a7a65d31893314ef4f2cda2a37c7915a9e42b40a5e4。18,109,476字节。
Recovery/Removal最小报告余量7.147/1.011 ns，最小脉宽余量6.914 ns。工具未给出未约束路径总数，不能宣称为0；异步输入、UART/PA输出及I2S占位延迟边界沿用原SDC。本次未做后仿真或物理PT8211时序验收。

## 音频结论与边界

≤220 Hz使用12分音候选，高音沿用V1；音高、四复音、力度和ADSR口径不变。
C2邻音36/37在65 Hz带的归一化慢起伏：V1=0.588472，V3=0.588481，几乎未变。
最低音24/25的65 Hz谐波带也未改善，部分快起伏上升。低音原始总RMS约比V1低3.9～4.1 dB；RMS匹配后仍不能证明人耳改善，不能以降音量判成功。
八个Gaussian近似带仅作诊断，不是完整心理声学粗糙度或LUFS。WAV是同当前包络、相同音符/力度/时长的模型对照，V2是谱/攻击行为移植，不是旧V2整机.fs精确模型；模型PCM16也不是正式PCM24混音逐位复刻。真实RTL另有黄金比对。

CC64经过真实路由回归；STAT路径保留并编译，未做本轮STAT UART协议测试，未恢复T025/T026。当前正式基线本身无HDMI，本轮不新增HDMI。

## 文件入口

- [实际日志与构建快照](E:/FPGA/GAOYUNFPGA/pop_repair/v3/build/candidate_20261002_141443_r2)
- [八组WAV及指标](E:/FPGA/GAOYUNFPGA/pop_repair/v3/output/audio_audit_1)
- [冻结/复制/路径适配SHA清单](E:/FPGA/GAOYUNFPGA/pop_repair/v3/build/candidate_20261002_141443_r2/frozen_input_manifest.json)
- [实际综合命令](E:/FPGA/GAOYUNFPGA/pop_repair/v3/build/candidate_20261002_141443_r2/gowin_synthesis/command.json)
- [最终审计](E:/FPGA/GAOYUNFPGA/pop_repair/v3/verification/FINAL_AUDIT.md)、[验证发现](E:/FPGA/GAOYUNFPGA/pop_repair/v3/verification/FINDINGS.md)

## 实际运行命令

以下为本次已运行命令，结果目录已存在，运行器拒绝覆盖；复跑须新建独立快照并把$snapshot指向新目录。不要删现有结果来复跑。

```powershell
$taskPython = 'C:/Users/songdongkuan/miniconda3/python.exe'
$taskNumpyPython = 'C:/Users/songdongkuan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$taskVerify = 'E:/FPGA/GAOYUNFPGA/pop_repair/v3/verification'
$snapshot = 'E:/FPGA/GAOYUNFPGA/pop_repair/v3/build/candidate_20261002_141443_r2'
& $taskPython -B "$taskVerify/run_oscillator_checks.py" --snapshot $snapshot
& $taskPython -B "$taskVerify/run_core_checks.py" --snapshot $snapshot --suite lifecycle --cc64
& $taskPython -B "$taskVerify/run_core_checks.py" --snapshot $snapshot --suite existing_capabilities
& $taskPython -B "$taskVerify/run_full_top_checks.py" --snapshot $snapshot --mode note_fast
& $taskPython -B "$taskVerify/run_full_top_checks.py" --snapshot $snapshot --mode note_real
& $taskPython -B "$taskVerify/run_full_top_checks.py" --snapshot $snapshot --mode sustain_fast
& $taskPython -B "$taskVerify/run_gowin_synth.py" --snapshot $snapshot
& $taskNumpyPython -B "$taskVerify/run_audio_audit.py" --snapshot $snapshot
& $taskPython -B "$taskVerify/audit_old_versions.py" verify
```

本次追加构建命令：先以prepare_pnr_attempt.py --name pnr_attempt_2创建独立副本，然后在已安装Gowin IDE自带Tcl控制台执行 source {E:/FPGA/GAOYUNFPGA/pop_repair/v3/build/pnr_attempt_2/run_pnr.tcl}（不是Windows终端命令）。该脚本设置SystemVerilog 2017、原顶层及副本include路径，再run pnr；实际工具生成的cmd.do/.prj/日志在pnr_attempt_2/impl。最后运行audit_old_versions.py verify及export_pnr_delivery.py。现有交付目录不可覆盖，未重跑完整仿真。

权限：主对话3负责source/design，主对话2仅负责verification/build/output/README。正式仓库HEAD仍为427f3d33d6559e83b31e7e5347993db7dc4fa124，无代码修改、Git提交或推送，无下载/Flash操作。本轮交付是研究候选与验证证据，不是低音修复完成。
