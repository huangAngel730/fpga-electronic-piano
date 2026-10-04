# 面板输入实测后的隔离实现

CSV在develop2a43963原件：279条CC7、30条CC25..30；USB消息/现场瞬时操作，不扩大DIN或新FPGA L6。输入SOURCE_ID实例独立，按channel/button状态只低→高一次，不因长按高重复/松开触发，不加2ms屏蔽窗。B4-6不产生新动作。

私有命令7/8/9仅隔离提案，公共包未发布。CC7 separate16slot transport缓存与PitchMod共享1kHz成功握手冷却，类别交替；volume不占/改离散FIFO，发出锁保持，最新值更新下一次。CC1去重不把音量锁当Mod锁。默认关闭与de68038四配置逐拍对照。

实际入琴通道1字段0；接口保留全部来源/通道，实测只此channel0，16channel/双source为仿真覆盖，不假称琴上全部通道已验。

run_panel_verified_candidate.py --output <新output目录>执行真实Icarus输入+UART+曲谱+CDC+数学提案+4编译反例，full默认含原parser长miter，--quick不等于最终门禁。无固定位流、无自动写生产/公共包/顶层。

K1数学仍等待M1专业意见；独立volume_proposal测试通过不等于批准映射/平滑/音质。视觉模块用自编有限练习谱，不称正式歌曲。按顺序帧边界一次处理一个离散按钮，屏幕队列有限溢出会显式video_fault，消费者暂停/取消显示事务直到sharedreset恢复，不向音频施加ready。mode切到upper自动暂停，回fall须显式B3继续，上飘B3忽略；最后谱完成并退出后B3清谱从头；restart清score状态不reset扫描/音频。

当前源码在test目录，与旧308dbab生产路径隔离，旧4控件候选不整批合入。最终涉及source/mainintegration写集先私发M1/M3并群公告，仅同版完整STA与实际合约全部通过才给M3SRAM测试包，不写Flash。

本轮原报文/独立输入/真实UART仿真、B1独立银行与CC64、有限曲谱/CDC/数学proposal、四行为反例及default关闭长miter实际日志分别保留output；最末fullrunner本身没有编译生产整机，不替代最终STA。
