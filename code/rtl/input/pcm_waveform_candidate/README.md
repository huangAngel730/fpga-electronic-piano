# T058 像素域真实 PCM 波形候选

仅独立候选，不修改或例化原 L/音频/CDC/扫描/PLL/TMDS。统一入口
`pcm_waveform_candidate.sv`，25 MHz，低有效异步复位（释放由调用方同步）。
接口严格沿用 D038：无 ready；sample_valid 可背靠背，sample_seq 模2^32递增，
左右 signed24 原子包；只画左声道。右声道不平均、不去重零或重复值。

窗口2048包，每4包先以 signed24 比较 min/max，再取高有符号8位；量化为单调映射，
因此缓存每列16位不会损失规定像素口径。三银行各512×16位：front/pending/write，
共逻辑3072bytes，RAM不复位。参考模型保留全部2048 signed24样本，不依赖此实现。

序号跳失/重复时计一次gap，丢未完成窗口，当包作为新窗第一包，旧front/pending保留。
正常序号回绕不计gap。stream_restart优先于sample_valid，清所有有效元数据和连续性；
累计两个饱和计数保留，pixel_rst_n复位才清计数。restart不计完整窗口丢弃。
每次新完整窗替换未发布pending，window_drop_count加一；front从不被采集写入。
frame_start优先发布旧pending，同拍完成的新窗随后成为pending；任意输入速率都不反压。
三银行无需因无空闲主动丢样本，允许不断替换pending。无完整窗时只有背景/零轴。

绘图窗口x64..575/y64..319，q=PCM>>>16，y=191-q；区内mask1，区外或DE/enable0时mask0。
背景RGB=08/10/20，零轴40/40/40，轨迹00/e0/ff且优先。区外RGB固定0但mask0，不覆盖原动画。
无额外边框、AGC、触发、时间缩放、FFT、李萨如或控制键。

输入沿N的坐标/DE/enable，在沿N+2后对应输出RGB/mask；同步RAM读、绘图寄存、输出寄存。
frame_start当沿读新发布银行，第一个像素对应新快照。trace_valid是即时元数据，不额外延迟2拍。
复位清渲染流水线；stream_restart使本拍取样的trace失效，先前已入流水的像素仍按2拍输出。
M2最终须对原RGB/HS/VS/DE同样对齐，独立模块没有CDC、原动画合成或发送器。

复现：

```powershell
python -B -X utf8 code/scripts/run_m3_pcm_waveform_acceptance.py --output code/output/m3_pcm_waveform_<new-run>
python -B -X utf8 code/scripts/run_m3_pcm_waveform_acceptance.py --check-capture <capture.txt>
```

默认复用现有D:/Gowin/oss-cad-suite/bin/iverilog.exe与vvp.exe，不安装工具。
详细结果、原证据与边界见`code/docs/hardware/pcm_waveform_v1/DELIVERY.md`。
