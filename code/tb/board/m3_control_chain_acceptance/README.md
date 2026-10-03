# M3 控制联合验收（任务 A）

2026-10-03，依据 `3f62a12` 任务单；仅测试文件，验证等级 **L2**。
不修改生产 RTL、公共包、算法、顶层、工程、约束或编号表。

## 执行

仓库根目录：

```powershell
python -X utf8 code/scripts/run_m3_control_chain_acceptance.py
.\code\scripts\check_repo.ps1
```

默认使用本机 ModelSim SE-64 2020.4。可用 `--modelsim <win64目录>` 指定工具路径；
`--timeout` 为单次运行的秒级上限。保留 `--simulator icarus --cad <目录>` 入口，但本轮
该组合未完成验证，不能把 ModelSim 的结论记成 Icarus 已通过。
每次建立新的 `code/output/m3_control_chain_*` 目录，保存编译/运行日志、逐事务 capture、
实际源 SHA-256、模拟器版本、覆盖统计及日志 SHA。生成文件不提交。
缺源文件/ROM、空 capture、缺结束标记、异常输出、超时或行为不符均非零退出。

## 连接与记分规则

50 MHz 单时钟、低有效复位。实际串联：两份当前 MIDI 字节解析器（source 0/9）或
真实 `midi_input`（source 3、31250 baud）→ 公共 32 深度 FIFO →
`performance_control_snapshot` → 候选四路 `pitch_mod_snapshot_pipeline`。
解析器的 1 kHz 参数未缩短。另一路是明确标记的 TB 竞争事件生产者，
为全部 256 身份注入控制及合法/非法范围事件，不代表实物来源或生产路由。

独立 Python 解码原始 MIDI 字节，逐来源核对 Note/CC64/Program 离散顺序及完整
64 位事件；连续值只要求合法映射、合并后最终值到达，不强加跨类型到达顺序。
FIFO 入队和出队逐条比对；256 身份参考控制表只由 FIFO **输出握手**更新。
Program 原始编号 0～127 保真，不改变 Pitch/Mod 表，不自行决定音色政策。

四槽 occupied/source/channel/generation/base 均为 **TB 声部夹具**。
请求 E 握手同时冻结 base，直到快照被 FCW 消费者握手；E 后改 live 身份和 base
模拟抢占，不能改变旧事务。快照检查 E+4，FCW 结果检查消费请求后 E+7、逐样本
调用已签收 M1 `PitchModVoice`；取消后的运算不回滚 LFO。
同拍/异拍 NoteOn 都是单拍脉冲。层级 LFO 相位只作附加 once-only 检查，
主体结论来自输出 FCW 与完整请求标签，不例化第二份算法 RTL 作 oracle。

`manifest.json` 与 seed 20261003 固定场景和 xorshift base 序列。
候选默认 LFO_INC=447392、MOD_DEPTH_MAX_Q10=512，与模型显式默认一致；
Mod 非零时 bend=0 或 range=0 不作为强制旁路。5 Hz/±50 音分是候选口径，
不是用户最终冻结的产品策略。

## 实际结果

最终 ModelSim 实跑目录 `code/output/m3_control_chain_t5hbsn_1`；
仓库九项门禁全 PASS，日志位于 `code/output/m3_control_chain_nqtxmedu/repo_gate.log`：

- 1270 条公共 FIFO 接受事件，235 条原始 MIDI 离散事件，128 种 Program 编号。
- 878 次快照请求，874 次 FCW 计算，858 次成功消费；差额来自刻意取消/复位。
- 256 个身份，2899 个非零 Pitch/Mod 占用槽计算；6 项 MIDI 最终合并值检查。
- 576 个 cadenced 请求，间隔严格为 1041/1042；同/不同身份四槽和空槽均检查。
- 满 FIFO 同拍 pop/push 151 次，快照读取期间事件反压 4 拍，结果背压 46 拍；
  同拍控制写入与请求 1 次，未接受控制排除场景通过。
- 8 个取消场景；四个快照读取阶段、八个 FCW/held 阶段复位与恢复通过。
- 真实 50 MHz/31250 UART 混合 Pitch、CC1、Program、Note On/Off、CC64 通过，
  两个字节源另外覆盖 Running Status 和 F8 穿插，全部输入错误/溢出计数为 0。
- 三个反例先编译成功，再分别由相位断言/独立 FCW oracle/请求标签检查拒绝：
  held-valid 重复推进 LFO、使用 live base、破坏请求 id。

工具输出与进程退出双重检查，原始日志和源 SHA 在 evidence.json 中。
这不是正式音频路由、键盘变调/颤音/切换音色、Gowin、PnR、STA 或实物验收。
后续由 M2 复核、取验证编号、更新看板并负责正式连接；T036 不因此关闭。
