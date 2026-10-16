# 夜间任务2 A：R02真实采集完成，待C独立消费

本轮用户授权在总控最新原文核实，授权单见 coordinator/night_20261016/RESUME_R02/AUTHORIZATION_AND_DISPATCH.md。A本轮限定观察接线修复、真实采集和原件交付完成，实际L2；不替代C独立PCM/PT8211判据、M2整机签收或实物验收。未提交、未推送，Git发布由总控负责。

## 修复与实际结果

- 仅将隔离板级观察副本的 `wire night_committed_clip` 移到generate前；相对R01 FIX02只有一行声明移动，相对FIX03_PENDING完全同字节。config两线也在generate前；其余新增night观察信号均在首次使用前声明。未修改算法、ROM、时钟和正式接口。
- 使用原固定ModelSim SE-64 2020.4及原EXE/DLL SHA，正常提升审批获准。新R02只消费第1组，vlib/vlog/vsim均exit0，组4.437秒；没有第2/3组。原R01三组仍为已消费，无重用。
- 原stdout精确PASS：`PASS M2_M1TD_REAL_CHAIN_BOARD_FUNCTIONAL_ONLY`；真实摘要 accepted=6、active=4、commits=303、nonzero=258、frames=303、serial=3905、max_cycles=35。vlog 8条/vsim 7条告警均为13314默认端口var语义提示，Errors=0；原双流完整保存。
- 主capture和inputs各253456个连续TICK；303笔音频请求与303次commit一致，无pending尾项，全部有下一真实frame边界且在其前提交，最大35拍。833/833/834帧分布一致；该观察窗clipped均为0，无削波覆盖结论。
- 此次第1绝对沿12500ps即满足all-known且reset低，startup_edges=0，主相对cycle1=绝对cycle1。两份startup侧车保留HEADER/END，原始boundary由模拟器写出；未删行、补零或后裁剪。虽然前缀长度为0，startup仍按合同UNKNOWN_NOT_SIGNED。
- MAIN输入保留t0原始状态、88个MIDI边沿、2个raw-reset边沿和全部同沿记录；两条采集reset逐沿一致，终段复位得到2个epoch。
- A自检验证25份执行源码快照、90个stage输入、12份原双流的原字节/SHA和运行前后身份；工具前后身份一致。`git diff --check` exit0。

## C入口与合同差异

先读本目录 CAPTURE_READY.json，按其中精确身份取 RUN_01/RUN_RECEIPT.json、REAL_CAPTURE/REAL_INPUTS、两startup侧车、STARTUP_BOUNDARY_RAW及STARTUP_BOUNDARY.json。源码快照仍为FLAT_RELATIVE_SHA_MAP_V1，映射完整。完整命令、cwd、时间、双流、exit、Python和EXE/DLL身份均在原run receipt；本目录NIGHT_RUN_RECEIPT.json作总交付入口。

STARTUP_SCHEMA.json仅producer_observer/producer_board两条来源路径改为R02，字段、宽度及分段语义未改；精确STARTUP_SCHEMA.diff及新SHA列于READY。C应核差异后更新自己的新副本来源pin，不借用过期pin。CAPTURE_INTERFACE.md仅把已消费R01额度说明改为R02新三组首过即停，采集选择规则不变。

## 失败历史和边界

旧R01 RUN01准备路径过长未消费；RUN02编译未声明config线、RUN03公开端口unknown、RUN04 clipped连续64沿Z均保留在原R01失败包。旧RUN03的“复位初始化导致”仅为当时假设，持续Z观测和本次只移声明即通过支持观察线作用域是阻断；不将它归咎冻结算法。R02准备时裸python命中不可访问WindowsApps别名，未创建工具进程；改用上轮记录的既有miniconda Python后准备通过，未变更ModelSim工具。

旧失败原件、已暂存文件未改。真实工具正例与旧真实失败证据同包可查；不为凑负例再启动仿真。C独立串行解码待总控唤醒；first_valid未导出、模拟起音≤10ms、PLL/HDMI物理行为、STA、Gowin综合/PnR和硬件均未新增验证，board_release_allowed=false。不能把A限定L2写成整机通过。

## 接手

总控核原件后唤醒C真实消费，并衔接ABCD；M2保留最终同版复核。正式发布时间、门禁、编号和共享状态均由总控/M2办理。本窗口任务已完成并按首过即停，不继续花剩余2组。
