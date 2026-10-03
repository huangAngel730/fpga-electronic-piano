# Pitch/Mod实际四声部接入候选：功能通过，音画STA失败（2026-10-03）

**结论：最小实际音频接入候选已实现并通过L2/L3，Gowin综合L4通过；最新音画布局布线完成但STA失败，不满足L5，不落正式、不烧录。**
当前正式RTL、公共包、引脚和旧可用码流保留。不能因为工具退出0或生成.fs就发布失败候选。

## 实现范围

新增M2隔离候选目录 `code/tb/board/pitch_mod_bank_integration_candidate/`，不在正式GPRJ：

- router原功能不改，只输出注册的四槽来源、通道和代次，供控制参数绑定。
- bank把同一个成功演奏事件同时交真实router/控制表，不能一侧先接收。
- 在事件分配完成、ADSR准备结束后冻结四槽身份/base FCW与请求id，四读快照后计算FCW。
- math结果id/source/channel/generation/occupied核对成功后，才用对应FCW同时推进真实V1 DDS/ADSR。
- 空槽DDS保留原base相位生命周期，occupied槽LFO每次真实计算只推进一次。
- frame_tick取消并排空旧math/control事务；帧缓冲下一拍的新request id在排空期间保存，避免丢失新帧请求。已计算LFO状态不回滚，遵守原消费者合同。
- 原V1 ROM、CC64、分配器、Q15 gain/PCM24 mixer/帧提交均只读复用。ADSR使用已验证流水候选，不改曲线/240 Attack/4800 Decay/Release或幅度。

默认Mod为既有候选5Hz/最大±50音分（LFO_INC447392、depth512），不是用户最终冻结声明。
不接T028或Program音色政策，不修改M1模型、M3解析器或可视化算法。

## 功能实际结果

命令：

```powershell
python -X utf8 code/scripts/run_pitch_mod_bank_integration_candidate.py --output code/output/pitch_mod_bank_newrun
```

实际run3：502188项银行检查、1886个消费结果；Python记分板由成功事件独立维护source/channel状态，4353个非零控制声部结果与M1模型匹配。
784个中心/Mod0样本与**无控制的已审ADSR流水银行参考**逐样本匹配，保留V1 DDS/包络/FCW/occupied/states；不冒称与未流水化的旧生产ADSR逐周期相同。
真实分配器/CC64/Release尾音/同音重触发/第五键抢占及旧键松开、背压、7阶段帧取消/复位均自检。
错请求tag与绕过调整FCW两个变异先编译，再由行为断言拒绝，不把编译失败当反例PASS。

真实polyphonic_audio_core→Q15 floor gain→4voice mixer→pcm_result_hold→pcm_frame_buffer：560帧、560非零输出，3394检查，clip与非故意underrun为0；最大请求到实际提交30clk（600ns@50MHz）。
该600ns仅**RTL仿真内部处理段**，不是MIDI键盘到模拟声音的端到端延迟，不恢复T031实测或外推≤10ms。

## 最新组合物理构建

Gowin V1.9.11.03 Education、GW5AT-LV60PG484AC1/I0，top为audio_visual_coexistence_top。
由V0161冻结工程复制组合，当前3d6430e parser/midi_input、f8054b5正式counter换入，新增顺序control snapshot与四槽FCW流水，实际音频bank/router换本候选。
严格闪光沿已审冻结源码。47工程输入，7 ROM文件，CST未变；系统50MHz、像素25MHz、串行125MHz，setup uncertainty1.000ns、hold0.550ns，不放宽false_path/CDC例外。
仿真bank/router与PnR副本只有显式ROM路径替换差别，代码语义一致。
可复现准备入口：

```powershell
python -X utf8 code/scripts/prepare_pitch_mod_bank_combo.py --output code/output/pitch_mod_combo_newrun --frozen-project code/output/hold_guardband_20261003/C_hold055/audio_visual_coexistence_top.gprj
```

准备不运行Gowin，不覆盖旧output，不表示任何验收通过；精确输入/ROM SHA输出到manifest。

### 最终STA（失败）

| 项目 | 实际结果 |
|---|---:|
| Logic | 19711 / 59904 |
| Register | 8671 / 60780 |
| DSP | 46 / 118 |
| BSRAM | 20 / 118 |
| 系统Fmax | 35.878MHz，目标50MHz未达 |
| 像素Fmax | 35.035MHz，目标25MHz |
| 系统Setup最差 | -7.872ns |
| 系统Hold最差 | -0.390ns |
| Recovery最差 | -0.334ns |
| Removal最差 | +0.643ns |
| Setup违例端点 | 430（系统427/串行3） |
| Hold违例端点 | 2770 |
| 像素Setup/Hold | +11.457/+0.275ns |
| 串行常规Setup/Hold | +7.229/+0.275ns（仍有Recovery导致端点违例） |

资源未接近器件容量上限，不能据此声称时序够用。原报告门禁的0.500ns与8BSRAM要求仅对原音频生效；本候选0.550ns与20BSRAM单独严格核对，**真实Setup/Hold/Recovery错误全部保留，未过滤**。
报告复核入口：

```powershell
python -X utf8 code/scripts/check_pitch_mod_bank_combo.py code/output/pitch_mod_bank_integration_20261003/physical1
```

实际返回1。主工具退出0/.fs生成并不等于STA通过。失败fs只在忽略output保存，不压缩交给M3烧录、不提交Git。

## 当前阻塞路径和下一步

最差Setup：`u_midi_input/u_midi_event_parser/system_data_remaining_0_s0/Q → locked_event.control_value_10_s3/D`，data26.818ns、skew−.009ns；前列同类端点指向locked control value。
源码路径为本拍parsed_control影响effective_control_pending，再进入32槽RR线性选择、selected_value和锁定。原M3 L2通过不证明该新路径已满足50MHz；问题由本次真实组合STA量化，不是泛化指责。

建议M3优先修该**输入调度组合结构**（优先于非阻断D来源审计），不改8握手上界/1kHz/RR/同拍最新值/CC1取消去重/payload稳定/FIFO次序。可根据注册pending/RR预计算第一/第二候选，本拍parsed update末端决定插入/删除，或等价平衡树；需逐拍独立参考和原行为反例。若必须增阶段，先讨论实际延迟/合并与握手口径。
具体新范围通知已准备，**待用户私发M3后开工**。M2未自行修改任何parser。

M2侧最差Hold：`u_controls/snapshot_id_15 → u_pitch_mod/held_id_15`，data .382ns、skew−.197ns；另有base流水、ADSR ROM地址和输出短路径。
Recovery位于串行复位到OSER10 CLK复位，−.334ns。优先在输入Setup修复后的同版新布局检查全域/时钟分布，再针对剩余短路径处理，不先给大量短路径插无意义delay、不增加无依据false_path、不牺牲50MHz。
候选Hold门槛0.550ns保留为实验策略；若需改变正式约束、钟树或接口，另按D027群通知。

正式接入涉及router只读私有身份输出、bank状态机/工程依赖与既有ADSR流水落地；M1跨岗位通知和接口群通知已经整理，但未送达、未应用正式patch。

## 验证等级和证据

- L1编译、L2自检、L3独立M1模型对照、L4Gowin综合实际完成。
- PnR流程完成但STA失败，**L5未通过**。
- 没有L6/L7、真实键盘变调/颤音、同版音画实屏、T028或动态音色切换结论。
- 证据：`code/docs/evidence/pitch_mod_actual_bank_integration_20261003.json`；原运行/最差路径/报告SHA位于`code/output/pitch_mod_bank_integration_20261003/`。
- 首轮验证入口缺include，run1失败保留；补依赖后run2银行通过，run3增两个真实反例/PCM完整通过，未靠重复挑结果。

旧正式版本保持，补丁尚未应用；本阶段功能接入候选可以供复核，但不发布为稳定电子琴码流。

发布门禁第一次T007的tb_key_to_tone exit1，原run.log未产生本次新结果，保留为执行限时疑点而非擅自判功能FAIL；只按用户规则重试一次，实际最终发布门禁结果另登记。正式依赖SHA保持不变，不延长原300s入口或关闭任何检查。

唯一一次按原入口重试后，仓库九项门禁实际全部PASS（141文件Python语法/T007/T019），未修改正式源码、门禁或超时值；第一次失败日志保留。门禁通过只允许发布本轮候选/失败证据，不改变音画STA失败判定。

发布前同步到M3来源审计26c6ab5，已普通合并保留双方提交历史；本条仅接收提交，未签收D测试结果，不再派重复审计。解析器Setup长链仍作为新的具体任务待用户转发后开工。

同步26c6ab5后的最新发布门禁再次实际九组全PASS（142Python/T007/T019）；这只证明当前仓库门禁，不替代D来源审计专项或当前音画STA。
