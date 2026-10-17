# R8-20 电平裕量离线核算

状态 PREPARED_NOT_RUN；九个新软件用例归总控 H 组合组。代码入口为同名 software 目录 `m3r08_20.py --request REQUEST.json --output NEW_OUTPUT_DIR`，本窗口不启动。格式见 INPUT_SCHEMA.json。

每个电压值携带单位 V、evidence_id、页号、含该数值的原句，并绑定原文件大小/SHA。工具只机械检查链接和原句数字，不验证引用原句确为对应条件下的原文。实际负载、温度、供电条件须由责任方核对。REAL_CANDIDATE 恒待人工签收。

高电平裕量=VOHmin−VIHmin，低电平裕量=VILmax−VOLmax，绝对输入裕量=输入绝对最大值−信号峰值；另核实测 VCCIO 上下界相对允许范围的裕量。用 Decimal 计算。任一依据、Bank或共地未知则不计算；已知负裕量、错方向、错Bank、无共地、已声明不耐5V的FPGA输入直接接5V均拒收。有电平转换器时须另补转换后条件。

合成案例中的数字仅为算术夹具，不是 FPGA、MIDI、PT8211 或功放规格。`REAL_INPUT_GAPS.json` 记录实物与官方本地原件缺口；未到件不猜引脚/Bank/电压。输出 io_voltage_budget.json 的 safe_to_wire 恒为 null，不能据合成 ACCEPT 改接线。未执行测量、工具、综合、时序或上板验证。
