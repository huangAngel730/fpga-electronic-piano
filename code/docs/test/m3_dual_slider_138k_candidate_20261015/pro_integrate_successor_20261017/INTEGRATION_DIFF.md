# E1：现场来源绑定的 Pro 接入差异（task-day，L0）

**静态准备DONE；新Pro正式接入PENDING_PRO_SOURCE_OR_PRODUCERS。** 当前HEAD=414e1a9d3ee0617c5e8ba72dd4b22c36122c9926。旧487/4限定L2保留，不新增RTL运行，不修旧闪光FAIL。正式接入仍排在Pro基础四声及M2双音色同版出口以后，board_release_allowed=false。

证据缩写与完整路径/原字节SHA见INPUT_IDENTITIES.json；本地INPUT_ORIGINALS保留42件本体用于核字节，按总控收尾新要求不入最终zip/发布清单，仅引用原Git/文件位置；FINAL_SOURCE_INDEX.md由终末静态核验生成。下文行号均是**原文件**行号，不是引用文档行号。O=历史R05冻结副本，C=当前仓库通用文件，D=旧已签pro_parallel候选；都不自动等于新Pro生产源。

| 缩写 | 现场路径 | SHA256 |
| --- | --- | --- |
| O.top | code/docs/test/m3_r05_functional_integration_20261015/REWORK_WATCHDOG_RUN_02/stage/inputs/sources/m2_fourvoice_timbre_delay_board_top.sv | f2a8f30fef8ad2da26d1d3b80793b727f45806b6d5c78f2a071fb383322639be |
| O.shell | 同一stage/inputs/sources/audio_visual_display_probe.sv | df1f05b4a6a06deddd9d3a2244106ec29bb0d15e5dd808fc9bef9436d710a5cf |
| O.pll | 同一stage/inputs/sources/TMDS_PLL_800_600_60.v | 7d6006749d113207bcc2246d0415c874570db0c92e8563bbd55eea6ed17fce20 |
| O.sdc | 同一stage/inputs/constraints/audio_visual_hold055.sdc | a8791f826c0bd8630483ce28c44636c24e4e28c041a9622d17d0b1764a8f888f |
| C.shell | code/rtl/board/audio_visual_display_probe.sv | 6eca6bb7a4adae483ec4c802530392d3545174b2946d64724081320b317d2390 |
| D | code/rtl/input/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/dual_slider_pro_parallel.sv | c0bbcc715edb573a160ce54c4d01982f15881dd311bdd38131d379059a48fc70 |
| M2合同 | code/docs/M2_双滑块同版接入边界与待定生产者_2026-10-16.md | 06abb92e16e00ecaa5ee15e858897611cda8480c2d1015024f14970fdde41244 |

## 逐项结论与精确停止点

| 项目 | 现场可核事实（文件:行） | 新Pro状态/最小可逆差异/下一责任 |
| --- | --- | --- |
| mode实际生产者 | O.shell:6–8/45–67是五秒自动诊断；:83接mode_pending。D:13–15、68–71只接受40MHz valid/ready；:83–88在pixel沿先更新请求、frame_start锁旧请求，故同沿本帧旧模式、下一帧新模式。 | **UNKNOWN正式生产者**。保留邮箱和帧锁存，只替换诊断源。M2须给操作来源、公开源路径/SHA、去抖/保留valid直到ready、一次操作一次接受和共同复位取消。SOURCE_MODE属于音频诊断，不可充当显示开关；不另占演奏键/引脚。 |
| score实际生产者 | O.shell:60–65/85–90为本地diag_frame及固定note/velocity/duration；不是下载曲谱。D:15–23仅输入及score_ready输出握手接口，不含生产者。TB:224实际`hit=current_frame+120`；M2旧合同的+6举例不代表此TB现值。二者都只是测试计算。 | **UNKNOWN正式曲谱源**。M2提供98bit生产者原件、valid等待时全部稳定、note_id生命周期、reset取消。不得把40MHz直接读取25MHz多位current_frame写成生产接线；不擅在98bit包加epoch字段。 |
| frame零点/epoch | C.scanner=code/rtl/common/video_scan_timing.sv:16–35，复位坐标0/0，rst有效且x=y=0时frame_start；C.score_tracker:347–350复位current_frame=0，:368/386在frame_start更新；D:110–119由同一扫描脉冲推进。O.shell:54–56承认diag_frame与真实帧复位释放有偏差。 | **UNKNOWN跨域同版epoch映射**。必须冻结复位后哪次frame_start定义第0/1帧、命令在同沿的生效语义、源pending如何取消/重启。需要回读帧号时由M2另定握手快照或已批准相对时间协议；本包不自行增加CDC/接口。 |
| accepted唯一复制点 | O.top:476–499共享事件FIFO/valid-ready，:679–682把`shared_event_valid && shared_event_ready`和shared_event_data送u_visual；D:60–67只读复制到显示桥。C.event_bridge:10–12没有音频ready输出。 | **OBSERVED_OLD；Pro复制点UNKNOWN**。M2在新源确认真实唯一握手，复用原64bit数据，显示queue/mode/score ready/drop/desync不得反馈音频ready/PCM。不能把旧字段名同名视为Pro证据。 |
| FIFO与几何 | D:4–7默认640×480/SLOTS8/Y_WIDTH10/PREVIEW120/BASE_NOTE36/NOTE_COUNT49/EVENT_FIFO_DEPTH32；:60参数化桥；C.event_bridge:43–49/84–88为32队列加1在途邮箱。 | 候选合同可复用。不得回退原D写死8队列；八画面槽与32队列分开。display_event_enable正式拟系1（D:90），诊断暂停不是新增用户模式；正式绑定仍须M2决定。 |
| 40MHz核时钟 | O.shell:6、12–13、70–71有ref_clk输入/core_clk输出；O.top:172、679–680将50MHz ref与40MHz core闭接。O.sdc:46–47参考20ns/生成4÷5核钟。 | **OBSERVED_OLD；Pro UNKNOWN**。保留新Pro唯一真正PLL/core生成点，不能整块用D替换旧外壳，因为D不输出core_clk；不得用clock-enable冒称新增40MHz时钟。 |
| 25/125MHz与唯一扫描/出口 | O.shell:70–72单PLL和串行reset，:100–102单scanner，:121–128唯一一拍RGB/HS/VS/DE，:130–134唯一DVI/TMDS；O.sdc:294–295为125/25生成约束。D本身无PLL/扫描/串行器。 | **OBSERVED_OLD；Pro UNKNOWN**。只替换CDC/scene段，保持新Pro唯一扫描、寄存级、DVI出口/端口方向。必须提供实际新PLL配置/目标/锁定/约束及依赖；旧名TMDS_PLL_800_600_60不能证明实际模式或Pro器件。 |
| 当前同名外壳冲突 | C.shell:6–8是250000000/840000诊断常数，:51–52注明50MHz，:67仅clkout0/1，接口没有ref_clk/core_clk；O.shell有第三输出且7018B，C.shell6886B。当前code/build/electronic_piano.gprj:36为GW5AT-60B/PG484，不能替代Pro。 | **CONFLICT_IF_MIXED**。不要把当前C.shell与O.top/40MHz候选按名称拼接。先由M2冻结完整新Pro闭包；本包不修C.shell或搬旧PLL。O.pll:8–10旧60K头与:13–14迁移注释也不是FPG676身份。 |
| 共同复位 | O.shell:22 `sys_rst_n && pll_lock`共同断言事件/控制及串行reset；D:57–58汇合各桥本地释放，:83/99/110供像素消费者。C.reset_sync为异步assert/本域sync-release。 | **UNKNOWN新Pro复位树/端点**。M2保留唯一共同assert来源及扫描/串行边界；mode/score外部producer也需取消旧pending，禁止只复位pixel或只清场景而留邮箱token。七组数据控制同步器不覆盖所有reset/PLL lock路径。 |
| 七组CDC/第二级 | 见CDC_PATHS.md的七行精确静态映射。旧SDC:300–306仅指当时u_visual/u_event_bridge或u_control首级；新D内部事件实例已是u_events。 | **UNKNOWN新网表匹配/CDC**。每组按实际新实例/优化名重新查首级、二级、属性和扇出；不得抄_s0层级就称命中，不用宽泛异步clock-group遮挡缺约束。M2执行并核完整CDC/STA。 |
| 64/98bit bundled | C.package:121–133定义64bit；C.control:32–46定义98bit整包；保持/捕获锚及旧路径见CDC_PATHS.md。旧SDC:308–309 maxdelay10ns，:312–313只有payload定向setup；:314–327的hold是同步器级间。 | **UNKNOWN新Pro有效位数/路径及setup/hold**。M2逐有效位统计、列优化原因，并核数据稳定窗口、真实约束命中、定向setup+hold与完整时序。不能把7组二级hold算作64/98bit数据hold通过。 |
| 1bit mode payload | C.control:49–54单bit邮箱src_data固定1，mode_data不参与功能，toggle来自dst_valid；req/ack仍有实际控制用途。 | **UNKNOWN综合保留位**。如常量payload优化消失需原网表证据，不机械要求恰1条数据路径，也不据此豁免mode req/ack和reset。 |
| 命中闪光/音频 | D:122–132固定flash_active/flash_level为0，旧FAIL暂缓；候选无音频ready/PCM输出。旧L2只检查诊断音频持续，未签真实Pro声音/串行/板测。 | 保留旧FAIL，不扩大到闪光修复。M2/M1在正式新树接入时核同源事件/PCM/期限/欠载无退化；M3在准入后采同版上飘按松、下落连续运动退出、模式/复位/音画原视频。 |

## 到件范围与边界

DISCOVERY_INVENTORY.json冻结三个明确范围：code/rtl/138K_Pro、code/rtl/board、code/build（后者只列gprj/sdc）。本机Pro目录见参考CST/PDF/静态引脚报告，未见Pro RTL/工程/SDC；M2旧合同引用的code/output/m2_m1td_whole_prepare_20261015_06路径本体不存在，只有R05 stage封存副本可读。**这是接收入口/扫描范围内未到件，不声称全磁盘或其他成员机器没有Pro源。** 新Pro source/ROM/top/trace及正式producer未由M2提供身份签，故未知项不填默认值。

历史DELIVERY.json中的submitted=false/pushed=false是旧创建时收据，不是今天Git发布状态；旧源码/包已在本基线可见。本次新静态包未提交/推送，统一交总控串行发布。新Pro正式接入条件与最小可逆操作见WIRING_PROPOSAL.md。本包不代签基础/双音色，不生成CST/SDC/RTL补丁或码流，不增加模式、频谱、菜单或实物调用。
