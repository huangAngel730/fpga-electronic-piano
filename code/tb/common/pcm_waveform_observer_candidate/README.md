# M2 PCM观察/CDC独立TB与checker

输入固定原L56源/ROM收据，编译只读i2s_tx/pcm_frame_buffer与common mailbox/reset，
不用M3波形RTL、不改算法/ROM、不重跑原L顶层或Gowin。

完整集合入口（Icarus位于D:/Gowin/oss-cad-suite，可--cad覆盖）：

```powershell
python -B -X utf8 code/scripts/run_pcm_waveform_observer_candidate.py
```

输出默认新唯一忽略`code/output/m2_pcm_observer_<time>_<id>/`；显式--output也拒绝已存在
目录。单仿真240s、总900s上限（其余步骤45/30s），超时只终止自身进程树并失败。
原stdout/stderr/bin、compiled仿真源、original source/适配manifest、capture/vector与receipt
齐套；硬件/STA/Gowin标false。--case只运行一例并标partial，不用partial当全套通过。

- normal：strict Base64解码真实正常capture、原manifest SHA/长度核对，从全部5849个A
  行取同一时间间隔和signed24左右；原采集没有造MIDI波形。本测试加入明确标记的pixel
  暂停和display/audio reset，不能当原音频采集器新功能验证。
- diagnostic：同样取原诊断41个真实A，左右不等/极值/零/欠载重复；不复制扩充假数据。
- stress：公开标synthetic的固定seed1400帧，DEPTH3、FIRST_SEQ近2^32回绕、高频/突发/
  queue满、双reset、停止source/pixel。real回放测试仍按原40MHz/帧时序，stress仅边界。
- isolation：两套原L PCM buffer/i2s_tx、同一公开producer，40MHz真实BCLK步长；仅一套
  观察，两套在每audio拍比较play_left/right/ready/request/pending/计数/frame/BCK/WS/DIN。
  故意两个3帧欠载、像素暂停、停钟中reset、运行中reset，保持音频同一流。
- wrong_pcm/wrong_sequence：只在新仿真目录patch候选左右/队列序号，必须compile0+完整
  仿真exit0，再checker1特定失败；不以编译错/超时当语义拒收。
- 9种坏capture：空、缺META/END、END后记录、未知tag、错误PCM/epoch、重复D、错误END，
  checker非零拒收。checker读公开A/O/enqueue/drop/D/R记录与原向量，不读私有mailbox/RAM。

重算既有capture无需RTL：

```powershell
python -B -X utf8 code/scripts/run_pcm_waveform_observer_candidate.py --check-capture <capture.txt> --vectors <vectors.txt>
```

每个reset/观察branch epoch单调、观察ordinal仅音频reset归零；seq间隙由完整包显示丢失
形成，旧branch已入队未交付包在reset丢弃。原始装载数与串行完成数分别记录。
该验证只证明数字仿真等价/传递合同，不证明亚稳态MTBF、硬件clockstop、实际RAM映射或STA。
