# V0148实屏反馈后的严格到线与即时衰减闪光（2026-10-02）

本轮用户经主M2明确授权局部修复。上飘长条屏底/长按/松键行为已实屏通过，源码不返工；下落运动/时长不改。正式音频/top/pkg/桥CDC/有效CSTSDC保持。新视频仍无实际路径，不声称看过；以明确语义和源码定向自检为依据。

严格模式：匹配之前先筛slot_used、未判定、pitch相同、hit_frame==即将成为可见current_frame的effective_frame。frame_start同边界按effective_frame=current_frame+1，其他周期按current_frame；与tracker几何NBA更新后一致。只下落模式、非零Velocity NoteOn可判中，不保留任何提前按请求；错键/提前/晚一帧/NoteOff/CC64/held均无命中通知，提前或velocity0不写judged。legacy tracker严格参数默认0保留旧合同，wrapper显式选择strict1。

同音邻槽先筛到线资格再低槽优先，未来/过去邻音不抢配。曲谱source应按一次播放生成唯一note_id；严格模式拒收还在使用的重复note_id（handshake正常消费，不新增slot、不重新武装），每个保留实例最多一次。note_id随重播复位或回收后可重用，不宣称无限历史去重；不新增全歌曲ID内存。

hit_pulse由tracker注册。flash每pitch独立有限count，在通知下个pixel_clk立即激活，不等frame_start；目标成功NoteOn到active最多2个pixel时钟。局部底边颜色允许本帧改变，条形几何不改；底部光点若已经扫描过去需等下一次扫描，不声称物理零延迟。

默认4个强度阶段：hit→下一帧边界为白黄核心/高亮光晕，后3边界依次降到黄、暗橙、微光，再灭。命中正逢边界应先重启而非被减计数；中帧首阶段为剩余帧时长，总约3~4扫描帧（50.4~67.2ms @59.524Hz），不是4个完整帧加额外1帧延迟。不同pitch独立，重新正确命中该pitch刷新；clear/reset/desync/离开下落清理。新增内部2bit/pitch强度位图，不加粒子或动态乘除。

本轮必须证明边界前1周期/前1帧、到线边界/中帧、后1帧、提前按住无缓存、合法重新NoteOn有效、同音邻槽/同ID重复、zero速度、通知→active时钟上限、扫描前后/帧边界、光色衰减与清理。旧tracker参考只验证legacy合同；新严格合同以定向TB判定。复跑新音画隔离/最终Gowin，余量窄则如实报告。主M2登记现场反馈，本窗口不覆盖主任务表/编号。
