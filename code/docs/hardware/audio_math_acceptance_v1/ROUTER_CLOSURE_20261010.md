# T060 四声部独立路由参考层交付

2026-10-10，M3；D043/D044 A 三处授权范围，基于本地/远端相同的 cc86bd5。
这是当前冻结 H/capture2 的最小参考实现，不是新生产路由器或32音实现。
完整 T060、A1/A2 关闭由 M2 复核；本候选完整入口保留退出3和三项 complete=false。
旧96b364a及原失败、原JSONL/F、旧清单、旧报告/载体不修改。

## 实现及独立性

- `router_model.py`：只接受 R 复位、E 已接受事件、K frame 与 J 真实 sample request，
  只读 velocity ROM。R/E/K/J 是输入边界，不验证 UART/parser/FIFO 是否正确地产生 E。
- 4槽同身份重触发优先→最低空槽→LRU秩最旧；source4/channel4/note7，generation32逐槽回绕。
  被偷旧身份 NoteOff 不命中新身份。释放槽仍占用，直到独立 ADSR 的 state==0触发回收。
- CC64 >=2048 按 source/channel 保存256组逻辑状态，延迟 NoteOff、抬踏板按槽扫描；
  pending generation 固定直到 ACK，不接新事件；panic全局释放。内部 controller 与 allocator
  合并为参考生命周期对象，只适用受仲裁的单接受事件顺序，不作为任意内部端口状态的形式证明。
- router逐拍保留 ALLOC_SEND/APPLY、CTRL、RELEASE_SCAN/SEND/APPLY/ACK、RETIRE 的 NBA先后。
  先检查模型pre-state/脉冲，再推进；release_done 由独立包络公共idle产生，非观测STATE回填。
  对无事件间隙，只在包络全部流水register tuple固定点且路由/采样idle后跳拍；逐拍等价自检覆盖。
- 当前 bank 采样时序由 WAIT_DISPATCH→7拍SETTLE→Q、Q+14 D、Q+20 H 推导。
  不从 Q/D 倒推出事件或 sample tick；原记录所有对应边沿必须严格一致。
  新frame撞正在计算的MATH显式报未覆盖，未实现泛化的控制/数学流水排空模型。
- `compare_router` 逐条比较 N lane/cycle、Q occupancy/source/channel/generation/base/note、
  D request/cycle、全部 STATE 触发/占用/身份/请求及九项包络字段，不跳过闲置lane。
  `timeline` 再使用预测 N/Q 和预测 tick/on/off、预测实际cycle计算 DDS→ROM→gain→mix→PCM。
  旧 `router=None` 组件路径没有独立路由结论；正常 CLI 必须经过新层才可退出0。

## 来源与时钟标签

数学/时序来源为冻结 H 的 `polyphonic_event_router.sv`、`voice_allocator_4.sv`、
`sustain_controller.sv`、`sustain_control_contract_pkg.sv`、`polyphonic_envelope_bank.sv`、
`adsr_piano_envelope.sv`、`audio_defs_pkg.sv` 和原ROM。56只读源/模板/证据输入及7ROM
与任务基线6f3e813 LF身份逐份核对，实际raw/LF SHA另列最终receipt，不复制修改生产源。

M2已确认 generated TB SHA f6af9b1a8cc54eb73012d4b36709da60da655360ae78c0a392edca12e32316b1，
embedded observer SHA 1b67aa7dd264cef48c866c546435b42ca353f1b6239607708453f65c6ef32f1e。
该既有确认写入新收据，不重开观察来源请求，不改旧件。
独立 FSM 推出两个物理 off 沿：epoch1/cycle1023197/lane1/gen1、cycle1254337/lane3/gen1。
两条恰好为打印新值；on打印0/1分布6/8，tick按lane分布3800/6148（按组950/1537）。
old/new 只解释同沿活动区计数标签，模型绝不平移物理事件来迁就输出。

## 验证与原始证据

最终入口输出 `code/output/m3_audio_router_final_20261010_01/receipt.json`。
命令、cwd、Python3.11.2及exe SHA、当前HEAD、源/ROM/capture/日志SHA、真实stdout/stderr、
逐步退出码和elapsed均由runner实录；最终数字和门禁以该收据为准。

正常capture2：68接受事件、14 N、2488 Q、2487 D/提交、9964 STATE。
独立恢复7空槽分配、2重触发、5偷音、3命中NoteOff/2未命中、2踏板延迟、2 off、4RESET。
原轨迹没有 retirement；不得把合成回收项计作原capture实测。
包络89676字段、H波表/包络各9948lane、左右PCM4974次精确比较；原轨迹削波0。

新增16项自检：LRU及1000事件秩不回绕、重触发generation、旧身份off、Velocity0、
source/channel踏板隔离及2047/2048、延音重触发、旧generation完成取消、pre-NBA回收延迟、
panic扫描、release中重触发、generation wrap、非法输入/反压、稀疏vs逐拍、
独立非零包络4800 Release tick回收、reset取消、非路由控制和runner elapsed硬限。
与既有44项合计60项；69项旧合成指定诊断保持。

原56完整损坏输入仍逐一指定诊断拒收（exit1），不能以超时/导入错误/缺文件充数。
新6项保留完整END：错N lane、错Q占用、错Q generation、off改on、off错物理沿、
同源PCM768→769；两可执行Python行为变异：LRU取最新而非最旧、忽略踏板，
原capture经相同checker分别被 ROUTER_N_LANE_OR_EDGE／ROUTER_STATE_COUNT 指定拒收。
这些是模型/checker反向覆盖，不是新RTL变异仿真。

开发探针保存在 `code/output/m3_audio_router_probe_20261010_01`，不覆盖。
最终收据封存后任何执行源变化必须重新运行，不用开发探针替代正式门禁。

## 边界、状态和交接

5个F END内部诊断计数与2条fixture切换旗不可推导，保持严格类型/范围和可重算4计数，
不硬编码Golden。真capture未含回收完成或panic；这些只有合成模型测试。
本次是新增Python自检及原RTL capture独立参考比较（限定离线L3），不是新音频RTL仿真、
综合、STA或硬件实测；没有安装/烧录/串口/接线。T061声音算子与32音另任务。
完整T060暂保持待M2收口；请M2决定诊断排除项及回收覆盖是否需最小补采，当前不自动重跑RTL。
本任务禁止改共享登记表，因此状态只写本授权文档，统一登记交M2。

## 复现

在仓库根目录，安装好的Python，无第三方包；输出必须不存在：

```powershell
& 'E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe' -B -X utf8 code/scripts/run_m3_audio_math_acceptance.py --bundle-root 'E:/FPGA/GAOYUNFPGA/CallBack/M1_138K40_audio_V0208_M2复核反馈_20261009' --repo-gates --timeout 1800 --step-timeout 900 --output code/output/m3_audio_router_REPRO_NEW
```

外层预期exit3＝等待M2闭合，绝不把它描述为整任务PASS；正例/回归子任务exit0、负例exit1。
总<=1800秒、单步<=900秒；新router每个子进程<=30秒、子流程<=300秒；退出0但墙钟超限也拒收。
只允许新output，不复用旧目录，不安装工具或产生设备动作。
