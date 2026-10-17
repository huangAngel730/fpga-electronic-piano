# A-C5 include / ROM 静态补齐（新增版本）

**已完成本轮标准库文件装配，L0静态路径闭合；编译/elaboration/仿真均NOT_RUN。** 仅新增本目录，旧A、旧C5绑定、R6-4返修包及B原件共453个文件的前后身份一致。原包及原源码未覆盖，无Git写入，无消息回传尝试。

精确清单为`inputs/compile_r7a.f`，以解包`inputs/`为cwd，新增首行`+incdir+include`，原74个源单元保持顺序和字节。仍为76个字面module定义、无重名；9个原ROM载荷保留，增加2个同字节裸名alias，不增加不同ROM内容。没有添加整份DDS，M2选定leaf和既有唯一ROM定义保持不变。

补齐的header从同版M2冻结ZIP `931b7d2bbfd7ac056707542931101ff844b125936762748e344536d9be6c1ba2` 的`source_closure/inputs/include/`取原字节，并核同该原包`sources/`副本及B已封存源码ZIP的header：

| 新路径 | 字节 | SHA-256 |
| --- | ---: | --- |
| inputs/include/sine_table.svh | 5648 | 969fc7d1036e359fc55c3b0ca18eaf3c8a123a146ed95c32a81e52ee10519cca |
| inputs/include/sustain_controller_ports.svh | 827 | 8c51459cd47a7e21609cc02780a93af7d6be0fd5bf2d2278edda92e8a7ef486d |
| inputs/sine_wavetable.hex | 5206 | 1abfd5c47759cd4089f4b39069b3ff0ab388838502b325d9ef7d9e01549ec7f4 |
| inputs/triangle_wavetable.hex | 5210 | a6ee3195ad3a3310de5102531aac9d7773eebc6c31633d72c01b72a7d2461e3c |

两个裸名ROM直接复制各自`inputs/rom/`原载荷，逐字节等同B alias。递归扫描74源及所引用header的字面include、去注释后的.mem/.hex路径均有文件本体；include集合为上述两项，ROM路径集合与B的11个路径一致。具体引用位置、解析路径、每载荷SHA和来源见`ASSEMBLY.json`。这不证明宏预处理、参数展开、运行时参数/输入文件或物理IP正确性。

新源码包：`M3_R7A_C5_INCLUDE_ROM_COMPLETE_20261017.zip`，204660字节，SHA-256 **93ee67ad3983f831b8bd4f49f806d8d048516a3b87f712895e119262a13ead29**；ZIP CRC及全部成员字节核同。保留旧compile/BINDING原件于`provenance/`，旧ZIP未改。原A ZIP仍d24d8cb4…8dcf，旧C5组合ZIP仍2906dd13…9b4f，R6-4原件ZIP仍8e617916…e371，完整身份见OLD_IDENTITIES_BEFORE/AFTER。

实际命令（仓库根cwd）：

```powershell
& 'C:/Users/songdongkuan/miniconda3/python.exe' -s -B code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r07_20261017/public_capture_tb/c5_static_binding/r02_include_rom/assemble_static.py
```

北京时间2026-10-17 19:51:29，exit0，0.781秒，stderr空，无timeout；argv/cwd/PID、UTC、原双流、脚本及Python身份见`EXECUTION.json`。脚本只import标准库，未调用A脚本、R6-4程序、功能自检、HDL、EDA或硬件；A与R6-4新增功能组均0。

此处文件装配补齐已齐。后续由总控封总包，M2最终核源合同、实际时钟/窗口6参数、工具及首次组合执行准入；真实capture、M1语义、Pro物理和板测仍待。board_release_allowed=false。按本轮要求仅本地RESULT，不再跨对话回传。
