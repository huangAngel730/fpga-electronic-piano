# Tang Mega 138K L路径适配工程

本目录保留60K正式工程`code/build/electronic_piano.gprj`不变，只为已签收的
`L_locations_guard065`候选提供可迁移的本机路径副本。路径适配不是新功能、正式集成、
新一轮Gowin结果或上板放行。

源基线固定为：

- 提交：`0bb5c66862dcbd9dc3894b055d9703e2b3cd0e76`
- ZIP：`code/rtl/138K_try/hold_trials_20261005/M3_138K_Hold修复证据_20261005.zip`
- ZIP SHA256：`c4eeefac8c28e3ebc01475177601a65abfc0da6f314b1c80f94b223ee9fa5b50`
- 候选：`L_locations_guard065`
- 器件：`GW5AST-LV138PG484AC1/I0`，数据库索引`gw5ast138c-007`

原GPRJ的47项文件路径和9份RTL内部ROM/include路径均绑定M3机器。适配脚本从封存
ZIP逐项核对56个输入SHA，在Git忽略的`staged/`中保留原字节，只对9份RTL副本机械
替换候选根路径，然后生成本机绝对路径GPRJ、`run.tcl`和`receipt.json`。原候选目录
不会被写入。

在仓库根目录执行：

```powershell
python -B -X utf8 code/scripts/prepare_138k_l_project.py --prepare
python -B -X utf8 code/scripts/prepare_138k_l_project.py --check
```

成功后工程入口为：

```text
code/build/138k_l/staged/audio_visual_coexistence_top.gprj
```

本阶段只允许静态生成和检查。不要自动执行`run.tcl`；启动Gowin综合/PnR前应另行确认
板型B/C与底板电气、工具路径、输出目录和验收范围。不得把旧L报告写成此适配工程的新
构建结果，也不得烧录。
