本地 MIDI 导入独立候选（M3 任务5／B，2026-10-15）

功能：选择本地SMF文件，严格解析为现有T057 JSON，调用冻结原编码器生成records.bin／upload.bin，使用独立离线读回器核对事件、时间、帧及CRC。仅Python标准库，无需安装pyserial或MIDI库。本工具没有上传、串口、下载、联网、播放或音频合成命令。

在仓库根目录执行（输出目录必须全新）：
python -B -X utf8 code/software/score_midi_import_candidate_20261014/midi_import.py import --input "E:/your/local/score.mid" --score-id 1 --output code/output/score_midi_import_manual_001

使用本地文件选择框（需Python自带tkinter和可用桌面）：
python -B -X utf8 code/software/score_midi_import_candidate_20261014/midi_import.py import --choose-file --score-id 1 --output code/output/score_midi_import_manual_002

独立复核已有输出：
python -B -X utf8 code/software/score_midi_import_candidate_20261014/midi_import.py verify --score code/output/score_midi_import_manual_001/score.json --records code/output/score_midi_import_manual_001/records.bin --upload code/output/score_midi_import_manual_001/upload.bin --output code/output/score_midi_import_verify_001

软件验收与封存（自行指定全新目录，不调用RTL或旧专项）：
python -B -X utf8 code/software/score_midi_import_candidate_20261014/run_acceptance.py --output code/output/score_midi_import_acceptance_NEW

可选 --source-description 和 --license-note 记录用户提供的本地来源及授权说明；不替代授权证据。score_id范围0..4294967295，session范围1..65535。CLI成功退出0，输入／核验失败退出1，输出已存在或参数错误退出2。已有目录拒绝覆盖；失败若已创建目录则保留receipt.json及已形成产物，不能把其中产物当作成功导入。

输入子集与映射
1. Type0单轨、Type1同时多轨；只支持PPQN，不支持Type2异步模式、SMPTE division或RIFF/RMID包装。标准MThd六字节头、严格MTrk数量／长度，每轨末尾必须有唯一合法EOT，文件尾不能残留数据。
2. 只传NoteOn／NoteOff。channel0..15、note0..127、velocity0..127原值保留；零力度NoteOn转NoteOff。NoteOff的release velocity保留。channel9仍只是音符事件，不代表General MIDI打击乐还原。
3. 不给轨道重新分配声部或channel。顺序固定为绝对MIDI tick、track索引、轨内事件序号；T057无track字段，来源保存在provenance。相同channel/note重叠、跨轨配对的NoteOn／NoteOff、无匹配NoteOff及结尾未结束音符均拒收，不猜测轨道身份，不补造收尾事件。不同track的不同音符或channel可正常合并。
4. 默认tempo500000微秒／四分音符；Type1 tempo仅来自track0。相同tick的不同tempo冲突拒收，同值重复可接受。累加的是精确有理绝对时间，最后统一取整：tick=floor(exact_sample+1/2)，恰半个样本向上，不逐段截断。两个时间量化为同一sample时仍保持上述稳定顺序，不隐瞒精度限制；每个输出事件记录精确分子／分母及原始tick。MIDI绝对tick和结果sample tick均限u32。
5. CC（含延音踏板）、ProgramChange、PitchBend、Aftertouch、SysEx及系统事件明确拒收。不会静默删掉改变音色／力度／延音的指令。T057本身没有这些事件字段；扩大支持需另行受控接口工作。
6. 允许tempo、EOT及明确白名单注释：文本meta01..09，tick0的两字节sequence number，有效time/key signature；注释身份与轨道结束时间记录但不写T057。不保证原曲结尾空白时长或记谱信息。channel-prefix、MIDI-port、SMPTE-offset、sequencer-specific及未知meta拒收。
7. 容量1..512条音符事件，包括NoteOff；513条不会截断或切片冒充整曲。资源边界：文件16MiB、256轨、100000个解析事件、单条meta64KiB、VLQ最多四字节。超界非零退出。

输出
score.json：原合同严格字段，不向其中塞入provenance／track。
provenance.json：源文件SHA、tempo、轨／事件／字节位置、精确时间、未编码注释及来源说明。
records.bin：原编码器8字节记录。
upload.bin：原编码器BEGIN／DATA／COMMIT字节，仅文件，不发送。
readback.json：独立读回核对结果。
receipt.json：输入／实现／解释器／冻结依赖及产物SHA、状态、退出码、未进行硬件操作的标识。

实现依据与冻结身份
原编码器：code/software/score_transfer_v1/score_transfer.py
SHA256 8e2a065dcea4fef997da2b0fda7e16a314c65c436b654903ca388be407ddfc07
原协议：code/docs/hardware/score_transfer_v1/PROTOCOL.md
SHA256 431b5cd7ae678c97bcb0be720a775b51a031f096161a0dbef36bdeea5f41f15b
导入时核原件SHA，不通过改期望或换编码器放行漂移。独立读回器不复用原parse_frame／CRC／decode。
SMF资料入口：https://midi.org/standard-midi-files-specification

验证和交付边界
软件正负例和原编码器集成结果以最新run_acceptance输出receipt.json和原stdout/stderr为准，不能用本说明代替执行结果。
项目可访问路径未找到有可核来源的真实.mid；补查包括忽略目录时，15个历史输出子目录拒绝访问，因此不声称绝对不存在。开发／边界输入均明确标为合成夹具，真实用户文件验收待补。文件选择框真实桌面交互单独标待实测，不把CLI测试称作GUI操作通过。
等级为L0／L1及本地软件自检；没有新增RTL仿真、FPGA ACK、播放、发声、综合、STA或上板结论。未提交／未推送，全部本窗口自审，M2最终签收待进行。
