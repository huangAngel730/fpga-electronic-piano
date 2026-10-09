# T061 唯一独立主候选（B0）

当前仅实现冻结 L 的状态/ROM 清单、条件周期日历和 Python opaque-payload 协议 oracle。
不是可综合 scheduler/statebank，不计算新音频，不能证明 32 复音、N4 等价或 40MHz 时序。

建议单套分时完整上下文 engine。主候选选择不决定正式工程采用路线。
先保存全部 voice context（含包络私有 4bit 状态及连续流水工作副本），不凭假设删除寄存器。
256 组 source/channel 的控制和 CC64 状态固定保留；每 voice 的 source4/channel4/generation32 保留。
共享 ROM 的 L fraction 地址置换保留，不能用 H capture 的地址顺序代替 L。

运行（仓库根目录，Python 3.11；不安装依赖）：

```powershell
python -B -X utf8 code/scripts/run_m3_polyphony_scaling_acceptance.py --output code/output/m3_t061_b0_20261009_01 --repo-gates
```

输出必须为新目录。总上限 1800 秒、每步 900 秒；Windows 超时仅结束该子进程树。
入口以 Git `6f3e813` 和原 input_manifest 双重核对 56 输入及 7 ROM，并前后核源不变。
其中仅 lfo/oct/sub 三份 ROM 按既有 V0208 的精确 LF carrier SHA 在内存恢复 CRLF 后核原 SHA；不改原件。
报告由同一个 Python 对象产生 JSON/Markdown；所有命令、原 stdout/stderr、退出码、耗时和 SHA 入收据。
入口 exit0 只表示 **B0 范围通过**，收据 task_complete 始终 false。

21 拍/voice 的序列化日历是下一步实现合同，所有适配耗时仍待 TB 实测。
原 pitch 算术 II1/消费延迟7 与外层包装最小 II8 分开记录。
原事件 drain、CC64 scan 和 backpressure 的总上界未知，整体始终 UNKNOWN。
慢算子/缺步骤/未知耗时/不匹配 ROM 端口或延迟均拒收或超期，不能自动补一拍。
串行 signed32 左右累加后一次 signed24 饱和；不多加 velocity 乘法。
JSON 单列树形替代方案全部 2×(N−1) 个 32bit 节点，不将深度当节点数。
逻辑存储 bits 不代表 FF 实占；DSP、BSRAM/SSRAM packing、mux/decoder/control 开销未知。

协议 oracle 检查每 N 槽恰好一次、完整 tag、重复/未发起/错代次/旧请求隔离、乱序返回、
完整结果提交前 scratch 隔离及原子帧期间事件锁。它不计算包络/Release/声音，不证明取消的 LFO 非回滚。
request/generation 回绕时，RTL 必须保证旧事务已清空或在途上界，不以 Python 宽度检查代替证明。

下一步 B1：独立 RTL scheduler/statebank/ROM 仲裁、实际 II/latency/端口测试、至少两个可编译行为变异。
再 B2：处理连续 ADSR/ROM 预取/事件准备的上下文语义，先 N4 对冻结 L 的逐样本等价，再 8/16/32。
本轮不使用那一次 Gowin 综合授权、不专门重跑旧夜间/波形/桌面压力；原源、旧证据和共享表只读。
`--repo-gates` 仍按既有入口执行仓库门禁，其中含原 T007/T019 编译/仿真；
runner 的 no_HDL 标记仅指本候选未编译新 HDL，不能理解为门禁没有运行既有 RTL 仿真。
