# E2 固定左声道波形后继包（2026-10-17）

**限定隔离验收PASS；完整E2=PARTIAL，board_release_allowed=false。** 新增 wrapper 只联接旧观察桥和旧波形core，不修改正式工程。完成三轮中的第3轮后成功即停，前两轮TB失败与修复原件均保留。

入口：`RESULT.json` 为实际数字结果、命令/退出和首差异；`INPUT_IDENTITY.json` 为来源；`PRO_INTEGRATION_DELTA.md` 为M2接入差异；`FAILURE_HISTORY.md` 为失败历史；`ROUND_03/RUN_RECEIPT.json` 包含全部源码/工具前后SHA、机器、环境、调用、时间上限和结果。封存包内 `MANIFEST.json` 覆盖全部成员的字节与SHA；zip身份另在 `PACKAGE_STATUS.json`，该外部回执不属于zip成员。

实际覆盖：40MHz→25MHz观察桥+固定左core；历史真实RTL A捕获5849包，5848个相邻间隔逐对核833/834拍（3899/1949次），source_seq=adoption ordinal−1而非request_id。历史normal左右完全相同，来源不等于新Pro或板上实采。合成A明确用于signed24极值、量化边界、左右区分；合成B/C/暂停/恢复用于压力。总14241次音频采纳均被观察，正常目的交付14074；暂停显示时源200次均继续，观察分支丢167包，恢复gap=1段；pending替换=1窗。独立账本核逐包PCM原子身份、A→O预NBA一音频拍、O→D因果/恰一次、D→core I同沿。初始复位与带已显示front/未满partial窗的显示复位通过，显示复位后下一audio序号仍5849。

像素检查3998520拍（含默认区域外的背景时钟）中，8次完整512×256区域扫描及边界/DE/enable检查，对应5个独立黄金快照：真实前两窗、合成A、合成C、恢复。核2047不发布/2048发布、无帧边界不换front、pending最新窗替换、gap丢partial保front、完成恢复窗、RGB/mask两拍延迟。黄金只由原输入signed24逐四点min/max再右移16产生，从不读DUT银行或捕获像素反推。日志`x_now/y_now`是比较时当前输入坐标，实际被比较输出对应两拍前的坐标。

| RTL坏例（仅TB force或接线） | 实际首拒收 | 实际退出 |
| --- | --- | --- |
| 左输入错接右 | PIXEL_REFERENCE（合成A首次左右分离后） | 1 |
| seq4096私自发布而无外部frame_start | WINDOW_FRAME_TEAR | 1 |
| core丢seq1000 | SAMPLE_SEQ_GAP | 1 |
| 显示复位未传入core | RESET_TRACE_STALE | 1 |
| 队列满时禁止audio_frame_load | AUDIO_DISPLAY_BACKPRESSURE | 1 |

范围限制：本次未增加缩放、右声道显示、频谱、李萨如；未重复旧 `tb_waveform`/旧joint专项/E1。没有声称本次新测u32 wrap、序号重复、同沿完成与发布或复位取消在途邮箱；这些是保留旧源的规则/历史专项，不能写成本轮新增覆盖。TB中的停像素钟仅为仿真压力装置，不是可综合门控钟。没有新Pro工程/ROM/top/trace、完整raster/HDMI编码、综合/PnR/STA、同版实屏、板测；商业许可与硬件原件未到，不启动Gowin或下载。

可复现命令（本夜已成功，runner会拒绝重复消费，勿重新跑）：

```powershell
& 'C:\Users\songdongkuan\miniconda3\python.exe' -B code/docs/test/m3_pro_waveform_successor_20261017/run.py --preflight --output code/docs/test/m3_pro_waveform_successor_20261017/PREFLIGHT_01
& 'C:\Users\songdongkuan\miniconda3\python.exe' -B code/docs/test/m3_pro_waveform_successor_20261017/run.py --output code/docs/test/m3_pro_waveform_successor_20261017/ROUND_03
```

实际cwd为仓库根，内部每条compile/VVP/Python的精确argv、冻结stage与环境在launch/receipt里。工具是既有Python3.12.4和Icarus14.0devel，含EXE/DLL闭包SHA；每轮600s、Python90s、04:51北京时间收口上限，Job Object拥有子进程树。所有运行在边界内。

本窗没有提交/推送/Git写入、没有编号或修改共享状态，也未向审核员/预审员送审。夜间任务1负责统一发布及M2最终复核；真人M2材料仍待用户转发，尚未送达。收到精确新Pro原件与M2准入后再由对应责任人完成正式接入、同版STA及实屏采集。
