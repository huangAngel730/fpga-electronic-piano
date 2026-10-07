# M2 PCM帧观察和有缓冲mailbox CDC独立候选

本候选属于T058 M2接入准备，原L/生产/M3范围不变。真实接口口径来自
`code/docs/M3_HDMI真实PCM波形_接口与独立任务单_2026-10-07.md`。

- `pcm_frame_observer`：音频40MHz，在audio_frame_load同沿采pre-NBA play_left/right，
  signed24。输出寄存valid/左右/独立seq，默认首seq0，模32回绕；静音/欠载重复也采。
- `pcm_waveform_observer_bridge`：32深度音频域80bits队列，另有一份mailbox。复用
  只读common/visual_mailbox_cdc和reset_sync，握手payload保持到pixel接受及ACK返回。
  无音频ready或外部读口反压；display满/停只丢显示并计数。
- M3像素入口：sample_valid/seq/left/right、stream_restart和waveform_rst_n；valid可按
  实际mailbox吞吐发出，无需保证相邻，M3必须支持背靠背。当前实现一般间隔数拍，不冒称
  能每pixel拍排一条或等于双时钟RAM FIFO吞吐。
- audio_rst_n/display_rst_n共同异步清观察队列和mailbox；本域同步释放。display单独
  复位不改变观察序号/原音频reset，音频复位seq归首值。丢显示计数按本观察branch reset
  清零，非全系统跨reset累计。waveform_rst_n只给新波形模块，不能门控原视频/音频。
- source_reset_done在pixel域双同步后只发一次stream_restart，此后再输出数据；该周期
  无sample_valid。像素clock停止期间reset仍须清支路，本候选独立TB对此施压。

逻辑容量=DEPTH队列+1mailbox；未执行Gowin/BSRAM映射/CDC物理时序/整机STA/实物。
正式接入必须约束80bit payload_hold→dst_data延迟与请求同步/源保持关系、双向握手
同步器与复位Recovery/Removal，不逐位PCM双同步、不用全域false_path当完整CDC证明。
原函数/数据/ROM没有变化，FIRST_SEQ仅独立test参数，正式使用0。

唯一新增runner：`python -B -X utf8 code/scripts/run_pcm_waveform_observer_candidate.py`。
独立脚本用Icarus/公开端口TB；部分旧模块仅integer unsigned参数语法在仿真staging机械
适配，所有原SHA/副本SHA/命令/退出码/原日志保留，不能当原ModelSim工具复跑。
本模块准备与最终顶层/约束/接口组改动分开，后者仍需通知及系统验收。
