# E2 固定左波形：待 Pro 正式接入差异

本候选只联接既有 `pcm_frame_observer`、`pcm_waveform_observer_bridge(DEPTH=32)` 与 `pcm_waveform_candidate`。这些旧源码没有修改。新增 wrapper 无 ready、音频使能或播放控制输出，显示复位也不送入音频引擎。当前验证对象为独立数字观察链，不含实际 Pro 顶层、ROM、I2S 引脚、HDMI 编码器或板上模拟音频。

| 接入点 | 已固定口径 | M2 正式接入待办 |
| --- | --- | --- |
| 音频源 | audio_clk=40MHz；在发送器真实 frame_load 沿采 pre-NBA signed24 left/right；独立 adoption ordinal 从0递增，不取 request_id | 提供精确 Pro source/ROM/top/trace 身份，确认采纳沿对应实际发送帧，欠载保持/静音仍观察实际输出；不接预测 sample_tick 或未来 NBA 数据 |
| 跨域 | 80bit `{seq,left,right}`，源域FIFO32加一个稳定邮箱；pixel_clk=25MHz | 继承并核 bundled-data 数据稳定时间、req/ack 同步器属性、物理端点和约束，完成整机 Setup/Hold/Recovery/Removal/CDC；仿真不能代签 |
| 复位 | audio_rst_n 与 display_rst_n 均异步置位、各域同步释放；显示复位共同冲掉观察桥两端但保留音频 observer 序号；stream_restart 先于新样本 | 接现行 PLL/复位控制，禁止单独复位邮箱一端；显示复位不复位播放引擎；确认同版复位路径时序 |
| 区域/数据 | x64..575、y64..319，端点包含；2048样本/512列，每4点 signed24 极值后取高有符号字节；top=191-max、bottom=191-min；仅左声道 | 保持冻结区域和窗口，不增加缩放/双通道/频谱/李萨如；提供真实 video 坐标、DE、frame_start 和 waveform_enable |
| 输出延迟 | 输入坐标在沿N，RGB/mask在沿N+2；背景081020、轴404040、线00e0ff | 视频合成其它图层/DE/同步应按相同两拍对齐，确认真实 frame_start 定义；本TB只扫描区域与边界，不声称完整 HDMI 帧协议通过 |
| 快照 | 三个512×16银行，满2048才有pending，只在frame_start发布；同时满窗与发布先发旧pending，新窗留pending；中帧front不变 | 正式顶层提供唯一帧边界。逻辑存储量不是已综合 BSRAM 数；资源/映射/STA均未运行 |
| 拥塞/间隙 | 显示停钟时最多33个观察包驻留，后续观察包丢弃但音频照常采纳；gap丢弃不完整窗，当前样本作为新窗首点，保留已有front | 分别暴露包丢弃数、序号gap段数、pending窗口替换数，不把三者混同；正式音频链无显示反馈路径 |

同版实屏原件仍 PENDING：需要获准的 Pro `.fs`/恢复文件SHA、板型/Bank/电气原件、真实数字 A/目的 D/视频帧对应、逻辑分析或屏幕捕获、音画共存与不反压证据。M2 决定正式接口/约束/下载准入；M3在准入后采原件。`board_release_allowed=false`，总 E2=PARTIAL。音频数学定义未变，无 M1 算法变更申请。

新增文件在三个 E2 目录内；正式 top/pkg/PLL/CST/SDC、M1黄金、旧ROM/旧seal均只读。新 wrapper 的诊断输出只属于隔离候选，不能直接当作批准的生产公共接口。
