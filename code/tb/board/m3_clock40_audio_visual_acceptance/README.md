# M3：封存 L 的 138K／40 MHz 音画联合自检

写入范围仅本目录与 `code/scripts/run_m3_clock40_audio_visual_acceptance.py`。不修改封存候选、正式 RTL/ROM/公共包/顶层/CST/SDC/PLL/STAT、旧测试或共享登记文件。M2 复核后统一登记，无新增任务编号。

## 输入身份与复用

只从 `code/rtl/138K_try/hold_trials_20261005/M3_138K_Hold修复证据_20261005.zip` 提取 `L_locations_guard065`。整个 ZIP SHA-256 固定为：

```text
c4eeefac8c28e3ebc01475177601a65abfc0da6f314b1c80f94b223ee9fa5b50
```

复用此前 M2 已审查的 PCM runner **提取函数**（SHA `755ee24965d35835536dc6698a16c72e4b93cfd8cae8fd5f3dc009e025181c9c`），不执行其 PCM 串行测试。56 份提取件保持原字节；仿真另生成副本，只重定向封存绝对 ROM/include 路径。CRC、每份原件及仿真件 SHA 在 `source_manifest.json`；不以工作区 ROM 替换封存原件。

新刺激生成时，从 `code/tb/audio_out/m3_clock40_pcm_serial_acceptance/tb_normal.sv` 提取原 `byte_midi`（仅把日志句柄 `monitor.fd` 改为 `fd`）；从 `code/tb/input/visualizer/tb_renderer_geometry_equiv.sv` 原样提取整数几何 `golden()`。所有复用文件与生成 include 的实际 SHA 另列清单。复用 `tb_audio_visual_coexistence.sv` 的音频-only 对照思路和 `held_bar_semantics_20261002.md` 的长条合同，不运行旧缩小扫描/PLL 恢复场景。

## 测试边界与检查方法

本测试为子系统接线 harness，非原整机顶层的新完整验收。直接提供周期 25 ns 的 40 MHz 系统时钟、周期 40 ns 的 25 MHz 像素时钟；两者真实运行，扫描器为封存 `video_scan_timing` 默认 800×525 总时序／640×480 有效区，16.8 ms 一帧。不改扫描参数、不缩短一帧。125 MHz 仅为未参与判定的时钟占位；没有 PLL 模型或恢复刺激。

真实 31250 baud 8N1 UART→原 MIDI parser→原 32 项公共 FIFO→原四声部核心及帧请求；接受后的事件才进入原 `visual_event_bridge`→原 `m3_visualizer`→原渲染器。另一条相同原 UART/FIFO/core 组成独立 audio-only 对照链，不受视频 ready 影响。测试观察层级只读用于自检，不是生产模块间新增耦合。

显示模式保持原诊断顶层前 5 秒默认的实时长条模式；曲谱注入和自动模式切换关闭，不宣称下落曲谱／命中闪光模式在本轮全验。原 wrapper 的上飘条起点参数是 `SCREEN_HEIGHT-10=470`，尾端 480；不是把旧说明中默认 400 擅自写回设计。CC64 只影响音频，不延长物理按键条。

独立 Python 期望从真实 UART 字节、音频接受和视频消费记录建立事务账本，从事件身份和实际帧边界计算发布音符／held／位置／速度／key_down；不读取私有 `valid_q` 等状态作为期望。持键条头每帧升 4、尾端固定；松键后两端同升，帧边界发布旧快照。边界同拍事件归下一帧。

每个完整帧逐像素与旧 `golden()` 比较，另保存全部 525 行的 800 像素 RGB FNV32 摘要、有效像素数和水平同步数；Python 根据独立发布参考重算各行摘要。原扫描坐标、消隐及同步统计全部检查。帧起点 x=0 是发布边沿之前采样的旧快照像素，明确按该一像素管线语义核对，不隐去整帧。

DVI 使用明确命名的 `dvi_boundary_stub`，仅保存 RGB/sync 边界，无 TMDS 编码和引脚电气模型。没有巨大逐像素波形输出。全部实际 PCM 提交记录保存请求 ID、左右 PCM24 和 audio-only 对照结果，逐事务比较；按完整视频帧汇总全部提交和欠载计数。不是重做 PCM24→PCM16／PT8211 串行数学验收。

## 场景与必须满足的覆盖

- 正常：两个实际音符按下前、按下并保持、松键、松键后一帧发布；另真实第三音符 On/Off 与 CC64。六个完整视频帧，2,520,000 像素比较、3150 行独立摘要比较。正常先行执行得到 4838 组 PCM 比较，逐帧提交 `[806,806,807,806,806,807]`；最终结果以完整运行收据为准。
- 明确标注的短时视频背压夹具：新 harness 仅在桥到场景的握手边界加 4 ms ready/valid gate，期间四个实际事件仍准时由音频接受，视频随后按序消费，不丢失、不重复。
- 明确标注的有限队列溢出夹具：36 ms 背压期间真实 UART 发送 36 个 On/Off，容量为 32 队列＋1 在途 mailbox。合同允许后 3 个显示副本丢弃，饱和计数／失步提示须准确，音频仍接收全部输入；恢复后仅交付保留的 33 个副本。不是要求无限背压永不丢事件，也不把此夹具当成正常无丢帧演示。
- 两个错误实现仅生成在新的 runtime 副本：将实际音符 60 映射为 61；将音频 valid/ready 接受条件错误绑定视频背压。均须实际编译、运行完成，再由独立检查器针对行为拒收，编译失败不算反例成功。
- 损坏捕获检查拒收空数据、缺 END、零事件／零 PCM、缺完整帧／行／发布、错误像素摘要、错误 PCM、重复视频事件和缺夹具／欠载证据。超时及工具失败一律非 PASS。

首轮新夹具在像素上升沿解除背压，造成观察与采样的调度竞态；只改新夹具为下降沿切换后正常先行测试通过。首轮原日志保留在 runtime，不据此归咎或修改视觉设计。若后续发现真正实现缺陷，只交具体失败场景给可视化负责人。

完整四场景实际结果：正常及溢出夹具各六个完整帧／4838 组 PCM 比较，两个正向共 12 帧、5,040,000 次像素比较／6300 行摘要独立核对／9676 组 PCM 比较，欠载均 0。正常 6 音频事件＝6 视频事件；溢出夹具 36 音频事件＝33 视频事件＋3 合同允许的副本丢弃。两种错误实现均 compile=0／simulate=0 后被针对性拒收，19 个损坏捕获反例通过。结果及全部实际命令见 evidence/receipt.json。

## 命令与原证据

仓库根目录，Python 3.10+、ModelSim SE-64 2020.4：

```powershell
python -B -X utf8 code/scripts/run_m3_clock40_audio_visual_acceptance.py --repo-gate
```

异机可指定 `--archive <原封存ZIP>`、`--modelsim-bin <ModelSim/win64>`。`--case normal|overflow|wrong_note|wrong_audio` 仅用于局部调试，收据 `partial=true/ passed=false`，不能代替最终四场景验收。

完整成功运行之后发布证据（evidence 必须尚不存在，禁止覆盖）：

```powershell
python -B -X utf8 code/tb/board/m3_clock40_audio_visual_acceptance/publish_evidence.py --run <本目录下runtime/run_*的路径>
```

证据包含 source_manifest、receipt、正负编译／仿真原日志、完整扫描／事件／PCM 捕获。工具原数据用 Base64 无损保存以避免 Git LF／尾空格规则改变原字节；raw_manifest 记录原字节 SHA 和长度，解码后必须与运行收据一致。

```powershell
python -B -X utf8 code/scripts/run_m3_clock40_audio_visual_acceptance.py --check-capture code/tb/board/m3_clock40_audio_visual_acceptance/evidence/normal_capture.b64 --scenario normal
python -B -X utf8 code/scripts/run_m3_clock40_audio_visual_acceptance.py --check-capture code/tb/board/m3_clock40_audio_visual_acceptance/evidence/overflow_capture.b64 --scenario overflow
python -B -X utf8 code/tb/board/m3_clock40_audio_visual_acceptance/publish_evidence.py --decode code/tb/board/m3_clock40_audio_visual_acceptance/evidence/check_repo.b64
```

仓库旧门禁会写正式 `code/output`，故本 runner 在本授权目录内建立内容／原字节 SHA 一致的隔离仓库快照，执行**未修改的 check_repo.ps1**，并核对前后全部输入不变。结果明确标记 `content-exact isolated snapshot`，不冒称原工作区直接执行。临时 Git 长路径配置仅对副本生效。不改共享看板、当前状态、验证编号；M2 统一登记。

提交前 M2 新增复核脚本/登记文件后，仅补跑最新内容快照的仓库门禁，没有重跑原 PCM 串行验收或改写四场景原证据。补跑记录与原日志在 `evidence/latest_repository_gate.json` 和 `evidence/check_repo_latest.b64`，后者原字节 SHA 由前者独立记录；旧 receipt/check_repo 原件保留，不能把两次门禁的输入范围混写。

本轮最高为 L2 自检仿真／限定 L3 发布几何及完整扫描摘要独立对照。未验证 PLL 电气／启动恢复、TMDS 编码、显示器识别或实屏、PT8211 模拟输出、Gowin 综合／新 PnR／STA、布线后仿真、上板、烧录、长期整机稳定性及曲谱模式全覆盖；不关闭 T055 最终整机和上板验收。
