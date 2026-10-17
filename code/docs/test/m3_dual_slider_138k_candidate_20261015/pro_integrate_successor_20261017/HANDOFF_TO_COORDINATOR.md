# 夜间任务4：task-day E1本地最终领取单

**限定静态准备DONE_L0；正式Pro接入PENDING_PRO_SOURCE_OR_PRODUCERS，board_release_allowed=false。** 本轮2/2新静态软件组已消费并成功停止。未提交、未推送、Git写入/index/门禁/编号/状态修改0，交夜间任务1统一汇合发布。按总控最后通信指令不再主动发消息；本文件存在不等于总控已领取/处理，真人M2仍待用户转发，尚未送达。

目录：`code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017/`。先读README、INTEGRATION_DIFF、CDC_PATHS、WIRING_PROPOSAL；实际RESULT/FINAL_RECEIPT/PACKAGE_STATUS在根有成功同字节入口，原报告在RUN_02/products。PUBLISH_FILE_LIST.json为新增文件清单，明确排除INPUT_ORIGINALS/**，**勿整目录暂存**本地42件旧输入副本。封包只含新增静态增量及首失败，不含旧已签案例/旧zip。

原件包本体：`RUN_02/products/M3_E1_PRO_INTEGRATION_STATIC_DIFF_20261017.zip`，160415字节，62成员；SHA256 **13f0839a5b58c622f551c08dd5bdafbbb12029fdcdb7efe1d3a3f753757042d3**，manifest SHA **8d1b4de60e1f90dfb562150517afd9ab96065a7b7a3d7d3e07e8def6857e93dd**。成员字节/SHA/CRC全部核验。当前RUN的seal.*、FINAL_RECEIPT、PACKAGE_STATUS、成功根别名与发布清单为外部封存回执；本领取单也在zip封存后新增，不冒称包内成员。

实际文件：三份差异/可逆提案、START/消费/自审/失败/通信范围说明、INPUT_SPEC/INPUT_IDENTITIES/范围库存、32锚点规格与核验、READ_ONLY_REFERENCES/源索引、audit_static.py/run_static.py/seal_static.py、两轮冻结执行源/命令/原双流/退出/前后身份。没有新RTL/TB，不创建空目录。旧M2源/PLL/CST/SDC、旧pro_parallel/formal_geometry、M1模型均未改。

来源：开工实际HEAD414e1a9d3ee0617c5e8ba72dd4b22c36122c9926，跟踪/index无变化；本窗未fetch，不声称核过当前GitHub实时指针。两份task-day原件SHA为4142a701d0f48c3965c0596641be859d85cf7788b2d17d5d3af64f0e1745af75及7235fb23d4584687259d2743aaa4b91a517e2b5bd3dc8867f0e29857f3b14033。42件原件字节身份、105项明确范围库存、32处原文行锚均核对。旧L2包SHA2de22e136aa074604407592b7df91af9ff2db05357b1d508a61de9ec7c313757/129成员仅只读核身份及CRC，旧487/4未重跑。

新增关键结论：当前board外壳SHA6eca6bb7…17d2390为50MHz/双输出PLL；M2所引用旧R05封存壳SHAdf1f05b4…10a5cf才是40/25/125MHz闭接，旧_06输出目录本体不存在，不能混源当新Pro。旧top接受复制点在679–682，正式Pro对应点仍UNKNOWN。候选事件桥u_events与旧SDC u_event_bridge不同；七组首级/二级与64/98bit静态路径已精确列映射，但新网表实际命中/优化位/完整STA未知。旧SDC payload定向setup2、hold0；7组hold是同步器二级。正式mode、score与frame epoch均未批准，TB current_frame+120只属测试；mode常量1载荷可能优化，不能机械填一条物理路径。

实际执行：Python3.12.4，EXE SHA4e5a83fcdcd12bcb9ae4dc98c5405effe35dc5ac10d89982c6a6a3646493f88a，python312.dll SHAd9438d6b474a6c5d7bc9271b77b2da9f08a5b7ac32dc9dd4b75061a6dd8da078；完整加载模块/EXE/DLL依赖SHA见RUN_02/before.json与after.json，前后一致。外层命令：既有Python `-B -X utf8 code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_integrate_successor_20261017/run_static.py`，cwd仓库根；内部冻结脚本精确argv/cwd/PID/UTC起止/原stdout/stderr/退出/上限与SHA在RUN_nn/audit.*及seal.*。Job Object挂起attach后resume，单组总90s及北京14:04:35共同上限。

首失败RUN_01 audit=1/seal未运行，0.860s：scanner_origin范围16–34少第35行，被原文门禁拒收；唯一修正范围35并同步差异表，未改源码或判据。原stderr SHAe83df6730d992b932a288e751ddafd43c91e3e7cc088e79de305173873945baf，全部首失败/执行源/原规格原字节保留。另修runner收据快照完整性和第二轮序号，不扩大来源判断。RUN_02 audit=0、seal=0，1.172s，0.218s/0.141s调用，无超时，源/工具稳定，2/2成功即停。新功能正负例/RTL、ModelSim/Icarus/Gowin/PnR/STA/设备均NOT_RUN；自有只读子智能体无运行，无审核员制度。

下一责任：M2先冻结新Pro source/ROM/top/PLL/CST/SDC/trace与目标闭包，并决定mode来源、score来源/note_id/帧零点epoch、真实接受点及共同复位/唯一显示出口。正式顺序允许后只在新副本替换CDC+scene，保留PLL/核钟/scan/RGB寄存/TMDS唯一角色，按新网表核七组/64/98bit及完整Setup/Hold/Recovery/Removal。M1核同源音频不退化判据；M3在精确同版.fs/恢复SHA、电气及本次SRAM许可齐备后采实屏音画原件。旧命中闪光FAIL暂缓，不能升级完整双模式/Pro/实屏/板测。
