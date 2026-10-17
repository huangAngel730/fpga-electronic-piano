# M2 双滑块同版接入边界与待定生产者（2026-10-16，L0）

此文件仅收敛现有隔离候选进入138K C同版整机前的M2受控选择。基础四音现场静音仍由M3独立调查；本轮不接正式top/CST/SDC、不执行Gowin或设备、不生成`.fs`。双滑块处于基础与双音色之后，准备合同不等于获准上板或启用新工具额度。

## 冻结输入

- 现有`_06`顶层`m2_fourvoice_timbre_delay_board_top.sv`37,390字节/SHA`f2a8f30fef8ad2da26d1d3b80793b727f45806b6d5c78f2a071fb383322639be`；视觉外壳`audio_visual_display_probe.sv`7,018字节/SHA`df1f05b4a6a06deddd9d3a2244106ec29bb0d15e5dd808fc9bef9436d710a5cf`。
- M3 D候选`dual_slider_candidate.sv`7,491字节/SHA`a8116d04f7fa70ba4500c4819e3ffb939fcc7096acef9bb7f87004e1e648868f`；其chat8缺口说明SHA`997761e5190f630837cbee6122b2a85863d861d2aaf22ae787b0b0c8db7b713b`。
- `_06`约束输入CST SHA`1f22af2d963315cfe625af5f22b25c9ce68152ee0ec2bed859d36b3a196e723d`、SDC SHA`a8791f826c0bd8630483ce28c44636c24e4e28c041a9622d17d0b1764a8f888f`。新候选改变层级后须按新网表重新核约束对象和完整STA；B已签五对定向L5不搬运为新树证据。

## M2确定的最小接入规则（后续隔离复制工程适用）

1. **时钟与出口不变**：保留原TMDS_PLL产生40MHz核、25MHz像素、125MHz串行时钟，现有扫描器、唯一一拍RGB/HS/VS/DE寄存、唯一DVI/TMDS出口。仅替换旧事件/控制CDC及场景段，不在旧桥之外串接另一桥、不并联两套RGB。M3 D是显示wrapper，不产生PLL或TMDS；整块替换外壳会丢40MHz音频核时钟。
2. **显示复制不能回压音频**：仅`shared_event_valid && shared_event_ready`握手的64bit演奏事件复制给显示；视觉`mode_ready`、`score_ready`、队列满/drop/desync都不反馈改变音频ready/PCM。原外壳`visual_event_bridge #(.DEPTH(32))`，D候选第55行写死8；初次隔离接入采用**32深显示事件队列**，八个画面槽不等于八深队列。后续若要降到8须另给突发容量/丢弃合同证明并更新决策，不静默缩容。
3. **默认几何**：准备和验证的生产默认为640×480、SLOTS8、Y_WIDTH10、PREVIEW_FRAMES120、BASE_NOTE36、NOTE_COUNT49；画面扫描保持现有800×525总时序的25MHz像素域。已跑128×64、四槽、preview8仅是加速隔离夹具，不能作为默认整帧、槽4–7、边缘/消隐、真实HDMI或实屏通过。
4. **mode握手语义**：正式模式请求必须从40MHz域以`mode_valid`保持至`mode_ready`，每次操作产生一次接受；控制邮箱向25MHz域传单个toggle，`frame_start`锁存显示模式。与`frame_start`同沿收到mode_pulse时，本帧保留旧模式，下帧提交新模式。`SOURCE_MODE`属于音频固定音诊断，旧外壳五秒定时切换属于诊断，不可声明为用户触发。当前两枚板键为演奏键、EX_KEY.0为复位，不在未选择独立输入前重定义。**实际物理/逻辑模式请求生产者尚未批准**；本文件不凭空指定新引脚或MIDI消息，也不生成生产码流。隔离功能测试可以用TB握手驱动，结果必须标“测试入口”。
5. **score整包和时间基**：沿现有`visual_control_bridge`一次握手传16位note_id、7位note_number、32位hit_frame、1位duration_valid、32位duration_frames、10位velocity，总98位，valid等待ready期间全部稳定；hit/duration单位为显示帧。当前`current_frame+6`来自TB跨层读取，不能让40MHz生产RTL直接采25MHz多位`current_frame`。**正式曲谱生产者、帧零点及复位后epoch映射待确认**。没有实际曲谱源时用TB来源验证滑块形状/运动，明确不能据此签正式曲谱导入；任何读回帧号需要独立握手CDC。
6. **共同复位及约束**：PLL失锁或`sys_rst_n`使事件/控制邮箱共同异步断言复位、各域本地同步释放；以D的`sys_reset_done`/`video_reset_done`汇合后启用源/像素消费者，扫描/串行保持原复位边界，不能只清像素侧而留在途token。新层级须重新统计七个异步首级及其二级寄存器、事件64位和曲谱98位bundled-data实际匹配数量，核setup与hold及全音画路径；旧SDC第300–327行的`u_visual/u_event_bridge`等层级不能盲抄成已命中。不得用宽泛异步clock-group掩盖容量或跨域缺失。

## 准入顺序与停止点

1. 在M3已授权的独占候选目录先核默认几何、队列32、模式脉冲同帧边界、复位/失锁和完整握手；保留首失败及原始日志。M2只读核输入身份和差异，不在此重复M3软件/RTL测试。
2. 只有基础四声及双音色同版出口闭合、正式mode和score生产者有可实现来源/必要输入和受控接口说明后，M2才在**新隔离复制工程**选正式接入点并先核同链音频无退化、CDC对象命中，再申请必要新Gowin/PnR/STA预算和精确码流。未满足时本合同停在L0；未选择mode输入时不借诊断自动切换冒称“双模式自由切换”。
3. 下落命中闪光仍是旧FAIL，首轮暂缓，`flash_active/flash_level`固定0不计命中反馈；没有基础L6、真实默认画面、完整新STA或板测时`board_release_allowed=false`。固定左波形与最小传谱排在本项之后，N32最后条件项。
