# A 对 M2 C5 的新增静态绑定

以SOURCE_DECISION_R06C5.json指定SOURCE_CLOSURE_R06C5.zip为准，原ZIP SHA为2fc5518a35600f67d025aa2efe55e6b436daa5a04b592053f7326385b42134fb。逐载荷按M2决定核字节/SHA，保留原71条compile.f及9 ROM、73个字面module。

新`compile_r7a.f`在原71条之后仅追加未改的R6-2 midi_public_port_driver.sv、已封存r7a_public_observer.sv和tb_r7a_public_capture.sv；路径基点仍为解包inputs。组合为74源、9 ROM、76个字面module，无字面重复名。没有追加整份DDS，保留M2派生leaf及既有唯一ROM定义；原compile.f、原DDS和M1源不改。

`C5_SELECTED_71_PLUS_R7A_3_STATIC.zip`提供输入本体和新清单，`BINDING.json`给每源/ROM及A追加源SHA，`RECEIPT.json`给静态输出SHA与计数。原A封存ZIP逐字节不变。静态装配命令是Python标准库ZIP读取/字节与SHA比较/写出新候选，exit0、0.6649002秒；没有调用源audit、assembler、自检、编译器或仿真器。

仅L0静态绑定；字面模块计数不是编译/elaboration/行为等价。时钟/DVI stub和旧PLL header仍仅仿真候选。M2须继续冻结实际6个窗口参数、工具/argv/cwd/预算和明确首次HDL准入。HDL/EDA/设备轮次0，A新增软件组0，board_release_allowed=false。
