# 给 M1：138K 新板级双音色＋延迟的自包含 ModelSim 输入

待用户转发，尚未送达。这是 **M2 新组合可复现准备 L0**，不是M1原独立测试复跑或新整机RTL通过。

M2基线T056 `L_locations_guard065` 精确冻结输入/约束保持；M1 原封存包SHA `5c18926ae307301e91ec0e44dcf4a48b2fb57adec71ad46c494b14df59913b06` 读取并在**隔离副本**接原板级 MIDI/FIFO、I2S/PT8211。旧L整体L5不可迁移。M2本机Icarus第一次真实M1新全链编译在90秒上限被内部`voice_allocator_4.sv`结构体数组类型断言挡住，原结果与失败证据已V0329发布；另一个T062整机同类失败V0331保留。不运行失败残留`.vvp`，不自动提高时限。

**交付**：`M2_138K_M1双音色延迟_ModelSim自包含输入_20261015.zip`，273614 bytes，SHA-256 `9af00c82d6b7a7a0a74bd195c823fc117ece1db0ba67fc2eb620b10c09b619f7`；仓库相对路径为 `code/docs/evidence/m2_m1td_modelsim_input_20261015/M2_138K_M1双音色延迟_ModelSim自包含输入_20261015.zip`。

包内保留84输入文件原/staged SHA，对40个外部ROM字面量保存可逆重定位记录；编译清单69项包含真实M1音色/左右延迟、真实M2板级壳、原FIFO/I2S与名义PLL/DVI/厂商模拟模型及TB；不含真实硬件时序。解包后在 `inputs` 目录按README的ModelSim命令编译运行。R01只读预检发现TMDS_PLL生产IP与名义PLL仿真模型重名，已原件保留；R02只从仿真文件表排除两个生产视频IP，源仍在包中。R02独立检查69个输入源均存在、无绝对路径/缺include/缺ROM/模块重复，ZIP清单和CRC通过。另有随本仓库交付目录的 `verify_portable_inverse.py` 与 `INDEPENDENT_REVERSIBILITY_RECEIPT.json`：默认只核包内完整闭包；M2附原staged目录验证40处可逆路径、84源逐项字节、91ZIP成员及69编译源均通过。这些仍是静态检验，不代ModelSim实际结果。**本机未提供您原ModelSim 10.7工具身份、未实际编译/仿真。**由您先核包内MANIFEST、实际工具文件SHA/版本、预定子步骤≤300秒及全流程≤900秒、原始stdout/stderr/退出码与FATAL拒收规则后，在原隔离授权范围决定是否执行一次；无授权不启动、失败不自动重试/换工具。请只反馈新组合真实运行的首失败或完整正例；原A04/B01/EDGE01/CHAIN02旧组勿重跑。

此TB只检真实MIDI事件→M1模块→PCM/frame/PT8211连通、program0/1两个NoteOn后的活动声部与非零提交以及共享复位；不独立重算新组合PCM数学/BSRAM资源，不证明效果无爆音、新PnR/STA/实物。板级配置目前仅上电装入一个私有延迟参数，运行时配置切换和参数平滑仍待正式接口。**M2保留正式顶层/CST/SDC与后续物理准入。**