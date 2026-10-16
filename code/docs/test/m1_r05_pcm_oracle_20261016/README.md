# M1-A：R06四频PCM最小黄金映射（2026-10-16）

本包完成现行M1活任务单2026-10-16增量A的**软件参考、输入映射条件和正反例**。对应新写集仅 `code/model/m1_r05_pcm_oracle_20261016/` 与本目录；主线真实结果为 `PENDING_REAL_CAPTURE`。未启动ModelSim、RTL、Gowin/STA或设备，未代写M3 observer、runner或串行checker，未改冻结算法/ROM或正式接口。N32仍暂停。

## 依据、输入和真实缺口

R06输入ZIP：`code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1TD_R06_XSAFE_7ms_ModelSim输入_20261016.zip`，273911 bytes，SHA `4be2b4c185691a3e493827a3a95303fa90f49ba6336eb4a8e0183942c8f05483`。总92条、91个清单成员、69编译单元；与M3成功7ms运行的89个inputs逐字节相同。逐项核验见 `../m1_fourvoice_night_candidate_20261015/SOURCE_INTAKE.json`。R06只将R05 TB watchdog由6ms改7ms并更新清单/准备回执，没有改音源算法。

M3已签有界L2结果是 `accepted=6 active=4 commits=303 nonzero=258 frames=303 serial=3905 max_cycles=35`，不能产生独立逐样本黄金。真实成功包没有接入现有公开observer；其中三份JSONL均明确是合成资料。现observer也没有完整的事件应用、lane_tick和已接受效果事务日历。仅用commit行/req_id不能唯一恢复取消前的相位和历史，缺项保持待验。

本包的 `Reference` 从**独立指定的事件应用沿、每次DSP advance沿和效果输入接受顺序**生成期望；不读DUT wave/env/phase/table来构造期望。当前只提供合成settled-event日历，不实现MIDI/router的周期模型。因此合成向量可以给M3建立数学字段映射，但不能直接宣称已经验证R06 TB的实际303条提交。

## 最小模型和边界

`oracle.py` 复用7项冻结依赖：原DDS/Piano表选择、整数ADSR、T010分配Oracle、T028数值模型，以及R06的Piano/Triangle/velocity三ROM。每次导入先核 `DEPENDENCIES.json` 的字节SHA，缺件/漂移即拒绝，不从工作树或网络回填。冻结源码原字节保留，局部`.gitattributes`防止Git换行归一化破坏SHA；没有运行其旧测试main。

支持N=4、Program0=Piano/1=Triangle、成功NoteOn锁音色/增generation、同音跨source/channel、第五音LRU、重触发、Release退休、Velocity0→NoteOff、reset和效果配置。无NoteOn清相位：空槽/Release/取消后的每次lane_tick仍推进四路；reset才清相位。只建无CC64/panic/PB/mod、无退休与重触发同沿的settled profile；这些未建组合明确拒绝，不能外推一般演奏。

事件应用和首tick间隔至少8个quiet clock，事件不能插入tick至E+5窗口；示例用更宽的16/64拍间隔。`advance_cycle+5` 为bank快照pre-NBA：Piano用tick后phase及active_table，Triangle用tick前phase；包络取更新至E+4的寄存值。效果接受沿是独立输入，默认例为tick+7，**不是本包预测出的真实板级延迟**。

四个不同基础频率的参考映射（Fs=48000为设计合同）：

| note | FCW | FCW×48000/2³² (Hz) |
| --- | ---: | ---: |
| 60 | 23409859 | 261.625561863184 |
| 63 | 27839171 | 311.126981496811 |
| 67 | 35075158 | 391.995437443256 |
| 70 | 41711627 | 466.163758188486 |

这些是独立振荡器的输入/相位频率；Piano/Triangle各自谐波不能当额外声部。R06实际bank没有纯正弦入口；旧8192纯正弦CSV属于另一输入日历，只按原范围引用，不能套本包或真实R06输出。

数值合同：`voice24 = ((signed_wave16 * unsigned_env_q15) >> 15) << 8`，负值右移向负无穷取整；四路signed32先求和，再饱和到[-8388608,8388607]，无除4。clip是严格超界，边界自身不算。R06板壳启动启用delay1、dry32767、wet16384、feedback0；两项乘积分别右移再相加饱和。历史按**被后处理接受的输入事务**推进，接受后取消发布也不回滚；只推进DSP但未被后处理接受的事务不改效果历史。enable0逐位旁路且不写历史；enable/length改变清历史，仅gain改变保留。模型不模拟外部buffer计数时序。

## 本轮实际软件验证

`run01/`：Python版本查询exit0；首轮新测试入口exit1，原因是原Triangle ROM含`//`注释而初版解析按全部空白分词。失败原双流、源SHA和 `EXECUTED_ORACLE_R01.py` 原字节保留。只修解析忽略行注释，ROM未改，随后使用新目录run02，不复用旧结果。

`run02/`：三个实际命令均exit0（原始版本输出为Python 3.10.2、13项新适配层测试、向量生成），源/依赖前后SHA相同。13项覆盖相位/音色、分配与generation、释放退休、取消两种效果接受路径、旁路/flush、负数floor、正负饱和边界、reset、缺第四路/错代数及非法/依赖漂移拒绝。这是新适配层的定向软件验证，不是旧T010/T023/T060专项复跑；收口时将先前误写的3.10.11按原双流更正，未改日志或重跑。

`run02/vectors/`：264条期望样本（两epoch）、11个输入事件；224行四槽占用、219行四路各有非零贡献，reset后8行静音。request99推进DSP但没有效果接受；100效果已接受但不发布，两者的后继历史不同。`EXPECTED_PCM.json`保留每路identity/generation/phase/wave/env/voice及混音/效果，CSV提供紧凑数值，`STIMULUS.json`给独立合成输入，`EVENT_DECISIONS.json`给分配判据。

`comparison01/`：一份合成相等输入exit0、漏第四路/左PCM一LSB差/错generation/错clip四个输入各exit1，5/5符合预期，命令和原始双流齐全。相等正例比较262条发布行（264条生成样本排除99/100两个不发布者），来自期望副本，只证明数值比较入口；**不是独立DUT正例**。`compare_math.py`只比较已归一化的数值行，不认证期望来源、真实capture或窗口完整性；M3仍需封存真实前门输入/原始trace和独立归一化映射。

复现命令（输出目录必须新建，不能覆盖封存原件）：

```powershell
& 'E:\python3.10\python.exe' -B -X utf8 'code/model/m1_r05_pcm_oracle_20261016/run_checks.py' --output 'code/docs/test/m1_r05_pcm_oracle_20261016/reproduce_unique'
& 'E:\python3.10\python.exe' -B -X utf8 'code/model/m1_r05_pcm_oracle_20261016/qualify_comparison.py' --vectors 'code/docs/test/m1_r05_pcm_oracle_20261016/reproduce_unique/vectors' --output 'code/docs/test/m1_r05_pcm_oracle_20261016/compare_unique'
```

工作目录为本仓根目录；实际绝对argv/cwd/二进制SHA和逐步骤耗时以原JSON收据为准，`-B`不写缓存。软件计时不是实时硬件deadline，也不证明从预检到封存的严格墙钟。

## 接真实R05/R06时的最小字段与容差

1. M2/M3给同次执行的R06/候选源、ROM、事件输入、工具、原始双流和完整窗口SHA；不能只传汇总或从另一干净目录取快照。
2. 从真实前门事件接受及可审核的调度规则，独立导出事件应用沿、slot/代数/音色、全部lane_tick、取消/reset与配置接受。不能用观测wave/env/table/phase填期望输入；当前公共observer不足以直接提供全部推导前提。
3. 按每epoch/req_id映射bank E+5期望，再按全部效果接受事务重建历史，包括不发布者；最后只对合法成功commit比较左右PCM24、clip、身份/generation。整数数值容差0 LSB；Piano/Triangle波形和ADSR不能只作“非零”判断。
4. 完整左右PT8211/I2S字及逐请求下一帧期限由M3现有C/A写集接续，本包不新增采集工具。真期限仍为commit_edge<next_frame_edge；缺下一frame或first_valid时保持UNKNOWN，不把max35/<834当每帧保证。

当前等级：来源/合同L0、纯软件参考生成与正反例通过；没有新RTL编译、模块仿真或真实DUT逐样本L3。M3既有指定L2和M2指定物理L5按原范围保留，board_release_allowed=false、T052 PARTIAL/旧4207 UNKNOWN不变。
