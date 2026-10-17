# 夜间3 R08角色C READY

全部8项代码/CLI和独立用例准备齐，T=56例（13=9、14=6、15=20、16=9、17=6、18=6），H本角色=17例（23=8、24=9），均NOT_RUN。精确源码/用例SHA、依赖与各READY入口见ROLE_C_READY.json。所有run_case先创建独占目录，先保存完整INPUT_BEFORE_CALL，实际结果先落ACTUAL_BEFORE_ASSERT，再断言；失败抛异常并保留首件。

仅总控冻结并运行整个T组和合并H组，本窗口没有import执行任何候选/测试，没有子进程/EXE/HDL/EDA/设备/Git写入。旧R6-6 28/20、B19、D22不跑；R6-3只读。两处控制位自审阻断已在冻结前修正并补反例，未消费修复额度。

C6静态绑定位于R07/public_equivalence_tb/c6_binding/：C6正式71源+2头+9ROM的82件与既有双top输入逐字节同，可原样复用C5双top76源/78module包（旧名保留），输入本体/decision/源码胶囊已复制保全。没有重跑B；compile/elaboration/实际组合准入仍PENDING。

真实M1语义/采样/工具来源、板卡/时基/物理、新.fs/恢复与可信M2许可均未取得；PENDING/UNKNOWN/UNRESOLVED不能写成实义PASS。24即使合成机械齐套也不能授权下载，Flash/重复SRAM拒收。board_release_allowed=false。

总控可直接读取本地READY，不因平台通信被拒重复请求用户授权；本窗口等待统一组的实际结果，不自行触发功能执行。
