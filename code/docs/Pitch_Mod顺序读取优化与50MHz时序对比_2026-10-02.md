# Pitch／Mod顺序读取优化、采样调度和50MHz时序对比

2026-10-02，M2独立候选，基线251cd8d，用户要求按“资源优化→调度验证→Gowin时序对比”依次完成。没有新增角色或代做M1算法/M3输入，既有performance_control_state作为原参考保留，正式top/GPRJ/router/PCM/ADSR/公共包/CST/SDC及实际可播放码流未修改。

## 一、资源结构与时序合同

新增rtl/board/performance_control_snapshot.sv。保留16source×16channel全部256身份、Pitch12补码、Mod12无符号、range5（0..24，默认2）和完整四槽source/channel/generation标签。原版三张表和四路组合查询改为一张29位控制字RAM，统一单读口/单写口；空闲读口用于事件partial-field read-modify-write，采样期间逐槽读取，避免四路读口复制/大多路选择器。

RAM数据本身不复位，256位initialized有效表异步清除，未初始化身份返回{range2,mod0,pitch0}；首次partial更新先补其他字段默认值。通过复位时逻辑有效位隔离旧RAM，不改变复位默认语义，不依赖上电不确定RAM值；删除initialized保护的实际RTL突变测试会被参考拒收。

本模块不是原组合查询接口的零延迟替换，端口不同只属于新增独立M2局部候选。event_valid/event_ready用于成功控制接收；request_valid/request_ready接受一组4槽请求；snapshot_valid/snapshot_ready整组发布/消费。保持输入直到对应ready握手，不把未经ready接受的event_valid更新成演奏状态。

接受请求的上升沿E冻结sample_id、4槽占用/source/channel/generation。E+1..E+4逐槽读，E+4发布完整结果；这4拍event_ready=0，不接受控制更新，确保各槽对应同一参数时间点。若事件与request同沿都握手，先写控制字、后续槽读能看到新值，与原版write-through快照一致。已在下游呈现的快照背压期间保持所有字段不变，但可以继续接收控制事件到状态表；只有旧结果握手或无结果时才ready接受新请求。

NoteOff/Release/抢占不清通道控制；标签总线后续变化不影响正在读的一组request。未占槽返回0/0/2。复位取消正在读/背压结果、有效位清零；非法range>24拒绝，未知控制/CC64/Note/PANIC不改轮状态，同原局部合同。最终接入仍须M1/M3确认panic控制状态策略，候选不暗改公共接口。

固定4clk准备延迟在50MHz为80ns，占48kHz最短1041clk周期0.384%；并不等于完整FCW/音频/模拟端到端延迟。不能把snapshot_valid每系统拍当LFO采样使能；M2最终只根据request代次推进算法，结果依同代次提交。

## 二、真实功能和采样调度自检

运行：

```powershell
python -X utf8 code/scripts/run_serial_control_snapshot.py
python -X utf8 code/scripts/run_control_snapshot_schedule.py
```

第一条std-library交易参考和原performance_control_state并行RTL参考共同对照。固定随机种子，27525拍、131803检查、2464请求/2459消费、15511事件握手PASS；差额来自明确复位取消的在途/背压请求，不称丢帧。覆盖全部256source/channel、Pitch4096补码位型、Mod4096数值、range4096合法/非法，重复身份4槽、同沿更新capture、事件/请求/结果独立背压、稳态旧快照不被控制更新污染、输入标签在4拍间变更不撕裂、代次回绕、复位后旧RAM隔离与首次partial更新、持续真实producer随机交错。每次已接受request结果完整位等同原快照，除显式4拍协议延迟。

定向负例：仅在另一向量副本改一个Pitch期望位，明确FATAL拒收；仅在scratch RTL副本删除logical-reset有效保护，编译成功后因旧/未知数据不能等于参考而FATAL拒收，不能把编译失败算行为证据。原源/正常向量不改。

第二条真实M3 parser（e522402）在50MHz输出事件，采样请求按1041/1042系统周期产生，和原表以同一成功握手tap比较。216773检查、203request/203消费、5连续事件/3离散事件PASS；准备延迟始终4clk，模拟算法显式等待后最长13clk消费、event_ready连续低4clk，未错过下一采样请求，parser错误/溢出0。槽source/generation抢占重新绑定和reset恢复默认通过。这里测试parser字节入口，不替代真实31250bit/s串行RX或实际FCW/LFO/PCM/模拟时延；M3输入原有真实UART专项已单独通过。

## 三、50MHz独立公平探针与实际报告

新增tb/board/control_snapshot_timing_probe.sv统一scan观察wrapper，原版和候选仅SERIALIZED参数不同，输入相同、快照readback相同，不观察原版额外live query口，避免不公平扩大原版成本。全部260位任意事件/身份/标签可由扫描输入到达；7tap cyclic XOR只是探针可逆输入转换，精确GF(2)秩260，所有合法身份和payload仍可到达。不是生产输入编码。

两版SDC/CST逐字相同：sys50MHz period20ns、setup uncertainty1ns、hold uncertainty0.5ns，只有外部sys_rst_n→u_reset异步入口false-path；内部无false-path/multicycle/低频过门禁。V22和AA13沿用板事实，只在output独立约束指定，其他scan引脚工具自由放置，未给外部IO timing。因此只比较内部STA/资源，不作为可上板工程或端到端约束证明。

复现：

```powershell
python -X utf8 code/scripts/prepare_control_snapshot_timing.py
python -X utf8 code/scripts/prepare_control_snapshot_timing.py --baseline
# 两目录分别执行run_all.tcl，Gowin gw_sh run all。
python -X utf8 code/scripts/check_control_snapshot_timing.py code/output/control_snapshot_optimization_20261002/serial_validated_probe_PnR
python -X utf8 code/scripts/check_control_snapshot_timing.py code/output/control_snapshot_optimization_20261002/parallel_validated_probe_PnR
```

Gowin Education1.9.11.03，GW5AT-LV60PG484AC1/I0，两版实际syn/PnR/STA报告：

| 指标 | 原四路表 | 顺序读候选 |
| --- | ---: | ---: |
| Logic（含相同wrapper） | 8016 | 2168 |
| Register（含wrapper） | 1897 | 836 |
| 分布式RAM16 | 512 | 128 |
| DSP／BSRAM | 0／0 | 0／0 |
| 实际Fmax MHz | 56.395 | 58.122 |
| Setup最差ns | +2.268 | +2.795 |
| Hold最差ns | −0.200 | +0.002 |
| Setup／Hold端点违例 | 0／255 | 0／0 |
| Recovery／Removal最差ns | +16.056／+0.406 | +15.686／+0.603 |

相同wrapper条件，Logic下降72.954%、Register下降55.930%、RAM16下降75%。原版本组Hold FAIL，最差stimulus_24/Q→stimulus_40/D为包装移位链；不能称两版都L5。候选内部独立L5通过，最差Setup stimulus_59/Q→control_mem/DI，最差Hold stimulus_90/Q→snapshot_id_20/D（+0.002ns），最差Removal有效位clear（+0.603ns），余量/精确端点保留原报告。没有用原probe7851Logic直接混作同wrapper本组百分比，也不拿2168加到12960音画资源算实际整机预算。

checker校验非空路径/端点、真50MHz时钟、不确定度未削弱、四类slack、零latch和device；Gowin会省略0DSP/BSRAM行，额外查综合层级无该资源后才可写0，不把有用资源缺表假装零。篡改Hold端点、Setup端点、hold uncertainty、clock period四个实际报告反例全部非零拒收。

生成FS仅厂商run-all输出，独立scan引脚未验证，绝不交板测/不自动烧录；没有新的电子琴.fs。最终正式模块连接到router/算法bank时仍需整机STA/PnR和实物。

## 四、定位过程和失败边界（原件保留）

- 首次SDC用了工具不支持的不确定度简写，解析TA2000失败；改本机已验证的-from/-to写法，保持1/0.5ns，原失败log/SDC存档。
- direct-copy原观察wrapper版本候选1872Logic、Fmax62.592/Setup+4.024，但355Hold端点/−0.371ns，明确FAIL。显式开启Gowin correct_hold_violation1，cmd.do确认correct_hold1却没有改善，本试验仍失败。
- 更严格set_min_delay1ns（原hold uncertainty不变）试验没有引导路由，2079Hold违例/−1.371ns及Removal−.275ns，拒收，不用于L5结论。手册SUG940-2.0E说明min-delay同时作用Hold/Removal，这条只读定位用，不改生产SDC。
- 第一次probe输入转换文本替换产生自引用，复查发现后未使用该目录任何报告。仅改新tb wrapper；修正原表达式，Yosys check-assert确认无组合环，再用fullrank输入证明保留全部payload，新validated目录实际重跑。
- 修正probe采用两版一致输入转换后，候选Hold通过，原版某些wrapper移位路径仍不通过。该结论依包装条件，不等同候选在任何接线/布局都无Hold风险；保留正式音频原Hold+.001ns等实际现状，不能提前宣称整机新Fmax。

## 五、接入限制与下一步

旧performance_control_state.sv原样保留，M3parser不改；新candidate端口需要独立event/request/result ready。不能直接拿旧accepted tap只读连接它：4拍事件背压必须由正式路由协调到同一共享FIFO，尤其不能让控制分支ready阻断Note/CC64或忽略快照未完成。可以只在需要这组snapshot的阶段暂停控制更新，正常音频帧继续，但具体router/bank最小端口影响由后续合同给出。

新candidate没有4路live组合口，M1算法消费整组快照或顺序lane参数即可；读取ready/valid/sample_id/generation时序须与M1真实FCW/LFO结果接口匹配。当前没有新增弯音/颤音听感、M1算法未代写、无共享top/pkg/CST改动。原可播放V1+CC64/音画诊断和M3实物证据都保持，不新做或中断实物。

本阶段三步独立任务完成：资源结构候选/调度有界验证/真实50MHz STA对比。正式算法集成、生产工程STA、原Hold约束整体恢复、T031真实延迟和新控制音效L6仍未完成，T036/T029整体不关闭。T025/T026补验按用户决定继续暂停。本阶段反馈供用户私发M1/M3，尚未送达。

最终check_repo.ps1九组全PASS（118份Python语法/T007/T019/引脚/引用），git diff --check通过。源/向量/调度日志/同wrapper输入/原始STA与资源报告SHA及所有失败定位试验见evidence/control_snapshot_optimization_20261002.json。生成独立探针.fs不提供板测，不替换正式电子琴.fs。
