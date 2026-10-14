# T057/T062 曲谱公开读口→统一演奏事件：M2 私有隔离候选

2026-10-15。此模块没有进入正式顶层，不改原T057协议、T062新同步RAM、公共包或声音算法。当前状态：**隔离RTL L2通过，RAM→UART→播放→PCM→I2S完整链没有验证，资源/40MHz物理STA和实物均未验。**

## 精确接口和政策

- 40MHz音频core单域，异步断言/同步释放低有效复位；`frame_tick`为原I2S 48kHz**完整帧脉冲**，其余时间不使用系统拍代样本tick。
- 输入T062已提交银行的 `committed_valid/count/score_id/commit_pulse` 和公开单拍读口 `rd_req/rd_index→rd_valid/rd_event`。8字节 `<IBBBB`按 little-endian tick、kind、channel、note、velocity解释；转换为原`audio_defs_pkg::performance_event_t`，来源ID2**只是私有提议**，尚未正式分配。
- 私有政策：每次COMMIT先请求score来源的ALL_NOTES_OFF，待该事件握手后从tick0开始计时、读取新bank；同沿或在途的旧bank输出均丢弃。按原按键/MIDI FIFO在先、score在后仲裁；score事件与ID背压保持，两个同tick事件不丢；迟到按消费时的tick关系计数，但不会回压I2S帧。非法读口记录或欠缺应答锁错并再次发本来源panic，不把坏事件送入演奏核心；复位清状态。
- COMMIT触发播放**只限此私有候选**。T057没有PLAY命令，公开开始/停止策略和来源编号需要M2受控接口决定。不同来源的音符仍可能在声部满载时相互抢占；优先权指同时事件的FIFO仲裁，不承诺实体声部绝对隔离。

## 新增：实 T062 接收器到统一事件的隔离子链（2026-10-15）

已在**不实例化音频核心**的独立L2检查中实际运行 T062 新双银行 RAM、原UART
接收/回复、M2播放模块和公开演奏事件消费者：72测试输入字节按115200/40MHz原
347拍位时序发送，BEGIN/DATA/COMMIT三个ACK、一次同来源panic、tick0 NoteOn69
和tick16 NoteOff69、两次同步公开读及624个完整音频帧使能通过。
`MUTANT_RAM_READ` 真实RTL错读银行变体编译0/仿真1定向拒收。最终证据ZIP
`code/docs/evidence/m2_score_rx_event_20261015.zip` SHA
`114f3bdaf43a090a115bf028ccb909dcc9b562721d490a0fc859793dceb4a8c7`。
这是 UART→RAM→统一事件 **子链**，不证明曲谱PCM、I2S或用户下载文件；下面
记录的“原整机接旧声音核心编译阻断”仍原样有效，不因较窄子链通过而消失。

## 实 T062 UART 接收器同版联调的当前阻断

M2 在旧 `138k_night_cache_combo` 62 个输入原字节的**私有顶层副本**中，把原固定
`rd_req=0` 改接本模块，生成T057小型测试曲谱（BEGIN28/DATA30/COMMIT14字节），
只在输出目录把两个绝对include字面量变成同内容相对include。第一次准备因顶层guard
计数过严退出，第二次准备完成（没有改变原文件）。第一次实际编译在旧include路径
拒收；第二次在受控90秒上限内，由**基线**`voice_allocator_4.sv:37` 的Icarus
变量类型错误与`elab_expr.cc:3088`断言卡住，90.047秒超时，runner非零。**VVP
未启动、无实际UART/PCM/串行结果，未自动重试/提时限。**原62输入/工具前后SHA同，
失败证据原件在 `code/docs/evidence/m2_score_board_real_uart_failed_compile_20261015.zip`
（SHA-256 `a0eb25fddd7235a4fd0094314efe5c2b4632fa09fe325d01839433d36c7e7bcf`）。
这是整机工具/基线兼容阻断，不是本模块播放语义被真实RAM拒收；模型L2维持原范围。
下一步须独立核定实际可用兼容仿真工具或由声音源负责人确认最小受控兼容改法，
用**同一精确顶层新尝试**验证真实UART→读口→事件→PCM/I2S；原失败不可回填PASS。

## 可复现边界

```powershell
python -B -X utf8 code/scripts/run_m2_score_playback_20261015.py --output code/output/NEW_SCORE_RUN
python -B -X utf8 code/scripts/run_m2_score_playback_20261015.py --mutant --output code/output/NEW_BAD_BANK_RUN
```

原数据与工具SHA写入独立新目录receipt，工具每步≤90秒、总≤300秒、无自动重试。最终正例 `_04`：编译0、仿真0，旧score 2条已消费、旧tick2尾事件在新COMMIT后不得播；新score tick0 NoteOn 与tick2 NoteOff、MIDI对panic同沿优先、背压保持、非法kind拒收/score panic/复位清零均通过。变体 `_04`只将**同步RAM公开口模型**在第二银行返回旧银行事件，编译0/仿真1，以`SCORE_STALE_BANK_OR_ID`拒收。原 `_01`–`_03` 成功过程只是逐步加严TB刺激，最终以 `_04`同版源码为准；不重跑旧T057/T062专项。

模拟的RAM读口遵从T062下一拍返回及COMMIT同沿旧bank语义，但**没有实例化真实T062接收器，更没有真实115200 UART帧或下载`.mid`**；不是实际上板播放L5。曲谱真实来源应是用户从网络下载的`.mid`经M3导入为严格T057记录，手写夹具只用于开发。下一步把此候选与精确T062 RAM和现有顶层仲裁接入，补同步读地址/COMMIT切银行/多个同tick/实时MIDI压力、统一事件→PCM/ID→I2S端到端和至少一项可编译RTL行为错误；正式顶层/约束变化及新资源STA由M2单独验收。