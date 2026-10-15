# 138K C/31005 四声部双音色与立体声延迟：新整机物理后继

2026-10-15，M2 自审。基线是 T056 L 的**隔离拷贝**，叠加 M1 原封存 ZIP `5c18926ae307301e91ec0e44dcf4a48b2fb57adec71ad46c494b14df59913b06` 与 M2 帧事务适配；正式 top、原 L 源/ROM/CST/SDC 均未改。精确准备目录 `code/output/m2_m1td_whole_prepare_20261015_06/`，本次 Gowin 原结果目录 `code/output/m2_m1td_whole_gowin_20261015_02/`。失败前置 `_01` 是 runner 的 Windows 常量错误，工具调用 0，保留原收据。

- 单次 `gw_sh run.tcl`、`run all`、目标 `GW5AST-LV138PG484AC1/I0`；退出 0、1171.498 秒、未超 1200 秒。完整综合、布局、布线、STA 和新 `.fs` 实际产生；新输入及工具执行前后 SHA 一致。工具 `gw_sh.exe` SHA `4c172d4c0d2a4c7ef5c764d091a315cbcde2127573554bfd7d09ac6f2e5ea535`。
- 新资源：Logic 27879/138240，Register 9582/139095，DSP 50/298，BSRAM 28/340；延迟 buffer 的映射包括报告中的 SSRAM 967，而 28 BSRAM 都计作 pROM；这是实际报告量，不是架构预算。
- Setup 最小 +1.736 ns、Hold 0.000 ns、Recovery +1.410 ns、Removal +0.492 ns；`sys_clk` Fmax 42.984 MHz 对 40 MHz；三个业务时钟 `sys_clk`/`video_pixel`/`video_serial` Setup/Hold TNS 0、违例端点 0。音频新层级中实际至少记录 1 条 Setup 和 8 条 Hold 路径。引脚表 14 个端口、音视频电压声明、音频输出 max/min 约束、视频 CDC 活动约束与报告均通过原平台 checker 保留的判据；额外 VCCO 实际测量仍未做。
- 原 L 平台 checker 的四项不适用旧身份被**精确限定**：两条旧音频 FF INS_LOC/定向路径已在这份新副本禁用，旧 DSP=46/BSRAM=20 不能要求新声部/效果组合相等。专用 checker 仅允许这四项已知差异，其余引脚、CDC、时钟、时序和资源容量检查原样运行，退出 0；报告原件 `PHYSICAL_REVIEW.json`，`board_release_allowed=false`。
- 新 `.fs` 在本机 `.../impl/pnr/m2_fourvoice_timbre_delay_board_top.fs`，37,517,739 字节，SHA-256 `5f4960d91ffb7ccd22ac5f79526cf45b55bbc20836285a5f9b328cc3cfc27c10`。证据 ZIP `M2_138K_M1TD_整机PnR_STA_20261015.zip` 132,953 字节，SHA-256 `17e71ebd5b54743fd0214af5fbfdfd1a4cca4eddbcedab56f7b3df7b3ca521ff`，含 14 原件及 manifest；为节省仓库体积 ZIP 不包含 `.fs`，须到精确本机输出取件并独立核 SHA。stderr 记录 `alog` 用户缓存日志打开失败，但 Gowin `run all` 退出0并生成完整报告；原 stderr 保留。
- 新组合的真实 M1 整机 RTL 仿真**仍未执行成功**：本机 Icarus 的旧尝试触发 M1 分配器内部类型断言及 90 秒超时，未运行遗留 `.vvp`。ModelSim 当前机器不可用。追加了 R04 自包含 69 编译单元的增量 TB 输入（四音同时发声、第五音接收时仍四槽、复位、帧 833/834 拍期限），源/ROM 与本次物理副本同源；91 个成员、40 处 ROM 路径可逆校验通过。R04 ZIP SHA `1101f1af0809530a150143456aab8ff9a1c66373e9ccbc174c6459e8c916b3bf`。**TB 尚未实际编译或运行，不能据其设计断言声称通过。**同目录 `verify_portable_inverse.py` 验证 ZIP 及可选原 stage。

**阶段结论**：新整机组合资源、布线和受约束时序的精确离线报告通过；功能准入尚缺真实M1板级仿真（尤其四音、第五音、帧期限），新音频 FF 定向路径旧约束已停用而新端点复核需要针对网表落定。禁止把这份 `.fs` 作为可下载版本，也不把旧 L 单路 `.fs` 或 60K 四声部 STA 混用。没有下载/Flash/接线/设备操作。建议 M1 在有 ModelSim 10.7 的机器用 R04 的 `inputs/compile.f` 实跑一次并交 vlog/vsim 原日志、退出码/完整PASS和前后 SHA，M2再做功能与物理组合签收。
