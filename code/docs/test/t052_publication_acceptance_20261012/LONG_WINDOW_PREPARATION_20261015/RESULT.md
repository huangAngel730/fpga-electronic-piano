# T052长窗静态准备实际结果

日期：2026-10-15。实际状态：静态准备完成，实际长窗执行待M2放行；完整T052仍PARTIAL，旧4207发布完整性UNKNOWN。

## 本轮范围与结果

- 新增独立固定输入/FSM日历、流式事务checker、薄TB/公开端口observer、工具资格与准备入口、使用说明和执行请求；只写三个新长窗子目录。
- 17项纯软件自检全部PASS，实际退出0；手写256沿前缀的独立预期15/9/6，并非旧128沿RTL重跑。错误ready、错发布沿、取消沿误发布、重复ID错serial、错epoch、缺沿/END、假计数、错时间/reset等均按指定诊断拒收。
- 完整8536336沿输入生成退出0，375598784字节，SHA-256 `fd220e83da98c03f0181c0a45e4edfa2ddc77adda055911508e7f7469131d4d0`。两个先后准备版本的输入SHA相同；最终以`m3_t052_long_preparation_20261015_03`为准。
- 独立静态总账A/P/C=8207/8201/6、open=0。末posedge时间170726710ns，末沿后1ns结束；不是实际RTL采集计数。
- 实际工具元数据：Icarus及VVP `14.0 (devel) (s20260301-474-g5591c2dde-dirty)`；两个`-V`查询均退出0。编译器SHA `5c1f4e38c6dc0807aeab8814d63af97313bef5813e815e17021ae8e36e0a0bab`，VVP SHA `d38cc76e6946136aaf46db8a3bf34bec2a54bad564dfe146686579ca2d39c9ed`。
- 源码/工具静态库存前后SHA核同；库存覆盖bin DLL、lib DLL、ivl文件和两执行文件，实际动态加载闭包未观测，原始库存与版本双流在tool_metadata收据中。
- 仅本任务软件L0/自检；新长窗HDL编译0、RTL运行0、Gowin/EDA0、设备0。发布门禁的既有烟测另列，不能冒充本次长窗结果。

## 实际命令与原件

仓库根目录执行：

```powershell
$py = 'C:\Users\songdongkuan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -B -X utf8 code/software/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015/run_preparation.py --output code/output/m3_t052_long_preparation_20261015_03 --m1-confirmation 'E:\FPGA\GAOYUNFPGA\Callback3\chat6\M1给M3_T052长窗输入与事务确认_20261015\M1_T052_长窗输入与事务确认_20261015_R01.md'
```

实际退出0；其software_tests、tool_metadata、prepare三个子步骤均退出0，未超时。精确argv/cwd、耗时、输入/源码/工具身份及原始stdout/stderr见封存包`run/receipt.json`、`run/software_tests/receipt.json`、`run/tool_metadata/receipt.json`和`run/prepared/proposal.json`。

第一轮隔离九门禁在`2744ca670ae90bea82753a9b4b41c49d09ce0c46`基线上退出0、9/9 PASS；后续增加工具版本查询/依赖库存后，最终发布树另做一次门禁，原日志和实际结果随独立门禁收据交付，不以第一轮代签新增代码。

封存入口（输出文件须全新）：

```powershell
& $py -B -X utf8 code/docs/test/t052_publication_acceptance_20261012/LONG_WINDOW_PREPARATION_20261015/seal_delivery.py --run code/output/m3_t052_long_preparation_20261015_03 --output code/docs/test/t052_publication_acceptance_20261012/LONG_WINDOW_PREPARATION_20261015/T052_LONG_STATIC_R01.zip
```

封存包含完整controls.hex压缩原件、M1输入确认文档、冻结依赖、独立预期账本、新源码、17项自检/工具资格/准备原日志及manifest；解压会展开约375.6MB的控制文件，不要按ZIP压缩大小估算磁盘。没有合成观察轨迹冒充实际capture。归档CRC和每成员SHA均由封存入口独立重读核对。

## 修订与失败历史

1. 第一版手写软件自检14项通过。随后补实际每沿64位时间戳、CRLF适配和3个额外边界检查，17项通过。
2. 第二版完整输入/独立账本及17项自检通过；随后补两次工具版本查询，并把静态依赖库存从bin/ivl扩展到lib DLL，最终第三版重新记录源/工具前后身份并通过。
3. 首次创建隔离发布worktree因Windows文件名过长退出1；Git自动撤销目标路径，随后仅本次命令用`-c core.longpaths=true`重建成功，不改全局配置。首次Git错误保留在本对话工具记录，未另保存原始双流文件，不伪造完整本地失败原件。
4. 本次软件自检及准备入口没有失败后盲重试；旧版本输出均保留，未覆盖任何旧capture或封存。

## 待验与M2接手

请M2先复核紧凑全沿日志布局、853万沿/约650MB观察规模、90/300/300s及总900s提议、执行来源绑定和消费标记/进程树/文件上限监督，再决定单次编译和单次真实RTL采集的新许可。现有原始capture入口即使事务匹配也退出3，等待批准runner收据认证来源。

TB/observer未编译，语法/调度/运行表现待验；四声部PCM数学、active/clip、真实声音、I2S/PT8211、40MHz整机、STA、模拟输出和实物均未验证。两份可编译RTL行为反例尚未实施/运行，不以17项软件坏轨迹替代。

M1确认的50MHz/1042拍/倍频FCW纯DDS隔离源，与138K R04/40MHz/ADSR/音色/效果的非倍频合同分开适用；不修改任一算法定义。若M2要求改短窗、分批或频点，需M1给新输入版本。

本次不取号、不编辑共享状态表。功能提交与普通推送的精确SHA在交付消息中提供；包内形成期状态不用于证明远端发布。待用户转发M2，尚未送达。
