# T057/T062 曲谱公开读口→统一演奏事件：M2 私有隔离候选

2026-10-15。此模块没有进入正式顶层，不改原T057协议、T062新同步RAM、公共包或声音算法。当前状态：**隔离RTL L2通过，RAM→UART→播放→PCM→I2S完整链没有验证，资源/40MHz物理STA和实物均未验。**

## 精确接口和政策

- 40MHz音频core单域，异步断言/同步释放低有效复位；`frame_tick`为原I2S 48kHz**完整帧脉冲**，其余时间不使用系统拍代样本tick。
- 输入T062已提交银行的 `committed_valid/count/score_id/commit_pulse` 和公开单拍读口 `rd_req/rd_index→rd_valid/rd_event`。8字节 `<IBBBB`按 little-endian tick、kind、channel、note、velocity解释；转换为原`audio_defs_pkg::performance_event_t`，来源ID2**只是私有提议**，尚未正式分配。
- 私有政策：每次COMMIT先请求score来源的ALL_NOTES_OFF，待该事件握手后从tick0开始计时、读取新bank；同沿或在途的旧bank输出均丢弃。按原按键/MIDI FIFO在先、score在后仲裁；score事件与ID背压保持，两个同tick事件不丢；迟到按消费时的tick关系计数，但不会回压I2S帧。非法读口记录或欠缺应答锁错并再次发本来源panic，不把坏事件送入演奏核心；复位清状态。
- COMMIT触发播放**只限此私有候选**。T057没有PLAY命令，公开开始/停止策略和来源编号需要M2受控接口决定。不同来源的音符仍可能在声部满载时相互抢占；优先权指同时事件的FIFO仲裁，不承诺实体声部绝对隔离。

## 可复现边界

```powershell
python -B -X utf8 code/scripts/run_m2_score_playback_20261015.py --output code/output/NEW_SCORE_RUN
python -B -X utf8 code/scripts/run_m2_score_playback_20261015.py --mutant --output code/output/NEW_BAD_BANK_RUN
```

原数据与工具SHA写入独立新目录receipt，工具每步≤90秒、总≤300秒、无自动重试。最终正例 `_04`：编译0、仿真0，旧score 2条已消费、旧tick2尾事件在新COMMIT后不得播；新score tick0 NoteOn 与tick2 NoteOff、MIDI对panic同沿优先、背压保持、非法kind拒收/score panic/复位清零均通过。变体 `_04`只将**同步RAM公开口模型**在第二银行返回旧银行事件，编译0/仿真1，以`SCORE_STALE_BANK_OR_ID`拒收。原 `_01`–`_03` 成功过程只是逐步加严TB刺激，最终以 `_04`同版源码为准；不重跑旧T057/T062专项。

模拟的RAM读口遵从T062下一拍返回及COMMIT同沿旧bank语义，但**没有实例化真实T062接收器，更没有真实115200 UART帧或下载`.mid`**；不是实际上板播放L5。曲谱真实来源应是用户从网络下载的`.mid`经M3导入为严格T057记录，手写夹具只用于开发。下一步把此候选与精确T062 RAM和现有顶层仲裁接入，补同步读地址/COMMIT切银行/多个同tick/实时MIDI压力、统一事件→PCM/ID→I2S端到端和至少一项可编译RTL行为错误；正式顶层/约束变化及新资源STA由M2单独验收。