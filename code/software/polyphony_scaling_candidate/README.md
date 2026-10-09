# T061 唯一独立主候选（B0）

## 2026-10-10 新增 B2a 真实声音后端子阶段

新入口 `--stage b2a`，只读复用冻结 L 连续 ADSR/Pitch，独立 DDS 状态加共享实际
波表/Q15 gain/signed32 混音，先 N4 长程独立数学复算，再 N8/16/32 短程及慢后端。
最终合格运行 `code/output/m3_t061_b2a_final_20261010_01`：六配置、10,672 个完整结果，
两份实际编译行为反例、九份完整 capture 语义反例、六项新单测及仓库九门禁通过。
此为混合后端 L2/L3，**不是完整 B2/T061，也不是已实现32音演奏**。
MIDI/CC64/Release ACK、B1 持久状态接线和端到端服务上界仍未完成；无 Gowin/STA/设备测试。
合同、复现及覆盖缺口见 `code/docs/hardware/polyphony_scaling_v1/B2A_IMPLEMENTATION_20261010.md`
及 `DELIVERY_B2A_20261010.md`；新封存目录 `B2A_20261010/`，旧封存不改。
下文 B0/B1 历史说明不代表当前阶段只存在协议 mock。

## 2026-10-10 新增 B1 传输／存储 RTL 子阶段

已新增单一参数化 scheduler、双银行 statebank 和 tagged ROM fixture（不是音频计算）。
新入口加 `--stage b1`，输出仍必须为全新目录；默认 B0 模式及旧证据保持。
N4/8/16/32×ROM1/3、慢算子、公开端口回放及两个实际编译 RTL 行为变异独立验证。
源码/协议/排空参数/复现和明确未测项见
`code/docs/hardware/polyphony_scaling_v1/B1_IMPLEMENTATION_20261010.md`。
以下 B0 文本为旧阶段说明，不代表当前没有新 RTL；B1 的 task_complete 仍为 false。

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
入口 exit0 只表示 **B0 回执返修软件范围通过**，收据 task_complete 始终 false。
旧 B0_20261009 及原日志不改；新入口会原样读 Git 41d2871 两份旧源码，复现 M2 的8组问题，
再执行修版检查及两个仅内存中的 Python 行为变异（指定拒收 exit2），记录真实日志和SHA。

21 拍/voice 的序列化日历是下一步实现合同，所有适配耗时仍待 TB 实测。
原 pitch 算术 II1/消费延迟7 与外层包装最小 II8 分开记录。
原事件 drain、CC64 scan 和 backpressure 的总上界未知，整体始终 UNKNOWN。
慢算子/缺步骤/未知耗时/不匹配 ROM 端口或延迟均拒收或超期，不能自动补一拍。
串行 signed32 左右累加后一次 signed24 饱和；不多加 velocity 乘法。
JSON 单列树形替代方案全部 2×(N−1) 个 32bit 节点，不将深度当节点数。
逻辑存储 bits 不代表 FF 实占；DSP、BSRAM/SSRAM packing、mux/decoder/control 开销未知。

协议 oracle 检查每 N 槽恰好一次、完整 tag、重复/未发起/错代次/旧请求隔离、乱序返回、
完整结果提交前 scratch 隔离及原子帧期间事件锁。它不计算包络/Release/声音，不证明取消的 LFO 非回滚。
构造/replace/pedal/tag/N 严格拒 bool/float。result 身份非法返回 False，不靠异常拒收。
oracle 构造须显式提供 `drain_limit` 正整数（测试值不是硬件实测上界）。
cancel/reset/commit 后只要曾 issue 就保持隔离，三路 empty 同时确认前禁止新帧/换身份/控制更新；
超时锁闭，局部 reset 不绕过。详见 B1_CONTRACT 的补充节。
request/generation 回绕及完整 tag 复用依赖真实旧工作完全排空。若生产者谎报 empty 后仍吐同 tag，
软件无法辨别；该限制有显式测试，不宣称无条件 ABA 安全或实际事件服务已有界。

下一步 B1：独立 RTL scheduler/statebank/ROM 仲裁、实际 II/latency/端口测试、至少两个可编译行为变异。
再 B2：处理连续 ADSR/ROM 预取/事件准备的上下文语义，先 N4 对冻结 L 的逐样本等价，再 8/16/32。
本轮不使用那一次 Gowin 综合授权、不专门重跑旧夜间/波形/桌面压力；原源、旧证据和共享表只读。
`--repo-gates` 仍按既有入口执行仓库门禁，其中含原 T007/T019 编译/仿真；
runner 的 no_NEW_candidate_HDL 标记仅指本候选未编译新 HDL，不能理解为门禁没有运行既有 RTL 仿真。
