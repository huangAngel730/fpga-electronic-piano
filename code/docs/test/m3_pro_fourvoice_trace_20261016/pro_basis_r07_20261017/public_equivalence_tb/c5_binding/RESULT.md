# R7-B 对 C5 的新增静态绑定

状态L0：已按M2发布C5决定核 source ZIP SHA/CRC、逐成员SHA、compile.f存在性、71单元/9ROM/73字面module无重复，以及DDS原件 `[0:1240]+LF` 得1241字节leaf。STATIC_BINDING.json保留逐源/ROM/模块与派生关系，清单基准为解包后的inputs目录。没有执行B程序/HDL/EDA/设备。

C5包SHA `2fc5518a35600f67d025aa2efe55e6b436daa5a04b592053f7326385b42134fb`；原DDS SHA `9588637c20348c7df8eda5ab5bca780de4468aec607fc9d4b918df63f746c556`；leaf SHA `303e3a9927e743d4149ceae4bb8754ebb8abdfb14638d407254b8e555dfcd3bd`；共享ROM尾SHA `4b1d526758efd05c2780d24b8116bc3660620aa98f639b3a2813e633c17d216f`，唯一sine_wavetable_1024仍在m1td_dds_oscillator。没有追加整份DDS、修改M1算法/端口或混入未发布C4。

71是C5 **observer仿真源闭包**（69减旧board/core/TB三件，加C3四件与DDS leaf一件），不是B双DUT等价TB的完整编译单元数。B旧原/新top双装配、外部比较TB/driver和旧基线关系仍须M2对最终精确候选绑定后重装配；本次没有擅改原assemble或恢复已用B额度。旧75等历史装配清单和原失败保留，不能把C5决定当作其编译/等价通过。

B原RUN_01的15项与RUN_02的4项仍各绑定原源码，最后`<=stop`增量继续L0/NOT_RUN，不声称最终19项全跑；D既有22项及原件冻结。FROZEN_B_REFERENCES.json记录旧报告/收据清单身份。本次只新增c5_binding及静态元数据脚本，不更改旧B/D功能源、报告或消费台账。

静态元数据脚本 `code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r07_20261017/public_equivalence_tb/c5_binding_static.py` 实际exit0；首次临时ZIP成员查找exit1已单列FAILURE_HISTORY。时钟/DVI stub与旧PLL头仍只用于仿真；compile/elaboration/fullchain NOT_RUN，execution_admission=null，board_release_allowed=false。未提交/推送，交总控统一发布与M2最终复核。
