# T058 夜间公开端口联合黑盒验收

仅新增测试，不修改冻结功能。连接 a17803c 的观察桥与 4739e39 的波形候选；
逐项核对夜间 SHA 清单。不是生产顶层，不接触设备或旧 L/ROM。

在仓库根执行：

```powershell
python -B -X utf8 code/tb/input/pcm_waveform_candidate/night_blackbox_20261007/run.py --output code/output/m3_night_wave_NEW
```

默认 Icarus 路径可通过 `--iverilog`、`--vvp` 覆盖。输出目录必须不存在。
单个子进程 600 秒、整套 1800 秒；超时只终止自己启动的进程树。
生成编译/运行/check 原 stdout/stderr、capture、向量与 receipt.json。

公开 audio_frame_load 输入在 40 MHz 时钟沿采样；观察器 pre-NBA 样本经桥
传入同一 25 MHz 波形域，不读任何私有 RAM。独立扫描为 800×525，有效区
640×480。正常封存 A 5849 帧、诊断 41 帧原 signed24、原帧间隔先核 SHA；
合成压力有 10500 个样本、左右不同、零/重复、极值、尖峰、u32 回绕。
分别完整扫描 12/1/14 帧。压力包含停像素钟、32 项满队列、停钟时显示复位、
音频停钟和音频复位。观察计数独立于生产请求 ID；复位期间不入队的样本独立标识，
不把它们伪装成队列满丢包。bridge source_reset_done 在 O 记录末字段公开捕获。

TB 使用收到的公开目的包重建 signed24 的完整 2048 样本窗；每列 4 个 min/max，
只在 frame_start 发布。逐像素比较区域、消隐、RGB 和 N+2 延迟。Python 再独立
从 D 包重建窗，核对全部扫描行实际像素 hash、状态和计数；不是只相信 TB EXPECTED。
frame_summaries 给每帧发布快照的 first/last seq 和 512 列 bins SHA。
复位可清旧快照，除此以外同一帧快照固定。seq gap 清部分窗，不拼接非连续片段。

新 wrapper MUTATION1 交换左声道，MUTATION2 改部分 seq；两个反例必须各自
编译 0、完整运行 0，再由 checker 分别以 PIXEL_REFERENCE/STATE_REFERENCE 拒收。
空/截断/错计数/错像素捕获必须非零。正常结果不能只凭仿真进程 exit0 判 PASS。

checker 单独复核捕获：

```powershell
python -B -X utf8 code/tb/input/pcm_waveform_candidate/night_blackbox_20261007/checker.py code/output/m3_night_wave_NEW/normal_m0.capture --vectors code/output/m3_night_wave_NEW/normal.txt
```

seal.py 只封存新的夜间目录/打包新的 ignored output；拒绝覆盖既有收据目录。
最终 checker 重新执行的日志、源码 SHA 与扫描摘要单独封存，原运行日志不覆盖。
首两轮测试台启动/复位完成记录问题的失败收据保留在原 output，不作为业务 bug 或 PASS。
本轮结论限定数字仿真 L2，不证明物理 CDC、亚稳态 MTBF、HDMI 实屏或整机 STA。
