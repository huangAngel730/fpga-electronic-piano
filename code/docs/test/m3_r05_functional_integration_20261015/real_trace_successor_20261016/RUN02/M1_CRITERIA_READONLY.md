# 给M3：R05冻结算法、源/ROM与PCM声音判据

待用户转发真人M3，尚未送达。依据M2第11批通知，R05功能复核和隔离候选接入由M3主责；本文件是M1算法/声音判据交接，不开发或替换M3 checker、TB、候选接入或新采集工具，也不构成真实执行许可。本批仅L0静态身份/合同与日志软件增量，未提交/未推送。

## 1. 用哪份原件和数学参考

R05输入ZIP SHA `dcf15f5d3ded1a0b160f55eab43066c728f80b3c329c44ea9f099c63f178696a`，273908 bytes；91清单成员+MANIFEST自身=92。新TB SHA `6e677154d0a53ff97e794555ef57695e385a9963de43f1ac9135a54c32fc9777`。源/ROM/编译清单保持R04原字节，TB只补X/Z拒收；本包 `inputs/` 提供实际ZIP，`INPUT_AND_ALGORITHM_IDENTITY.json` 提供逐项对照和9份ROM完整SHA。

M1完整冻结候选ZIP为 `algorithm_reference/M1_双音色与立体声延迟完整链_20261014.zip`，416469 bytes，SHA `5c18926ae307301e91ec0e44dcf4a48b2fb57adec71ad46c494b14df59913b06`。其中A04/B01/EDGE01/CHAIN02只按原精确身份、原有界范围REUSED，不重跑。32项业务源/ROM对R05的31项相同，`m1td_note_pitch.sv` 仅3处include guard从NOTE_PITCH_SV改M1TD_NOTE_PITCH_SV，R05 SHA `3dde1ca9d72da29030e03940504abe758856fffbaf9a637867a2ebf27f3194d6`，请保留隔离。R05清单才是实际执行树身份，不能仅凭旧模块名或旧封存SHA认同版。

| 冻结ROM/模块 | R05 SHA-256 |
| --- | --- |
| `rom/piano_band_4x256_8191.mem` | `c117230f43c7efce36be445f851140d3155aa2a35e71ea8a41f529ea2b5d32a1` |
| `rom/triangle_wavetable.hex` | `a6ee3195ad3a3310de5102531aac9d7773eebc6c31633d72c01b72a7d2461e3c` |
| `rom/velocity_gain_rom.mem` | `1bc0fd4430884604224a20620368afa50805b4efbf57d9703cae7a09132ffe64` |
| `sources/m1td_adsr_piano_envelope.sv` | `fd43aa6044b094d64f053c136092b767e1d3f8c384a0548c9c66fb602905a4af` |

辅助冻结模型位于 `algorithm_reference/frozen/`：dds_model、envelope_model、allocator_oracle、sine.mem和velocity.mem，精确SHA见身份JSON。`envelope_model`依赖同目录dds_model；保持该闭包。PianoDDS/FCW/PitchMod、整数ADSR/pre-NBA准备、gain/mix和分配身份可按各自函数/原签范围复用。完整候选ZIP的 `delay_effect_fixed.py` 提供T028数值模型，外层仍需按实际接受、配置、取消、历史写入建账；其中delay0旧注释误导，实际读当前环位置旧值，绕满1024个已接受效果样本回读，最终DELIVERY已有纠正。

`check_stage_a.py` 用实际bank wave/env重算gain/mix，属于限定L3，不是完整独立DDS/ADSR证明；`check_chain.py`从已混音PCM开始且含旧CHAIN02固定条数/日历，不能不适配直接当R05 checker。本交接不新增适配器或新checker。旧 `PURE_SINE_EXPECTED.csv` 是另一事件日历的12050行纯软件期望，不能套在R05，不能把其四正峰不clip或相位日历当Piano/Triangle+delay的结果。

## 2. 实际音色与声音解释

R05 bank无条件使用 `m1td_piano_triangle_voice`：Program0=Piano V1，Program1=Triangle，其他Program忽略。Program按source/channel保存，仅在成功NoteOn/重触发时锁入槽；已有音和Release不随后续Program改变，reset默认Piano。将 `PIANO_TIMBRE_ENABLE=0` 不能把此bank切成纯正弦。

R05 TB先发note69/velocity100（Piano），再Program1，随后64/80、60/95、67/85（Triangle），最后72/110为第五音。先前69不能因Program1就立即变Triangle。active=4不能独立证明每路贡献或第五音victim身份。

Piano用4×256表、力度相关attack长度和流水；力度既影响包络峰幅，也可能影响起音亮度，不能要求力度只变幅不变谱。Triangle的tick取推进前相位；纯正弦模型取推进后相位，Piano另有寄存延迟，不能混用相位日历。音高由冻结FCW/PitchMod决定；Piano/Triangle谐波不算额外独立声部，单一路波表多峰不能证明四路同时演奏。

## 3. PCM、延迟与事务合同

signed16波形乘unsigned Q15包络（≤32767），33位乘积算术右移15，负值向负无穷取整；signed16结果左移8成signed24，空槽强制0。四路signed32先求和，再饱和到[-8388608,8388607]；无除4、pan或额外归一化。clip为严格超限，正负边界本身不算clip。需要同epoch/请求ID/slot-generation及真实lane_tick解释每个样本，不能用帧序号推断取消后的振荡器相位。

板顶层启动实际配置为 **enable=1、delay=1、dry=32767、wet=16384、feedback=0**，不是独立候选reset后的默认旁路。对每路已接受效果事务，输出数值为：

```text
y = sat24((x * 32767 >> 15) + (delayed * 16384 >> 15))
```

两项分别右移再相加；历史在feedback0时写入当前x。n/延迟按**已接受效果事务**计，取消发布仍可能已推进历史，不能只用成功commit行重建历史。只有enable0才逐位旁路、不写历史。左右独立历史；最终clip=upstream OR effect，feedback clip仅历史诊断；clip_count在成功buffer commit把L/R最终clip OR后只计一次，不能在HOLD重复计数。

frame优先取消旧发布资格，不能同沿接受旧结果；已接受算法/效果工作可能继续排空且不回滚相位/历史。ready背压下result/ID/PCM/clip保持，跨reset不接旧代；reset清模式、资格和历史。外层result握手与真正buffer commit、playback frame要分清。未完成/取消请求、接受前等待及历史排空必须另记，不能从仅成功结果推导。

MIDI力度10位转换沿用 `v10=8*v7+floor(v7/16)`，v7=0规范为NoteOff；1/16/64/127分别为8/129/516/1023。非零力度增益取冻结1024字ROM，不用浮点近似替代逐位期望。键位、力度及起音比较需要匹配未被撤销的目标身份；已有声音非零或任意首commit不能代目标首次声音。

## 4. 验收边界与协作

TB的nonzero只计commit非零，serial_ones只计串行1位；都不能独立证明PCM正确、串行协议字、四路真实贡献、精确第五音victim、频谱或模拟声音。协议需完整PCM/I2S字的左右序、符号、幅度、样本/帧对应证据；当前TB通过也只签其指定有界L2观察。

`max_cycles<834`只限成功接受→commit的累计观测最大值，漏接受前等待、取消和未完成请求。逐帧真期限为 `commit_edge < next_frame_edge`；accept在F+a、帧长T时必须 `L <= T-a-1`。R05把该比较改为X安全不补齐逐笔期限证明，也不证明导出完整。沿用上次M1对M3帧预算/覆盖矩阵的受限合同；新TB/monitor/exporter/PCM-I2S/延迟/预算写集仍按M2实际授权，不由此文扩建。

旧M1 e9执行器因Failure漏检被M2拒绝。新支援执行器 SHA `1f2eebb681398fda778143f5b5979d247d1281357cd340303d9aad26270a8544`、本机提案预检 SHA `f0cbe213ad26796d02c60e30747886889d89a67e5041e768b4dbf33071a0d752`；10例本次日志软件增量符合预期。M3只读checker须同样拒两步两流的Error/Failure/Fatal/assertion及正数Errors，helper PASS不得覆盖runner FAIL。M1不代写该checker。

如需要M1工具机，先据本包完整工具/目录身份与M2协调新R05精确组合，再由M3协调执行所有权；不可沿用旧R04许可、旧stage或旧输入。本机提案尚未获准，300s等待/900s调度预算也非严格全程墙钟保证。换主机、目录、工具、命令或写集需重新核实际预检。

真实R05 ModelSim、定向音频STA、物理资源/BSRAM推断、实物四谱峰、键位力度与模拟≤10ms仍待验。正式board_release_allowed=false；旧4207完整性UNKNOWN、T052 PARTIAL保持，T060原H已签离线完成保持原范围，不因R05新缺口回退或外推。旧128/T060原H与已签数学不重跑。
