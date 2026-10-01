# CC64 独立延音控制交付

日期：2026-10-01；实施：M3；复核与正式接入：M2。

依据 `code/docs/CC64_延音控制开工接口合同_2026-10-01.md` 和接口 v1.6。
模块行为只延后 Note Off 的 Release 请求，不冻结包络，不修改已有 ADSR 曲线、
时间、幅度、PCM、时钟或分配算法。当前正式路由尚未连接本模块。

## 文件与编译依赖

| 文件 | 作用 |
| --- | --- |
| `code/rtl/input/sustain_control/sustain_controller.sv` | 四物理槽、256 来源/通道踏板状态及 Release 握手 |
| `code/tb/input/tb_sustain_controller.sv` | M3 补充：代次回绕、重复命令、背压、全局清音、停钟异步复位 |
| `code/rtl/input/midi_input/midi_event_parser.sv` | 使用公共 `make_sustain_event()` 输出 CC64 |
| `code/tb/input/tb_midi_cc64.sv` | 全 16 通道/128 值、Running Status、Realtime、异常和 FIFO 边界 |
| `code/tb/input/tb_midi_input.sv` | 真实 8N1 串行输入，保留 Note 回归并新增 CC64 四边界值 |
| `code/scripts/run_cc64_input_sim.ps1` | 三个 M3 TB 的 Icarus 自检入口 |

M2 已提供的只读依赖按以下顺序编译：`audio_defs_pkg.sv` →
`sustain_control_contract_pkg.sv` → `sustain_controller.sv`。
include 路径需包含 `code/rtl/board/`，端口直接引用
`sustain_controller_ports.svh`。本交付未修改以上公共包、端口文件和 M2 合同 TB。

## 输入与状态

解析器仅新增 `Bn 40 vv`，来源沿用 `SOURCE_ID`，通道沿用 `n`，统一事件为
`EVENT_CONTROL_CHANGE/CTRL_SUSTAIN`，`control_value={vv,vv[6:2]}`；
其他字段清零。raw 0/63/64/127 对应 0/2031/2064/4095。
其他 CC 仍完整消费但不输出，CC123 不擅自映射为全局 PANIC。
FIFO 满时保留已有事件并累计溢出，CC64 与 Note 使用同一队列、保持原顺序；
串行发送端不可反压，实物验收应确认溢出为零。

controller 所有端口均为同一 50 MHz 域。低有效 `rst_n` 异步断言，
同步释放由上游保证。四个物理槽各保存来源、通道、音符和 32 位 generation。
踏板位按 `{source_id, channel}` 独立索引。

- NOTE_ON：覆盖槽身份/代次，置按键保持，取消该槽旧 deferred/releasing。
- NOTE_OFF：身份和代次全部匹配且键仍按下才处理；踏板下则 deferred，
  踏板上则提出 Release。重复、陈旧或已 Release 的 OFF 无作用。
- PEDAL：阈值 2048。松开只释放该来源/通道已经松键的 deferred 槽；
  仍按住的键保持，重新踩踏板不会复活已经 Release 的音符。
- RETIRE：只有匹配的 releasing 槽才能回收；自然静音的 held/deferred 槽不回收。
- PANIC：清所有踏板和键/deferred 状态，对尚未 releasing 的 occupied 槽
  一次提出 Release；等实际 RETIRE 才回收。保留原 ADSR Release 行为。
- 复位：立即清全部槽、踏板和未确认 Release 请求。

`release_mask` 和 `release_generations[32*i+:32]` 保持到握手，
非 mask 槽的 generation 为零；generation=0 是合法代次。
`cmd_ready=rst_n&&!release_valid`，Release ACK 同拍不接新命令，下一拍才接。
generation 只比较相等，回绕允许；M2 不得保留跨 2^32 次重新分配的旧通知。

## 实际验证

仓库根目录运行：

```powershell
python -X utf8 code/scripts/prepare_sustain_contract.py --controller code/rtl/input/sustain_control/sustain_controller.sv
.\code\scripts\run_cc64_input_sim.ps1
.\code\scripts\check_repo.ps1
```

本机 WindowsApps 的 `python` 别名不可执行，实际第一条使用
`C:\Users\songdongkuan\miniconda3\python.exe -X utf8`，其余参数相同。

已执行 L2 结果：128 个映射阈值检查、M2 的 7473 拍独立合同向量 PASS；
M3 parser 2058 个完整事件/4134 项检查 PASS，UART 44 项检查 PASS，
controller 补充 47 项检查 PASS。Icarus 的公共包 timescale 和
always_comb 常量选择敏感列表提示不影响比较结果。

仓库 `check_repo.ps1` 全部 PASS（本次进程 PATH 前置现有 Miniconda，
避免 WindowsApps 别名）。Verilator 独立 controller lint 退出 0，
本模块没有新增警告；只读公共包原有 timescale/位宽/未用常量警告保留。
M2 合同原始日志和 `summary.json` 位于被忽略的
`code/output/sustain_contract/`，其他自检输出由上述命令直接复现。

## M2 接入及后续实物验收

1. 将已消费的 CC64 事件映射为 PEDAL 命令；Note On 分配结果携带新 generation。
2. Note Off 先匹配身份再交 controller，不能提前令 allocator 进入 Release。
3. Release mask 逐槽送 allocator/ADSR，整组完成后 ACK；期间禁止槽重新分配，
   PCM 采样继续。不能把 `cmd_ready` 或 `release_ready` 接成音频时钟使能。
4. 实际 Release 完成携带原身份/generation 发 RETIRE。原包络已 IDLE 的松键
   也须完成 Release 请求/RETIRE 握手，不等待不存在的包络状态转换。
5. 全局清音映射 PANIC；局部 CC123、断线恢复、复位触发和正式事件路由由 M2 定案。

当前验证限于独立数字控制 L2，未跑新增模块的 Gowin 综合/PnR、未改变正式工程、
未下载踏板功能码流；资源、50 MHz 时序、音频无阻塞和实际延音效果待 M2 接入验证。
二值延音不代表半踏。控制通过后用 M2 正式同源码流测试“踩后松键保持、
松踏板释放、仍按住键保持、重复踩松、重触发/抢占、全局清音”，记录码流提交号
及原始 CC64 字节。T024 四声部测试可独立继续，不能用其结果替代踏板验收。
