# E2 首失败与修复历史（永久保留）

## ROUND_01：编译展开失败，未仿真

- 源/工具/输入身份：`ROUND_01/before.json` 与 `after.json` 完全一致；消费1/6。
- 命令、机器、cwd、起止、原双流：`ROUND_01/compile.launch.json`、`compile.receipt.json`、`compile.stdout`、`compile.stderr`；argv为冻结的7个stage源码，退出码2，无超时，编译0.078s。
- 首差异：TB第13行使用 `queue_level`，声明在第21行，Icarus 14无法绑定（原stderr共2个展开错误）。没有运行VVP，不能算负例PASS。
- 最小修复：只把TB的 `wire [15:0] queue_level` 前移到首次使用之前；wrapper、旧模块、参考、输入、黄金、坏例判据不变。旧TB完整原件在ROUND_01/stage/s06.sv和execution_sources/，未覆盖。
- 下一轮：不同源的ROUND_02，同600s总上限/六轮共同台账；成功即停。

## ROUND_02：首包被 TB 的有符号哨兵误拒

- 消费2/6，输入/工具身份稳定。compile退出0、stderr空；positive退出1，无超时。命令与双流在ROUND_02/，首拒收 `DELIVERY_SEQUENCE_OR_EPOCH`，t=12507000ps，requested=observed=1、delivered=0。
- 定位：seq是unsigned32，`last_delivered=-1`为signed integer；比较时-1转换为FFFFFFFF，首seq=0也满足`seq<=last_delivered`。A/O原件显示首包是seq0、左右0且已入队，不是桥丢样。
- 最小修复：单调性比较增加`delivered!=0`首包保护，仍保留范围、入队、逐字段身份判据。之后已有包时last_delivered始终非负，无符号转换不改变顺序。旧原件保留，wrapper/旧模块/输入/黄金均未改。
- 下一轮ROUND_03，仅不同源定向验证；不更改负例首诊断。

## ROUND_03：限定隔离验收通过，停止试错

- compile=0，positive=0，独立check_capture=0，negative_1..5均为预期退出1；无超时/崩溃，源码/输入/工具前后身份完全一致，总174.531s。
- 五个首拒收依次为PIXEL_REFERENCE、WINDOW_FRAME_TEAR、SAMPLE_SEQ_GAP、RESET_TRACE_STALE、AUDIO_DISPLAY_BACKPRESSURE。首失败与两次修复完整保留，不抹去前两轮，也不将它们记作负例PASS。
- 本包消费3/6，成功即停；剩余3轮不继续运行、不迁移给其他任务。没有新增旧专项/EDA/硬件调用。
