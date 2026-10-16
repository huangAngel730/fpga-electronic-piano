# 正式Pro接线/CDC/STA差异表（只作L0提案）

来源：b6f28911发布的《M2_双滑块同版接入边界与待定生产者_2026-10-16.md》，其完整SHA另见CONTRACT_IDENTITY.json。本包未修改正式top/CST/SDC、PLL或TMDS。该M2合同引用138K C旧输入，不能作为新Pro同版工程/引脚/网表/STA证明。

| 项目 | 新隔离候选/验证入口 | M2正式接入前需决定/提供 |
|---|---|---|
| 事件生产者 | 旧64bit performance_event_t；TB合成NoteOn/Off，accepted_valid仅表示输入事件已由音频方接受 | Pro实际shared_event_valid&&shared_event_ready的唯一接受点/同版源SHA；不能用视觉queue或mode/score ready改变音频ready |
| 显示队列 | 新wrapper默认EVENT_FIFO_DEPTH32；32 queued+1 mailbox；八画面槽独立 | 保留队列32，核突发容量与drop/desync；正式观察水位是否留状态接口另决定 |
| diagnostic display_event_enable | TB暂停目的ready/fire以覆盖满空/回压，正常候选不反馈音频 | 正式生产默认系1；不新增用户模式入口或未知引脚；若需要正式stall控制须单独冻结合同 |
| mode生产者 | 40MHz域valid/ready，邮箱toggle到25MHz；同沿frame_start保留旧mode，下一帧提交；TB刺激非用户操作 | 实际按键/协议来源、去抖/保留valid直到ready、每操作一次接受；不得复用音频SOURCE_MODE或诊断五秒自动切换 |
| score生产者 | 98bit单握手：id16/note7/hit_frame32/duration_valid1/duration32/velocity10；背压稳定；TB期望由合成输入导出 | 正式曲谱源、note_id生命期、显示帧零点/epoch映射；不能由40MHz直接采25MHz多位current_frame，需独立握手快照/相对协议 |
| geometry | 640×480、SLOTS8/Y_WIDTH10/PREVIEW120、BASE_NOTE36/NOTE_COUNT49 | 按同版renderer/扫描器核边缘、消隐及画面槽4–7；加速运动帧不计真实HDMI帧率 |
| 时钟/出口 | 40MHz sys与25MHz pixel独立仿真源；800×525 raster，25MHz对应59.5238Hz | Pro实际PLL配置、125MHz串行时钟、锁定/复位、唯一RGB/HS/VS/DE寄存级及唯一TMDS出口；wrapper不产生PLL/扫描/串行器 |
| reset | 共同rst_n异步断言，两域reset_sync本地释放；在途mode/score/event由共同reset取消 | Pro PLL失锁与系统复位的共同断言源/扫描串行复位边界；不单清pixel侧留下token |
| CDC结构 | 只读复用event bridge及mode/score mailbox；静态源有7个数据控制异步首级（event req/ack/desync、mode req/ack、score req/ack） | 新物理网表逐实例命中首级/二级；64bit事件、98bit曲谱和1bit模式bundled payload的实际路径/保持条件；完整setup/hold/clock与reset检查，旧SDC层级不能盲搬 |
| 诊断观察口 | queue_level/high、display_event_fire/data、score_event_fire/seen_payload/sink_ready用于TB身份核对 | 正式不用的观察口可不接，是否保留调试需M2决定；本包不改正式公共端口 |
| 音频 | 原tick/buffer/tx+诊断PCM生产者独立并行，队列满/暂停消费不回压音频；错误门控calc_ready作为负例 | 新Pro真实四声/双音色链同版完整接线/欠载/期限；本诊断无R05算法/PCM黄金/PA_EN/模拟发声结论 |
| 已知闪光失败 | flash_active/flash_level固定0，旧命中闪光FAIL暂缓 | 后续另定修复与验收；不把连续下落显示称完整命中反馈 |

正式Pro source/ROM/top/trace未到、mode/score生产者未批准、基础与前项双音色同版出口未闭合时，本包停在独立候选。M2未来固定精确新树后另批工程/CDC/完整STA/码流，M3另做真实实屏记录；本夜次数均0，board_release_allowed=false。
