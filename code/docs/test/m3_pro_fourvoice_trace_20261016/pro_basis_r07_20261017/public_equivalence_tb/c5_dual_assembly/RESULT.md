# C5 双top静态装配补充（当前入口）

**静态源装配已完成，编译/elaboration/仿真未执行，实际组合准入仍待M2。** 本目录按总控后续明确要求新增，覆盖先前 c5_binding 对“未重装配”的当时状态；先前绑定/封包均保留，不改B旧源、旧报告、旧R01/R02或R6-6已冻结源码及28项结果。

精确编译清单为 `inputs/dual_compile.f`，以解包 `inputs/` 为cwd，首行 `+incdir+include`，其余**76个源单元**：M2 C5 observer闭包71源，另加同版冻结旧frame_core/board两源、原candidate wrapper一源、既有midi_public_port_driver和B最终tb_public_equivalence两源。旧全链TB排除，C5共享库/ROM只列一次。73+5=**78个字面module定义**，无重复；module表和逐文件来源/大小/SHA在 ASSEMBLY.json。

直接选用M2决定的1241字节dds_oscillator_leaf，不追加整份原DDS，唯一sine_wavetable_1024保留在m1td_dds_oscillator。两个DUT使用同一个simulation clock/DVI/GSR/pROM源定义，实例各自独立；仅静态路径/身份闭合，不签物理PLL或行为相同。

静态检查发现C5 ZIP没有携带被源码引用的 `sine_table.svh`、`sustain_controller_ports.svh`。同版M2原冻结包 `931b7d2b…6c1ba2` 在 `source_closure/inputs/include/` 与 `sources/` 两处都包含它们；逐字节核同后原样复制到新 `include/`，由清单incdir提供。没有从当前仓库近似文件选替代，没有改算法/端口。9个原ROM保留，两个裸名路径sine_wavetable.hex/triangle_wavetable.hex补同字节alias；所有源码ROM字面路径与include路径都有文件本体。

最终TB SHA `6768bf11f4d18e930f7d989707fe509ad263ec85c9a864729af98307b0a35bf8`，driver SHA `99e40266a46f1606409fa6ef270dd0c6b056dcb511363ae90dfbaf67653df89a`。同一sys_clk_50m/reset/key_n/MIDI同时驱动原wrapper与新observer；公开13pins严格比较、40MHz采样加postponed事件流、窗口1200..12000000与尾拍+1ps保持原TB。原top的38观察口仍NOT_PUBLIC。bytes/reset/ready.drv与plan.json复用R6-2已签原件，本次不重新生成或执行driver。

静态脚本 c5_dual_static.py 只import标准库，以ZIP/文件字节生成新目录，实际exit0，未import运行B assembly/build_sources/selftest/comparator，B新增功能组0。源码本体包 `M3_R7B_C5_DUAL_SOURCE_20261017.zip` 206956字节，SHA `8cdc01ccf36ee4a91d61ca270c076fcf8d20560465679a2a9b52e09f5ea0155d`；CRC、逐成员大小/SHA核同。源码清单中的C5原列表和旧69列表均另存原字节，便于复核。

后续M2可直接核精确清单/源码包，再按其规则批准特定工具版本/argv/cwd/timeout/输出和实际执行。没有剩余文件装配工作交回M2；待办是源合同最终复核及真实执行准入。字面module/include/ROM闭合不是语法/展开/端口/参数/功能正确性证明。B最后comparator的`<=stop`增量仍L0/NOT_RUN，不能声称最终19项全测。HDL/EDA/设备/Git写入0，board_release_allowed=false。
