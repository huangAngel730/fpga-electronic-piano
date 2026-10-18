# R10 C9执行申请输出域适配

当前 STATIC_READY_NOT_RUN。夜间2只新增本 admission 软件/文档；候选未导入、编译、AST解析或运行，未跑旧114例或drill；不写Git、不联网、不碰HDL/EDA/设备。沿用夜间1的主Goal、21:52 START和2026-10-18 02:52截止。N10-M3-LINK的一组≤120秒及首具体缺陷一次≤60秒由夜间1唯一冻结/执行，成员不消费。

入口 `adapter.py: build_application(request:dict, out:Path)->dict`。out必须是 `code/output/m3_c9_chain_night_r10_20261017/` 的严格子目录且尚不存在，旧D4根、其他根和R10根本身均提前拒收。CLI为 `adapter.py --request APPLICATION_REQUEST.json --output NEW_DIR`，完成申请退出3、拒收退出2；CLI保留有界/重复键/非有限JSON拒收。

适配器仅在被调用时读取固定SHA `ae4ad0f3fefa1bc28e099a2aabcb827f733358d9bd93988af31e5de20a824ccf` 的原C9 assembler源码，在新命名空间编译加载，__file__仍为原路径，唯一逻辑全局覆盖为OUTPUT。原模块/原源码/共用helper不改，不调用旧selftest。原72+3编译单元、86个decision载荷（84 inputs+2 provenance）、封套manifest、9ROM/2头/别名、工具/窗口/计划比较、原子申请占用及所有许可限制全部沿用原函数。该函数只组装申请，不执行商业工具。

成功后原 assembler 的 RESULT.json 原样保留，另生成 OUTPUT_SCOPE_DERIVATION.json 和 ADAPTER_RESULT.json；返回值沿用原artifacts并增加 output_scope_derivation（path/bytes/sha256）。始终 PENDING_M2_EXECUTION_ADMISSION / execution_allowed=false，未取得真实执行权或M2冻结。

APPLICATION_REQUEST复用既有实际C9源包、ROM、driver/observer/TB、原R6-2 plan/bytes/reset/ready、实际工具身份和外部白名单。source/tools/external_inputs与旧实际申请同值；只换本轮window引用、唯一CAPTURE_ID `C9_R10_PROPOSAL_20261018`、STOP_ID、新nonce及对应完整argv/proposed_plan。未产生新MIDI黄金、第二observer或FRAME生成器，不要求已存在首次真实trace。

WINDOW_PROPOSAL状态是 **PROPOSED_NOT_M2_FROZEN**。同源clock_plan_sim.v静态模型初始0，首core上升12500ps、周期25000ps；driver同相。reset.drv原release800/1002480、第二assert1000480，结合2级reset_sync及PRE_NBA，候选观测release为802/1002482。这些仅为源码推导，并非仿真/板测事实或FROZEN_FRAME_INPUT。STOP1130660后，TB248–251先等driver负沿再等core负沿，两者同相，存在finish1130660/1130661两分歧；选旧+1（1130661）只是待批精确argv候选，不能消除竞态或称已经验证。M2必须明确冻结调度/相位/窗口后才准许HDL执行。

三个新接缝用例由 `selftest.run_case(case_id,out:Path)->dict` 提供，out必须不存在：一次实际申请在新R10输出域装配及非合成请求/提案一致性；旧D4输出拒收；R10根本身与其他根拒收。CASES记录各自expected，BINDING记录最终源码/输入SHA。不是重跑旧组件自检，正例也不将文件结构通过升级为真实capture/数字闭环。

本包新JSON均按UTF-8/LF字节写出，先落完整INPUT后才由总控调用候选。只读辅助静态自审未发现具体阻断；当前JSON/LF/SHA检查不代替功能执行。实际软件组、M2准入/可信执行器/动态依赖、finish相位、独立plan序号/audio_stable、真实数学/物理/板测仍PENDING，board_release_allowed=false。后续保持冻结，仅应对总控报告的具体缺陷，不抢写、不另起执行者。
