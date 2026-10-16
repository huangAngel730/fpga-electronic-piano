# A：R05 真链／隔离观察后继

2026-10-16 收尾，主控统一发布，本窗口未提交／推送。**A整体 PARTIAL／BLOCKED_TOOL，不是R05通过**。
`board_release_allowed=false`。没有 Gowin、真实 R05 编译／运行或设备操作。

## 当前结论

- 冻结输入：R05 ZIP `dcf15f5d3ded1a0b160f55eab43066c728f80b3c329c44ea9f099c63f178696a`，
  273908字节，92成员／manifest91；69编译单元、9 ROM、2 include。TB SHA
  `6e677154d0a53ff97e794555ef57695e385a9963de43f1ac9135a54c32fc9777`。
- 84个物理输入身份可对应：69项原字节一致，15源码／40处ROM路径重定位可逆恢复到原物理输入收据SHA。
  R05还包括TB／GSR／clock／DVI模拟支撑和compile.f，不把这些额外成员当真实物理源。
- 已按最新四包／夜间授权接纳 **ModelSim SE-64 2020.4作为独立候选身份**；原10.7门槛不再作为权限阻断。
  但已知本机E盘2020.4安装的受监督版本探查仍报 Windows `WinError 623`（系统DLL重定位），
  没有取得成功版本输出、license或编译结果。局部PATH前置和提高沙盒执行身份对照均未解除，故停止真链。
  不更换工具、不修改安装／系统缓解／license、不盲重试；具体根因尚未证明。
- 真链功能命令 `vlib work`、`vlog -sv ...`、`vsim ... run -all` **启动次数0**；没有创建真实消费标记。
  既有版本探查记录不当作真实R05执行，更不能写成六份功能日志齐全。新授权不重置旧R04/T052等额度。
- 最终软件轮 `SOFTWARE_02`：36个外层软件子进程，20项 unittest 方法，退出0，总3.937秒；
  90秒/步与300秒总预算内，无外层超时。unittest另有4个Python假工具父进程、1个假孙进程，均单列原收据；
  合成进程树timeout和日志上限命中是**预期负例**，不是ModelSim或RTL超时。
- 独立账本合成正例：2600连续沿、3接受／2提交／1帧围栏取消，833/833/834分布；
  最大接受→提交15拍。仅软件夹具，不是实际四音声音、真实R05 capture或模拟≤10ms。

## 目录和入口

仅修改本目录、`code/tb/board/m3_r05_functional_integration_20261015/`、
`code/docs/test/m3_r05_functional_integration_20261015/`（排除主控coordinator）。其他窗口成果只读。

| 文件 | 作用／等级 |
|---|---|
| common.py、input_binding.py | exact ZIP/manifest/69单元/ROM/物理身份绑定，L0/L1 |
| receipt_check.py、receipt_cli.py | 独立单步双流错误即拒，真PASS与END只可来自vsim同一原stdout |
| audit_receipt.py | 六原始流／命令／SHA／工具版本／消费完整性，只能CONSISTENT_PENDING_M2 |
| windows_job.py、supervised_process.py | Windows suspended-start Job、进程树硬超时、原始双流／限量 |
| runner.py | 精确2020.4预检与唯一真实轮入口；本机已阻断，当前不再执行 |
| public_ledger.py、ledger_cli.py | 独立逐请求／帧／提交／reset寿命账本，缺下一实际帧保留UNKNOWN |
| run_software.py、test_software.py | 合成完整正负例与Python假工具自检，不运行RTL |
| 两个新SV文件 | 冻结frame core→冻结PT8211和公开observer的L0接线候选，**尚未编译／仿真** |
| seal_delivery.py | 只读验证已有软件结果与原件，封存，不借旧结果验证新增脚本 |

已执行（勿重复真工具预检）：

```powershell
& 'C:/Users/songdongkuan/miniconda3/python.exe' -B -X utf8 code/software/m3_r05_functional_integration_20261015/runner.py --output code/docs/test/m3_r05_functional_integration_20261015/RUN_01 --execute
& 'C:/Users/songdongkuan/miniconda3/python.exe' -B -X utf8 code/software/m3_r05_functional_integration_20261015/runner.py --output code/docs/test/m3_r05_functional_integration_20261015/PREFLIGHT_2020_01
& 'C:/Users/songdongkuan/miniconda3/python.exe' -B -X utf8 code/software/m3_r05_functional_integration_20261015/runner.py --output code/docs/test/m3_r05_functional_integration_20261015/PREFLIGHT_2020_02
```

三份原receipt均 `BLOCKED_TOOL`／Python合同退出2，PowerShell外层工具报告退出1；不把外层shell码改写成Python码。
第一份在旧10.7合同下探查E/D两个已知位置，各尝试一次`vlib -version`；后两份在2020.4新授权下各只探查E同一EXE，
后者是受限沙盒外的诊断对照，仍保留同工具与原失败。四个版本探查启动链均报623，原流为空，退出码未取得。
旧启动器未记录API内精确失败位置，因此**版本进程是否短暂创建UNKNOWN**；并无任何功能编译命令被调用。
随后修正新监督器对“CreateProcess成功、后续AssignJob失败”也立即计创建的边界，仅以Python假工具验证，不再探查ModelSim。

软件实际命令：

```powershell
& 'C:/Users/songdongkuan/miniconda3/python.exe' -B -X utf8 code/software/m3_r05_functional_integration_20261015/run_software.py --output code/docs/test/m3_r05_functional_integration_20261015/SOFTWARE_02
```

所有子进程精确argv/cwd、原始stdout/stderr、退出码、输入/执行源/依赖SHA见原receipt，不只给摘要。
软件合成日志不是`vlib/vlog/vsim`真实日志。`Errors: 01/0001`混真PASS均拒，`Errors: 0/00/000`不误拒；
缺PASS、跨双流拼PASS、Failure/FATAL、非零、timeout、X摘要、834拍、漏沿／ID／clip／欠载均有正负例。

## 未验与下一责任

原R05 TB只有active/commit/nonzero/serial计数及END/PASS。它不能证明四个独立频率各自发布到输出，
不能生成逐请求ID、首次valid、clip或BCLK/WS/DIN完整轨迹，`max_cycles<834`仍是DUT自报。
新public候选只读连接frame_core公开port；首次valid／内部取消握手未导出，不填造。协议是PT8211 LSBJ，低WS为右、
32槽每半帧、最后16位有效，不套Philips I2S。

本窗口不改算法、ROM、正式top、CST/SDC／接口，不做E复制工程，因为目前不是接线决策阻断而是工具启动。
下一步需在独立可核的2020.4工具环境解决实际启动／库／license后，重新核授权及共享消费状态，再决定是否启动剩余首轮。
不可解释工具崩溃／许可问题不符合第二修复轮条件，不能擅自借第二轮重跑。
C的真实新模块夹具证据独立交付；不能用它代签A真链、正式生产四音、物理STA或模拟端到端延迟。

当前HEAD `8b64a352464932a28df565038cafc8d623dea5c9`；中断前开工HEAD874c097。消息／文件待用户转发，尚未送达。
