# 最小可逆接入提案（不可直接应用，待M2精确新树）

新Pro源/ROM/top/PLL/CST/SDC与实际mode、score生产者未到，故不生成假端口或可直接应用的补丁。本提案是逐段替换范围与真实候选端口的绑定表，旧R05仅供定位。更改正式接口/时钟/复位必须由M2按受控流程处理，基础+双音色正式出口以后才接本项。

1. M2冻结一份**新Pro隔离副本**，列完整source/ROM/目标/工具/约束身份与工程引用，另封可恢复原树。不得以当前C.shell、旧O.top和旧O.pll拼成新源，也不在原封存或生产树编辑。
2. 在新树实际找到唯一PLL、核/像素/串行时钟、scanner、一拍RGB/HS/VS/DE、DVI/TMDS出口和实际音频接受点。旧对应段为O.shell:70–72/100–102/121–134与O.top:679–682；它们只作角色参照。保持这些角色及端口/时钟所有权，不能用D整块替换外壳。
3. 替换范围只限旧视觉事件桥+控制桥+scene（旧O.shell:73–99及103–118）。引入**一个**既有dual_slider_pro_parallel实例，不在旧桥后串第二桥、不保留两套并行RGB或重复消费。删除该副本中诊断mode/score生产块及废弃wire后，由批准producer绑定下表；未绑定时停止生产集成，不把tie0/五秒timer当完成。所有删除/新增行写新树精确patch，能够逆向恢复原字节。

| 真实候选端口 | 待M2绑定/保留规则 |
| --- | --- |
| sys_clk / pixel_clk | 新Pro真实40MHz / 25MHz，不能用TB钟或仅凭端口名推断；125MHz只留原串行出口 |
| rst_n | 新树PLL lock与系统复位的唯一共同异步assert源；各域由候选本地sync-release；producer同步取消旧pending |
| accepted_valid / accepted_data | 新树实际音频唯一接受握手与原64bit performance_event_t，显示支路不能参与源ready计算 |
| display_event_enable | 本候选诊断暂停口，生产拟固定1，需M2确认；不增加用户可选模式或新引脚 |
| mode_valid / mode_ready | 批准的40MHz操作producer，valid保留到ready，一操作一接受；不得绑定音频SOURCE_MODE或旧五秒timer |
| score_valid / score_ready及六字段 | 批准score producer，98bit整包保持，note_id生命周期与frame零点/epoch明确；禁止裸跨域读current_frame |
| frame_start / data_enable / pixel_x/y | 新树唯一scanner原输出；它的复位应使用候选video_reset_done，不能保留已删除旧control_video_done作为悬空依赖 |
| rgb_r/g/b | 接唯一既有一拍RGB寄存输入；HS/VS/DE同一拍保留，不能额外并联或漏合成延迟核对 |
| sys_reset_done / video_reset_done | 替代被删除两桥的汇合使能；producer在源域使能前须清旧pending，scanner/场景按像素完成信号启动；不改变音频复位定义 |
| current_frame | 像素域公开诊断计数，不能直接驱动40MHz producer；如确需回读，另由M2冻结可靠快照CDC或相对协议 |
| 其它诊断输出 | 不改变正式公共端口；是否留状态观测由M2决定，不因候选有口就默认新增外部接口 |

4. 参数保留已签默认640×480/SLOTS8/Y_WIDTH10/PREVIEW120/note36..84/FIFO32。flash_active/flash_level固定0对应旧FAIL，不修、不签完整命中反馈。
5. 按CDC_PATHS.md在**实际新网表**重建七组及64/98bit端点映射。候选u_events与旧u_event_bridge名不同、外层还增加实例前缀；_s0为旧优化名。需首级/二级、有效位统计、具体起止端/对象命中与数据setup+hold及全路径时序，不能宽泛异步clock-group或照抄10ns代替报告。mode常量payload若优化需证据。
6. M2为新树明确新的实现验证/EDA额度后才运行；M1给同源前后音频输入/PCM/clip/期限/欠载无退化判据，M3只在正式同版.fs/恢复SHA、电气原件和本次SRAM许可齐备后采上飘按/松、下落运动/退出、模式/复位/音画共存实屏原件。本轮ModelSim/Icarus/Gowin/设备调用0。

当前精确交接请求：M2提供新Pro闭包及三项决定（mode来源、score来源及note_id/epoch、真正接受点/共同复位/唯一路径），随后在正式顺序允许时选择新副本集成并核完整CDC/STA。缺件不是授权申请已获准；board_release_allowed=false。真人M2仍待用户转发，尚未送达；总控AI收件不等于真人已签收。
