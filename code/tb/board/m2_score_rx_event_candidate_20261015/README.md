# 真实 T062 UART 双银行 RAM 到 M2 播放事件：独立 L2

2026-10-15，M2 私有接口增量，不改 T057 协议、T062 RAM、公共包/正式顶层/约束、M1 声音算法。T062 源与 `5e1d13c398fd1cf749c613a30b9238d1a46319b4` 的对应 blob 一致；底座40MHz，115200 8N1 真实串行输入，不缩短 bit 周期。输入仅为**合成测试曲谱**的两条事件（tick0 NoteOn69，tick16 NoteOff69，48kHz tick），并非用户网上下载的`.mid`。

独立仿真以原T057编码器产生严格BEGIN28/DATA30/COMMIT14三个完整串行帧；真实T062解析、ACK、同步公开读口、新M2私有播放器、统一事件消费者一并编译仿真。最终正例 `_02`：Icarus compile0/sim0，无超时，3个ACK、一次score来源ALL_NOTES_OFF、两条NoteOn/Off、两次真实公开读、624个音频frame使能、late0；源/工具运行前后SHA同。错读银行仅启用**真实T062 `score_byte_lane.sv` 的 MUTANT_RAM_READ**，compile0/sim1按 `REAL_RAM_SCORE_RX_EVENT_BAD` 拒收；runner总退出0表示目标反例被拒收。工具各步≤90秒，总≤300秒，失败不重试/提限。原首轮 `_01` 与负例 `_01` 留作开发历史，最终同源回合以 `_02` 为准。

复现（从仓库根目录，每次给全新目录）：

```powershell
python -B -X utf8 code/scripts/run_m2_score_rx_event_20261015.py --output code/output/NEW_SCORE_RX
python -B -X utf8 code/scripts/run_m2_score_rx_event_20261015.py --mutant --output code/output/NEW_BAD_READ
```

**范围**：此L2证明真实UART/双银行RAM发布后到公开演奏事件的隔离数字子链，仍**没有**实例化原四声部/32音音频核心、PCM帧缓冲、PT8211/I2S或正式板级顶层。私有“COMMIT即播放”和source_id2未定版，M3真实下载`.mid`未交，BLE/FPGA实物/资源/40MHz STA不签。此前V0331私有**整机**尝试在旧`voice_allocator_4.sv` Icarus类型断言处编译超时；这份受影响范围较小的新证据不回填那个失败，也不意味着曲谱已经发声。下一次必须把同一精确RAM/播放器对接正式演奏核心并独立核事件→PCM/ID→实际串行帧，不借旧STA。证据包另封存原命令、stdout/stderr、退出码、源与工具SHA。