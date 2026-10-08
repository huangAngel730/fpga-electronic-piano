# M2 T058精确集成数字验证

新scope/code/build副本只读验证。实际top短例用真实UART31250输入4note/CC64，
原与新两实例每core拍比较play_PCM/valid_ready/requests/commits/underrun/event/status/
PA_EN/UART/I2S pins。serialWS解码独立确认完整32边/填充0。旧tone算法/ROM未改。

独立fullsigned24的publicpixel样本窗口oracle按先publish旧pending、再ingest、4点minmax，
比较每个DVI输入pixel及HS/VS/DE exactN+3。长display用原normal5849A/captureSHA及
时间间隔，不按MIDI另造曲线。旧动画区域外RGB也delay对齐。短例没有到完整2048窗，
不能冒称实际top长窗通过；长displayscope补其完整非空轨迹而不冒称livecore同run。

```powershell
python -B -X utf8 code/scripts/run_138k_waveform_integration_sim.py --mode 0
python -B -X utf8 code/scripts/run_138k_waveform_integration_sim.py --mode 1
python -B -X utf8 code/scripts/run_138k_waveform_integration_sim.py --mode 2
python -B -X utf8 code/scripts/run_138k_waveform_integration_sim.py --mode 0 --display-raster
python -B -X utf8 code/scripts/run_138k_waveform_integration_sim.py --vendor-startup
python -B -X utf8 code/scripts/run_138k_waveform_integration_sim.py --mode 0 --negative audio_pcm
python -B -X utf8 code/scripts/run_138k_waveform_integration_sim.py --mode 0 --negative video_alignment
```

默认每次唯一ignoredoutput，--output显式目录也拒覆盖。--project固定副本，源码SHA和
compiler输入SHA/runner执行快照保留，工具PATH仅子进程CAD bin/lib，无全局安装。
长raster900s/其他600s/global1800s，processwait和实际monotonic最终都严格计时，
异常旧longreceipt20473s已明确不合格，不能passedflag代替合格deadline。
2negativecase仅仿真copy变异，到指定音频/合成assertion诊断终点正常$finish，再外部
checker1；不能把任意fatal/编译失败/超时当PASS。所有失败/停进程日志原样保留。

checker.py提供原META/END精确计数与nonempty阈值及指定REJECT核验；它不是重复实现
完整DSP黄金数学，像素/音频语义来自TB独立publicoracle，真实原件/时序身份另复核。
原始DVI encrypted仿真stub不等TMDS显示器，nominalPLL模型只时钟source，真实vendor
startup另行验证。无上板、无模拟音频/noAPI/设备许可。最终完整STA另看新Gowin报告。
