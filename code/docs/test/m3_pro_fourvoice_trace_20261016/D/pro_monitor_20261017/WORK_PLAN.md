# M3：Pro接入被动监视器准备（2026-10-17上午）

用户本轮要求结合M1/M2/M3任务继续推进Pro适配。优先做基础四声C/D的具体缺口：旧C/D只有Python夹具，没有可直接接M2隔离测试台的端口监视器。M1仍管算法黄金，M2仍管Pro顶层/PLL/CST-SDC/PA控制及正式身份；本包只观察公开端口，不驱动或修改生产逻辑。

本轮新工作限于既授权D写集的pro_monitor_20261017子目录：software为执行/封存，tb/board为被动监视器与自检，docs/test为方案/合同/原件。旧C/D/E1–E4、旧源ROM/封包/消费记录只读；昨夜五小时时间盒已结束，原轮数不重置、不借用剩余额度。此次只验证新监视器，不重跑旧303或任何旧专项。

本轮时间盒90分钟，最多3轮针对新检查器具体缺陷的定向自检，首次通过即停；Python单组90秒，现有已核身份Icarus编译/夹具组240秒。只有当前新开发所需的普通离线检查；ModelSim/Gowin/综合/PnR/STA/码流/设备0。输出独占，首失败保留。没有M2精确Pro源与端口映射时结果只能签监视器自身的合成端口夹具，pro_dut_pass=false、board_release_allowed=false。

拟交付：公开frame-request valid/ready/id/payload和四lane、result/commit PCM-ID-clip、frame_tick、reset/cancel、PLL lock/audio_stable/PA_EN的被动检查；833/834节奏及严格小于833拍提交；原始逐沿CSV与机器化首差异。PA只检查“未安全时必须关”，不替M2规定何时开或复制控制器。序号/状态来自观测，算法PCM正确性归M1；没有源/映射不签真实Pro。

本轮同时交明确的三人不抢写任务建议及M2接入所需字段。自审后按精确树九项门禁普通发布；真人M2消息待用户转发，不因发送给夜间AI窗口冒称已通知M2。不得编辑当前状态/任务看板。
