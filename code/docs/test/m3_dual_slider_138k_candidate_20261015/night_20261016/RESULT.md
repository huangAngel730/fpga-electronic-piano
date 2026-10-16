# 夜间任务4 D增量：PARTIAL

2026-10-16；基线c12636c034be62e10c564217298564422a533b9c；本窗口未提交、未推送，交夜间总控集中自审/门禁/发布；默认交接待用户转发，尚未送达。

已经得到**真实模块隔离共存正例 L2 + 独立软件检查 L1**：现双滑块候选与原版sample_tick_gen/pcm_frame_buffer/i2s_tx，共享40MHz系统时钟/复位，25MHz独立像素时钟。PCM由诊断生产者提供，视频frame_start是加速夹具，非完整raster。模块事实不外推R05算法、正式top、综合/STA、码流、实屏/模拟声音或输入→模拟输出≤10ms。board_release_allowed=false；旧命中闪光FAIL不修、未验。

本次实际改动仅D目录night_20261016：tb/input/visualizer中的tb_slider_audio_coexist.sv；docs/test中的runner、独立共存checker、纯软件postprocess、原始执行/失败/封存和回执。未新增可综合RTL，无需修改正式top/公共接口/约束。旧D 99项/4负例只引用，不重跑；其余旧源/原件/工具/消费记录只读。

实际验证结果：

- RUN_01编译访问冲突exit3221225477，未运行产物。RUN_02在正常require_escalated审批后编译0，仿真1，定位新TB对视觉快照延迟的错误假设。RUN_03只修该假设，编译0/仿真0，58项新共存检查完成；独立原C音频checker通过，新D软件尾段断言错误导致positive_check1。原件均保留，详见FAILURE_HISTORY.md及各RUN调用回执。
- 三组RTL启动已全部消费，共3次编译/2次仿真（第一次失败/第二次正常）。最后正常160024个连续PRE_NBA系统沿，两个复位生命期各96音频frame_tick；每生命期95个帧间隔中833拍64次/834拍31次。短窗平均约48000.40Hz，不冒充精确频率实测。
- 软件修正只读复核RUN_03捕获，SOFTWARE_R02 exit0：188个完整立体声帧（含两次启动静音），186笔请求到完整串行观察，PCM24独立舍入/饱和、低WS右/高WS左、32槽/半帧、真实引脚相位/逐样本值和连续性通过；真实意外欠载0，32沿旧ID不ready，950沿提交后valid不二次提交，10次clip仅源元数据。最后数值以POSITIVE_CHECK.json为准。
- 每生命期20显示帧/29检查，实际按下增长、松键上移、模式邮箱→帧边界切换、下落移动/退出和切回期间，每显示帧间均有真实PCM commit/frame进展；独立解码每生命期观察到3个live阶段完整串行帧、17个falling阶段完整串行帧。复位后静音/ID重启，无幽灵显示项；不存在跨复位无损声明。
- 复位前94/95号已adopt但串行尾段未完整观察，分别记RESET_INTERRUPTED_SERIAL_AFTER_ADOPTION；96号未提交记RESET_CANCELLED。第二生命期94/95号仅窗口结束未完整观察，不冒称全请求闭合；完整观察请求数字request→串行最大1687拍/42.175us，仅诊断模块路径。
- 五个软件波形反例指定拒收：WS极性互换/STEREO_FRAME_MIX、载荷位翻转/SERIAL_PCM_LSBJ_OR_STEREO、漏系统沿/MISSING_OR_DUPLICATE_CYCLE、X引脚/UNKNOWN_OR_NONINTEGER、漏显示帧/D_VISUAL_FRAME_COMPLETENESS；全部明确SYNTHETIC_WAVEFORM_MUTATION，不替代RTL行为变异。

**未完成必做项：四个TB故障注入仿真尚未执行**（漏生产、左右交换、DIN错相、模式门控发送）。RUN_03正常软件检查失败即停后，三组额度已耗尽，不续跑旧组、不另开第四组。故本增量整体PARTIAL；后继需由总控/用户明确新的精确执行范围/次数，优先只跑这四个未执行变体并用当前checker核验，不重跑原99项。本轮没有收到新额度，不自动恢复。

封包入口DELIVERY.json；输入、源码、工具/Job/依赖、原始双流、产物SHA与调用/耗时见NIGHT_RUN_RECEIPT.json、MANIFEST.json及包内各RUN。源/工具前后SHA均稳定。每工具/组≤300s、本批实际仿真远低于900s，无超时、无Gowin/ModelSim/实物或Git写入。

依赖边界：各真实RUN的before/after包含C原decoder且稳定，RUN_03/execution_sources留原件；SOFTWARE_R02的before/after只列主脚本/捕获/Python，未单列动态导入C decoder，不能称该次全依赖前后冻结。最终封存静态再核C原件同RUN_03 SHA eea802c41f8edf59787a5cb8f5c2aea5c19c3e3827479eaf52a20dc5424074b6，不补跑也不回填旧收据。

直接通信被自动审批拒绝（认为无可信用户直接通信授权且存在禁止联系其他窗口规则）；阻断消息未送达，未绕过。可由用户将本文件及封包转发夜间总控01a14050-cd98-7c41-8004-5d3e25765167，再由总控交M2最终复核。发送文件或仓库落盘本身不记为通知。
