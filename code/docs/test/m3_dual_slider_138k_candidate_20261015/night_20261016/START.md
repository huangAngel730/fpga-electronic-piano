# 夜间任务4：D真实音频模块共存增量

2026-10-16；基线 c12636c034be62e10c564217298564422a533b9c。

用户经夜间总控直接授权本窗口执行 DISPATCH 的 D 增量并用自己的子智能体只读自审。旧 D 99 项/4 负例保留、引用、不重跑；原失败、旧消费账本、旧代码/工具原件只读。本轮只写 D 授权目录的 night_20261016；不做 Git 写入，由总控统一发布。不启动审核员制度、不联系其他窗口。

本次最小退出物：现视觉候选与原 sample_tick_gen/pcm_frame_buffer/i2s_tx 同时仿真；两次复位生命期各96音频帧，视觉帧加速夹具下做按下/释放、模式切换、落条运动/退出。公开请求ID/PCM提交/真实frame_tick/BCLK/WS/DIN捕获，独立软件解码逐样本检查。PCM来自明确诊断生产者；不是R05实时算法、正式top或完整视频扫描。clip仅源元数据，非原buffer/tx端口。

复位前尚未完成的第96号请求明确RESET_CANCELLED；复位后从静音和新ID开始，不声称跨复位无丢失。旧命中闪光FAIL不修，实屏、模拟起音、STA、码流/下载均未验，board_release_allowed=false。

本新批最多3组不同源码SHA必要修法，单工具≤300秒、单组≤300秒、本批实际仿真≤900秒。首次正例/负例全部通过即封存。每次先冻结源码/工具/Job/已发布依赖，独占RUN目录、消费标记、双流和调用回执；超时以Windows Job结束进程树。旧许可不恢复。

工具只用 E:/FPGA/GAOYUNFPGA/138K/tools/icarus_oss_copy。逐文件冻结现有工具副本；依据旧 run_repair.py/repair_run_02 的哈希核相同文件原字节，DLL搬迁按文件名和SHA比对，不执行旧副本缺少的无关工具。Python与Windows Job按旧精确依赖核同；原视觉/音频RTL和C checker另核c12636c字节。

计划执行命令（实际结果以RUN回执为准）：

```powershell
& 'C:/Users/songdongkuan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -X utf8 code/docs/test/m3_dual_slider_138k_candidate_20261015/night_20261016/run_coexist.py --output code/docs/test/m3_dual_slider_138k_candidate_20261015/night_20261016/RUN_01
```

四个TB故障反例：漏生产请求→真实欠载；左右交换→串行逐样本不符；DIN延迟一BCLK→错相；下落模式门控tx.valid→冻结旧串行样点。各变异工具可正常退出，独立checker必须非零并给指定诊断，不能把TB结束标记当音频PASS。
