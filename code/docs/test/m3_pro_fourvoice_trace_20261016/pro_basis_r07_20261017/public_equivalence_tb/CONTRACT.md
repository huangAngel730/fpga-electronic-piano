# R7-B 外部行为比较合同

仅观察冻结原wrapper m2_138k_pro_fourvoice_candidate_top和新m2_138k_pro_fourvoice_observer_top_r06的既有外部输出；同一sys_clk_50m/reset/key_n/midi_rx直连两者，无任何DUT私有层级引用。原top没有38obs口，全部NOT_PUBLIC，不能比较或反推M1内部语义。

13位顺序：bit0 BCLK、1 LRCK、2 DIN、3 PA_EN、4 UART、5/6 TMDS clk_p/n、9:7 data_p、12:10 data_n。所有既有外部输出在窗口内严格相等且已知；允许差异表为空。观测扩展不是原外部行为差异，也不以新obs控制旧输入。TMDS只比两份模拟输出，不签HDMI/物理。

唯一时基是P10 clock_plan_sim.v：模拟125/25/40MHz起始0，首40MHz上升沿12.5ns，lock在1000ns置1；两份PLL实例同源同相。TB外部50MHz首沿10ns，driver/ref40MHz首沿12.5ns，同一40MHz上升沿PRE_NBA采样。原clock stub本体/SHA随装配清单；不是Pro PLL实测。

输入原件只读复用R6-2 RUN_02/products的bytes/reset/ready.drv及plan.json，1122320拍；reset在0/800/1000480/1002480切换。driver只驱动外部MIDI/reset，ready输出不接生产top；event_valid固定0仅关闭driver自身事件日志，不能冒充DUT没有事件。key_n固定11。比较窗口冻结cycle1200到12000000；窗口前原始行仍保存、不计相等。两份UART按40MHz/115200整除下取347拍、8N1、七字段STAT解码，保留reset段和不完整尾部；没有完整STAT则PENDING_NO_COMPLETE_STAT，不签完整等价。窗口足以容纳最后reset后默认10000000拍上报周期及一条报告，但这只是计划，未执行证明。

assembly.py从原固定SHA archive读取69列表，不修改原件；去旧TB，加入原wrapper和R6C3指定4文件，并加入本TB与原driver。original.f/observer.f只是两个来源子清单；TB同时引用两top，**实际拟编译只用dual.f**。ROM原字节按源码字面量默认路径建立别名并列SHA，不改算法或参数。R06C3四源SHA核OBSERVER_EXPORTS；不选仓库同名近似文件。

原69列表不含dds_oscillator定义，其本体存在于原archive。新装配不给它擅自加项，输出PENDING_M2_DDS_LIST_DECISION／HDL_compile_allowed=false；这是词法闭包差额，不是实际elaboration失败证据。M2需决定精确允许的列表及真实执行组合。所有编译/仿真命令目前NOT_RUN，不调用旧T007/P7。

R01后总控发现40MHz采样会漏沿间公共输出变化。最终TB另在任意公共13位pins变化时以$fstrobe写postponed区稳定快照，同timestamp合并；窗口起点另写anchor。比较包含起止timestamp（29987500至299999987500ps），尾拍NBA/postponed后等1ps再关文件。它检查每个稳定仿真timestamp的行为，不签同timestamp内部delta毛刺或物理；DVI stub六个data脚为常量的模型限制另保留，不能据此签真实TMDS。

未来获准后重新装配最终源码，用dual.f/top=tb_public_equivalence并指定+TRACE=独占路径、+EVENTS=独占路径；实际工具/版本/argv/timeout/许可由M2另签，本文不是运行许可。R01/products/assembly内TB是首轮冻结版，**不能直接作为修复版最终装配**，须按FILE_SHA最终源重新冻结/生成列表。完成输出每拍CSV和独立事件CSV(time_ps,original,observer)，stdout唯一EQUIV_END cycle=12000000及EQUIV_EVENTS_END stop_ps=299999987500。equivalence.py --csv ... --events ... --stdout ... --output ...同时核采样行/事件流/首差异并解UART，缺事件流不得签完整公开行为比较。此比较器不认证生产者或捕获真实性，R7-D另封身份；即便相等，真实等价和G0–G3仍由M2复核。
