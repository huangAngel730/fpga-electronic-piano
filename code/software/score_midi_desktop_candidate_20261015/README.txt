PC 本地 MIDI 桌面导入、严格预览和确认导出（M3，2026-10-15）

这是原 score_midi_import_candidate_20261014 的独立桌面外壳，不改导入器、原编码器或
T057 协议。不联网、不打开串口、不自动播放、不生成声音，也不执行 RTL/EDA/固件。
它没有“发送”按钮；upload.bin 只是原编码字节文件，离线读回不是 FPGA ACK。

在仓库根目录启动（Windows；Python 标准库与 Tk 8.6；不安装任何依赖）：
python -I -S -B -X utf8 code/software/score_midi_desktop_candidate_20261015/desktop_gui.py

可指定全新工作目录及预选本地文件（仅预选，不自动导入或导出）：
python -I -S -B -X utf8 code/software/score_midi_desktop_candidate_20261015/desktop_gui.py --workspace code/output/score_midi_desktop_manual_001 --input "E:/scores/example.mid"

使用步骤
1. “选择本地 .mid”：选择已有 .mid/.midi；取消选择不改变当前预览。填写来源/使用权限，
   score_id 为 u32、session 为 1..65535。来源文字不等于已核授权，请附实际许可原件。
2. “导入并核验预览”：后台只调用原导入器CLI一次，私有进程树最多90秒，不重试。
   原导入器生成严格JSON→冻结原编码器→独立帧/事件/CRC离线读回；非零/超时立即拒收。
   本新预览模型另用独立SMF字节遍历和Fraction时间轴复算全部事件，核原始receipt、
   source/provenance、JSON、records.bin、upload.bin、readback及SHA；错误不得进入预览。
3. 预览显示严格JSON所有字段、Type/轨数/PPQN、默认与显式tempo、采样率、容量/剩余、
   最后事件样本/秒，以及全部逐事件track/channel/note/velocity、MIDI tick、sample tick、
   精确样本分数及原8字节记录；可横/纵滚动。绝对有理时间累计，最近整数、恰半向上，
   不逐段取整、不把MIDI tick当样本。最后事件时刻不是带尾部空白的整曲持续时间。
4. 检查后点“确认并导出”，输入全新文件夹名称，再确认。目录必须不存在；拒覆盖。
   导出前重新核输入/依赖/全部预览产物，导出后重新离线核同；没有确认就不创建输出。
   源文件改变或缓存篡改必须重新选取/导入，不能导出过期预览。

输出与失败保留
workspace 必须全新，默认在 code/output/score_midi_desktop_<uuid>，每次导入有新的
stage_<token> / logs_<token>。stage保留原五产物和原receipt；logs保留真实argv/cwd/
显式环境、stdout.bin、stderr.bin、process_receipt.json、desktop_execution.json、
preview.json（成功才有）。导出原件逐字节不变，另加desktop_export_receipt.json。
每次导入另保留dependency_before.json与finally中的dependency_after.json，含四项冻结
依赖及解释器实际SHA/读取错误、前后是否相同和原始异常；非零、超时、取消同样留存。
后置证据错误不得覆盖原始导入错误；成功路径依赖漂移或证据写入失败都拒收。
每次preview/export另留operation_<token>_start.json及_receipt.json，含新核心三个模块与
解释器前后SHA、输入身份、结果/错误/时间；预检失败也留痕，不把失败当作可导出预览。
取消/失败不删除阶段证据；部分导出保留FAIL收据，不得当成功目录使用。不覆盖旧尝试。
工作线程不调用Tk；队列由主线程轮询。busy禁重复启动，操作token屏蔽旧/关闭后结果。
Windows可移植路径边界（不依赖系统长路径开关）：以UTF-16码元计数（不是字符数），
普通完整文件路径最多259码元（MAX_PATH=260含NUL），目录最多247码元；单段最多255。
workspace必须给stage/logs/operation全部固定后缀预留空间，因此完整workspace最多198
码元，最长后缀是\\logs_<32位token>\\desktop_execution.json（61码元）。创建workspace前
逐一预检原导入器全部score/provenance/records/upload/readback/receipt文件，以及本工具
日志/operation文件；超限抛WINDOWS_PATH_LIMIT，明确actual/limit/path，不启动子进程。
输入路径和确认导出目录/每份导出文件同样前置检查；路径错误不替换当前选择，不创建
新导出目录、不启动worker。独立runner也在创建日志/子进程前核路径。请由用户明确选择
较短路径；工具不改LongPathsEnabled、不用\\?\\命名空间/盘符重映射，也不静默搬运输入。
输入/产物/冻结依赖的最终文件项在resolve之前拒绝符号链接（INPUT_FILE_SYMLINK），
包括选择入口和重新核验入口；不把它扩大成扫描或禁止全部父目录链接。冻结SHA照常核。
使用-S/-s不加载全局site/.pth或用户site；原CLI所在目录仍可加载冻结offline_readback。
Windows子进程以挂起状态创建，先绑定private kill-on-close Job再恢复；超时/取消仅
终止本窗口拥有的进程树；Job绑定失败则子进程不执行。不按名称杀别人的Python进程。
应用关闭会取消worker并等待清理，超过5秒明确提示而不冒称已经完成。

保持原输入支持边界
Type0/1、PPQN、1..512条NoteOn/Off；零力度NoteOn归一NoteOff；同刻按原MIDI tick、
track、轨内序号稳定排序。channel/note/velocity保持，track只在provenance，不写T057。
不支持的CC/延音踏板/弯音/音色/压力/SysEx/SMPTE/Type2及不支持meta明确拒收；
同channel/note跨轨身份歧义、重叠、未配对/未结束、畸形/截断/超容量均拒收。
不自动删除语义事件、重分配通道或补NoteOff；不伪称还原General MIDI音色/打击乐。

真实文件边界
已备真实网上CC0原件和出处见只读 score_midi_real_input_acceptance_20261015/SOURCE_RIGHTS.txt。
MIDI_sample_2018-03-21.mid（GolhaMedia）300字节，SHA256
c0a8cb9f1ba3496a00367786a2b4ee5e0580be7b4bfbf0891b75e3b7475f634c：
Type0/1轨/默认tempo/44事件/末事件384000样本，桌面新验证可使用原字节。
charge.mid（Beatscribe）真实Type1八轨文件因meta0x54必须拒收，不删事件伪造成功。
真实显式变速/多轨成功输入目前未具备，合成边界夹具不能冒称真实输入验收。
原真实补验封存包SHA256 4529de965b76e70b6bbbfba02b33e86eff48afb4a0307a51dd490e6660644eb0
保持不变。新的桌面验收结果以run_acceptance产生的原日志/退出码为准。

测试与实际验证范围
Controller无需Tk，可注入runner做异常/生命周期测试。默认runner才是实际私有Job调用。
DesktopApp(root, controller, chooser=None, directory_chooser=None, confirm=None)支持注入
选择/确认回调以做Tk自身按钮与事件循环smoke。此自动smoke只能证明Tk部件/回调/显示，
不是人工实际操作Windows文件选择框；native CUA不可用时不绕过工具限制冒称实测。
真实picker人工选择/取消仍须由用户桌面操作后留证；未运行阶段必须明确待验。
实际软件正负例和Tk smoke单独记录；不重复旧已签40项，不关联其他实现对话。
原输入/导入器/decoder/encoder/protocol前后SHA、命令/退出码及失败历史由本任务封存。
本任务不改共享任务看板/当前状态，不冒签M2最终验收或任何上板/电气/STA结论。
