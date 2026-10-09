# 138K曲谱接收独立集成候选

基于T058 reset_hold_v3离线L5精确副本，61inputs/52entries，只新top2UARTport、T057原接收源及CST/SDC准确追加，原音频/波形/ROM/PLL/14旧pin保持。该目录仅overlay/source身份；实际build必须新路径，旧结果不覆盖。

工程候选RX R18/Bank4/J9-5、TX T18/Bank4/J9-6，原R17 MIDI和U15 STAT保留。均资料声明3.3V/与SDRAM1复用，未接线或实物电压证明。输入只有原UART首级rx_meta/D被例外，二级rx_sync setup/hold专表完整，TX5ns/0输出约束。新top不接自动播放、事件注入或音频握手，公开rd_req=0；READ由原UART协议返回。

准备：`python -B -X utf8 code/scripts/prepare_138k_score_receive_integration.py --output code/build/138k_score_receive/<NEW>`，同入口--check核精确61inputs/52entries。
仿真：`run_138k_score_receive_integration_sim.py --project <prepared> --output code/output/<NEW>`，名义PLL/DVIstub短整机13case和12串行响应，2真实MIDI音/逐拍音频STAT和视频wave旧参考等价；不是实体UART/TMDS/全512证明。另两限定仿真negative audio_isolation/response_command编译运行后指定断言/checker拒收。

一次构建必须正例+两行为反例+静态预检receipt合格、源SHA不变，`run_138k_score_receive_integration_once.py`要求全新build/runs目录、<=1800秒/noautotry/no program。检查器继承旧final波形门禁并增加真实UART二级与2pin，原23BSRAM/89SSRAM+score唯一层级按实际加总，新branch不加DSP。实际score memory当前8192byte多路读是否有效推断/时序收敛未知，不预填成功。

不改原M3候选source/协议/ROM/生产接口，不安装APK/Flash/烧录或接线。工具失败/时序负值如实保留，不能沿用T058v3STA放行本工程。详见code/docs/M2_曲谱接收独立集成_实施范围_2026-10-09.md。
