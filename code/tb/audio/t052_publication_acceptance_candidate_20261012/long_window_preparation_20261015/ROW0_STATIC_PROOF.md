# T052 row0 启动修复与静态调度证明

本件只完成 M2《T052 新长窗格式与执行监督限定决定》要求的首沿修复及软件先验，等级 L0。未启动 HDL 编译、RTL 仿真或 Gowin；不代表长窗真实采集通过。原静态 ZIP、旧 JSONL 合同、DUT/observer/ROM 不变。

## 最小修改

`tb_t052_long.sv` 的下降沿读行条件从 `driver_index < LAST_CYCLE` 改为 `($time > 0) && (driver_index < LAST_CYCLE)`。t0 的 `clk = 0` 即使由 X→0 触发下降沿回调，也不能增加索引或读下一行；不依赖初始化过程与 `always` 注册顺序，不使用仍处于 t0 的 `#0`。

TB 完整 SHA-256：`daf67848153214d791d1f51e348dbbe7c7995c06424f0a819a23080c1fba3e20`，2868 字节。

独立冻结 controls 身份仍是 `fd220e83da98c03f0181c0a45e4edfa2ddc77adda055911508e7f7469131d4d0`，375598784 字节、8536336 行。软件逐块读取原件，核 SHA/字节数/换行数，运行前后身份相同；不从 DUT 输出反推控制输入。

## 推导与绑定范围

`test_row0_schedule.py` 不调用 HDL 工具，不导入 DUT、observer 或原 checker；它先锁住以上 TB 完整文件 SHA，并要求去注释/空白后的 DRIVER 区域精确匹配封闭模板。不是通用 SystemVerilog 解释器。模板外的 task/时钟声明/结束及超时过程由完整文件 SHA 绑定；任何进一步源码变更需重新人工核模板与身份，不会自动获得证明。

初始化同一过程按顺序打开文件并读 row0，随后才进入 `forever #10 clk = ~clk`。t0 的所有回调都被时间条件排除；因此到 t10 之前没有第二次读行。第一正沿 t10 使用 row0；第一正时间负沿 t20 将索引变为1并读 row1。对 k=0…8536335，正沿时间为 `10+20*k`，相邻负沿 `20*(k+1)` 在两个正沿之间，且仅增加一次索引。最后正沿 t170726710 使用 row8536335；t170726711 结束，早于下一负沿 t170726720，不再消费额外数据行。末次 `$fscanf` 是 EOF 探测，要求返回-1，不计为读到额外行。

软件分别枚举 t0 回调未到达、已到达两种启动情况的全部8536336正沿，每种均核行号、读行数、相邻沿关系及最后结束位置。回调若发生在部分初始化之前，时间仍为0且直接被屏蔽；无需读取尚未初始化的 driver_index。此证明不涵盖外部文件损坏时正常运行（TB 应 fatal），也不证明 `$fscanf`、编译器、observer 或 DUT 在实际模拟器中的行为。实际首次编译/采集必须另由 M2 批准精确组合。

## 软件正负例与实际结果

共7例：精确源码/输入身份1例，两种全窗口启动调度2例，4个拒收例。旧无时间保护、只添加 `#0` 的变体均保存文本和 SHA，并同时给出首个反例：`edge=0 time_ns=10 expected_row=0 actual_row=1 reads=2`。二者分别报 `SOURCE_NO_TIME_GUARD`、`DELTA_TIME_NOT_GUARD`。另拒收时钟半周期改为11ns和缩窗1沿。变体是软件构造的源码反例，**未编译**，不是已验证可编译的 RTL 行为反例。

首次软件运行 `_01` 已通过；自审发现 Python `assert` 可能受 `-O` 影响、命令记录应采用真实 `sys.orig_argv`，因此在新目录 `_02` 验证增量。两次原收据/变体均保留，没有盲重试。最终 `_02` 状态 `PASS_STATIC_ONLY`、exit0，3.172秒。输出：`code/output/m3_t052_row0_static_20261015_02/receipt.json`。

在仓库根目录运行（输出必须为尚不存在的新目录）：

```powershell
& 'C:\Users\songdongkuan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -X utf8 code/tb/audio/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015/test_row0_schedule.py --controls code/output/m3_t052_long_preparation_20261015_03/prepared/controls.hex --output code/output/m3_t052_row0_static_20261015_02
```

已有 `_02` 原件不得覆盖；复现时指定另一全新输出名。本件无 Git 写入；由 M3 主窗口汇总 runner、完整 SHA 与软件失败原件，再交 M2 决定一次编译/运行。旧4207发布完整性仍 UNKNOWN，已签128沿不重跑。
