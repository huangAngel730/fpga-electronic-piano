真实下载MIDI输入的离线限定验收（M3，2026-10-15）

本目录只补已发布任务5/B的真实网上输入，不重写解析器、T057合同或原编码器。
inputs下两份MIDI原件来自SOURCE_RIGHTS.txt列明的第三方CC0来源，字节未改。
一个真实Type0短旋律通过；另一真实Type1八轨文件因不支持的meta0x54拒收。
另行生成的多轨／变速／容量与损坏输入均是开发夹具，不算真实用户输入验收。

运行（仓库根目录；输出必须全新，不下载、不串口、不调用RTL）：
python -B -X utf8 code/software/score_midi_real_input_acceptance_20261015/run_real_acceptance.py --output code/output/score_midi_real_input_NEW

输入路径：已下载本地.mid → 原严格导入器 → 原T057 JSON/编码 → 已发布独立离线读回。
额外independent_oracle.py重新读取MIDI字节，使用Fraction时间累计，与原导入器的
整数分子算法分开；真实短旋律再与手工从原字节转录的22音符/时值表交叉核。
逐条输出原文件位置、轨道、绝对MIDI tick、精确样本分数、取整结果和8字节记录。
转换绝对时间到48000Hz样本，最近整数恰半向上；不把MIDI tick当样本tick。
同刻顺序为MIDI tick、track、轨内序号；原channel/note/velocity保留。
离线上传字节重建与CRC复用已发布独立decoder，不调用原encoder解析函数。

每步骤最多90秒，软件总预算300秒，新输出拒覆盖；失败保留命令、双流、退出码、
来源和源码／依赖前后SHA，不原样盲重试。运行器不自动启动浏览器、网络或实体设备。
封存包括原文件、权限说明、严格JSON、records.bin、upload.bin、逐条读回、负例日志、
工具身份与源码快照、完整manifest及ZIP CRC/SHA核验。

源码只读依据：score_midi_import_candidate_20261014、score_transfer_v1及T057 PROTOCOL。
没有实体UART READ/ACK，离线decode不是FPGA应答、播放或发声。
真实显式变速／多音符轨道成功验收仍未覆盖，合成夹具证明的范围必须分开列明。
GUI实际文件选择不属本次CLI离线补验；由独立桌面任务窗口处理。

实物边界：138K C版和Dock31005已确认，不再索取板型确认。无实测设备访问/读数，
Bank3/4/5电压、外接MIDI适配器FPGA侧电平与共地，以及启用HDMI时方向／供电均待测。
未经M2放行不接未知电平、不下载/烧录；本任务不重做C3固件/APK、T060 A/B或N32长程。
M2最终限定复核待进行；本轮不执行git add/commit/push或编辑共享状态／编号表。
