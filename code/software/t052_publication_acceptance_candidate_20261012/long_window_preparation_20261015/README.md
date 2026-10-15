# T052 新长窗 R01 静态准备

本目录对应 M1 确认的 `T052_LONG_50M1042_FROZEN_FCW_R01`。只准备独立输入、逐沿公开端口观察、事务检查器、源/工具身份和单次执行提案；当前实际等级为 L0/纯软件自检。没有编译或运行新 RTL，旧4207条完整性仍 UNKNOWN，已签128沿不重跑。

输入确认原件 SHA-256：`56574246ebd7fe75bf59ea7f583ffe2c00f5593b8567230dbb6992cfe857b555`。

## 使用

在仓库根目录使用已有 Python 3.12：

```powershell
$py = 'C:\Users\songdongkuan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -B -X utf8 code/software/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015/run_preparation.py --output code/output/m3_t052_long_NEW --m1-confirmation 'E:\FPGA\GAOYUNFPGA\Callback3\chat6\M1给M3_T052长窗输入与事务确认_20261015\M1_T052_长窗输入与事务确认_20261015_R01.md'
```

输出目录必须全新，重复路径直接拒收。入口依次运行17项软件自检、两次`-V`工具元数据查询及完整输入生成，保留运行前源码快照、stdout/stderr、命令/退出码/耗时和源前后 SHA。生成完成返回0只表示静态准备成功；`proposal.json` 始终 `execution_authorized=false`。

单独自检：

```powershell
& $py -B -X utf8 code/software/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015/run_checks.py --output code/output/m3_t052_long_software_NEW
```

未来原始 capture 离线比对入口：

```powershell
& $py -B -X utf8 code/software/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015/check_capture.py --capture code/output/ACTUAL_NEW_CAPTURE --report code/output/NEW_CAPTURE_REVIEW.json
```

此入口检查全8536336沿，没有短窗 CLI 开关。可证实矛盾返回1；缺文件、缺沿、缺END返回3；即使事务比对全通过，当前原始日志入口仍返回3 `PROVENANCE_NOT_VERIFIED`，需另外的获准执行收据绑定准确输入/工具/产物，才能签实际 RTL 结果。测试内部256沿手写夹具不属于真实RTL或旧128沿复跑。

## 文件职责

- `plan.py`：独立固定输入和冻结FSM日历。期望接受不读取 DUT ready，按 `[epoch, accept_serial, req_id]` 关联；取消不回滚接受，异步reset在断言时取消。
- `check_capture.py`：流式逐沿检查输入/时间/ready/valid/ID、完整发布及取消账本、异步reset、END和五段接受/发布覆盖。所有期望在读取对应观察行之前独立计算。
- `test_long.py`：从M1前缀表手写期望事务和公开端口窗口；17项正负例，包括静默漏接受、取消沿发布、重复ID串号、提前valid、错时间、缺沿、缺END、伪计数、漏reset等。
- `prepare.py`：核归档与成员SHA，只从冻结ZIP提取DUT/DDS/mixer/ROM；生成完整输入与预期账本；盘点工具并输出锁闭提案。
- `qualify_tools.py`：仅运行固定`iverilog -V`及`vvp -V`元数据查询，保存真实版本文本、二进制/静态DLL与ivl文件库存；不编译HDL或运行`.vvp`。
- `run_checks.py`、`run_preparation.py`：保存真实软件运行原件，失败即停，不原样自动重试。
- 对应新TB/observer：`code/tb/audio/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015/`。

## 三轨迹和异步复位

新格式 `T052_LONG_PUBLIC_HEX_V1` 只改变日志表达方式，不改变M1输入。

1. `controls.hex`：独立计划，全8536336行，每行43个小写十六进制字符+LF，170位由高到低是 `rst_n/frame/cancel/req/id32/enable/mask4/fcw0/fcw1/fcw2/fcw3/ready`。
2. `observations.hex`：实际公开输入与输出，每行75个十六进制字符，300位由高到低是 `cycle32/time_ns64/controls170/calc_ready/result_valid/result_req_id32`；最后必须是 `END 8536336`。接受LF或CRLF，不接受空行、未知值、少沿、重复沿或尾随数据。
3. `publications.jsonl`：实际ACCEPT/PUBLISH/CANCEL，`event/cycle/time_ns/key`；CANCEL另有`reason`。唯一END包含rows/A/P/C/open。异步reset的CANCEL时间取实际断言时刻，而非下一个posedge。
4. `resets.jsonl`：额外独立reset轨迹，应精确出现`(time_ns,cycle,rst_n)=(0,0,0),(80,4,1),(2560,128,0),(2640,132,1)`。初始化X→0单独记录，后续高→低才开启epoch2。

计划与观察分开：TB只从controls.hex流式读取，初始化应用row0，随后每个negedge应用下一行；观察器在posedge PRE-NBA采公开端口。观察器按实际ready标记候选接受，checker按冻结FSM独立推导必须接受的集合，因此DUT静默丢接受不能通过修改账本自洽。

## 规模与边界

- 输入：375598784字节；全观察约648761548字节（LF）／657297885字节（CRLF上界，具体以proposal公式为准）。发布账本约16415行，另有4条reset。
- 建议捕获上限750 MiB、全输出上限1200 MiB，工作盘至少预留2 GiB；不生成巨大逐像素或信号波形。
- 提议compile≤90s、run≤300s、check≤300s、总≤900s；它们只是待M2确认的上限，不是性能测量或已获许可。runner墙钟/文件上限监督与消费标记需要后继精确绑定。
- 当前不验证PCM数值、左右样本、mask实际声音贡献、active/clip或频谱；不重算旧数学。四次独奏与合奏的控制覆盖只能证明输入与事务，不等于声音数学/实物四音通过。
- 50 MHz固定1042拍对应理想采样率约47984.6449Hz；不是138K/40MHz的833/834拍合同，亦不是精确48000Hz实测。
- M1保留八度倍频FCW，并要求独奏+合奏。现场不能只以四个峰推断四独立声部；正式138K非倍频输入不受本准备覆盖。
- 缺工具、版本未知、动态DLL未观测、没有approved runner receipt均必须明示；静态库存是superset而非真实加载记录。

## 执行门槛

M2须决定精确源码/工具版本与依赖、日志格式、一次编译+一次运行的范围和资源上限，并签发新的许可。不能复用已消费的128沿或T060许可。当前软件只输出提案，不提供会启动HDL的执行按钮。

未来两个行为反例建议分别为：有效结果提前一沿；接受后静默漏发一次。它们需在获准的新范围中编译成功，再由本checker指定拒收；当前仅软件损坏轨迹已测试，不能声称这两个RTL反例已运行。
