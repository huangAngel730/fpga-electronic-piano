# T061 B2e：同一主候选 N32 短程检查点

按 D043/D044 B 五路径和新 output，不新增第二套声音架构，不修改生产或 RAM 工程。
沿用 0ca4515 的 b2d_control_snapshot、b2d_event_audio、tb_b2d_event_audio 原字节，
实际编译参数 N=32、LONG=0，ROM 响应 R=1/8/16/32。B1/B2a 保持 1c73e8d，
原 b2c RTL/TB 保持 33c8b70，冻结 L 56 输入/7 ROM 保持 6f3e813。
runner 对上述原源逐份 Git LF 身份检查，旧封存及共享文件执行前后 SHA 必须相同。
本次不改任何 HDL，仅将独立 Router 参考的合法 N 白名单扩至32；旧入口默认尺寸/响应/合同不变。

## 接口和数学

同一 wrapper 以 N 参数生成32份持续 DDS/ADSR/Pitch/LFO状态，波表、增益、混音和事件语义不变。
SW=5，完整 tag77={request32,source4,channel4,generation32,slot5}；context74 不变。
身份控制沿用 N16 修复，闲槽不覆盖同 source/channel 活跃槽的共享控制。
持续声音状态与可取消 token bank 分离，取消/身份失效不回滚 DSP 状态。
TB 单域40MHz（25ns周期），rst_n 异步断言；无 CDC、物理约束或器件操作。

期望仅由 R/I/J/X 输入、冻结 ROM 和源码日历推导；U/G/C/L/W/F/P/Y均为待比较输出，
不利用实际输出反填路由、声音或时间。每帧32槽完整求值、回写、双银行原子提交及公开读回。
槽31完整标签及占用最高位不能退化成槽15/16位mask。

## 源码日历，不是综合估计或物理 STA

令 W 为 router 静止且无 on/off 的首沿，Q=W+8。
G(i)=Q+3N+5+3i；C=Q+6N+3；A=C+8；L(i)=C+15+R+(3+R)i；
首次可见 F=C+16+N(R+3)，年龄=F-J-1，年龄>=833报late。
F 与输出握手 P 分离；背压不改变首次 valid 的时间，也不改变保持的 PCM/tag/late。
静止 N32 的 R1/8/16/32 年龄分别347/571/827/1339拍。
静止 R16 的827拍不是所有请求的上界，尚须计入原路由派发/释放等待，不能用静止预算放行。
各配置只有实际 capture 的全部首次结果不late，才标本夹具 sample_deadline_qualified。
这不代表完整外部事件服务上界、48k持续演奏准入或40MHz物理可跑。

## 验证与可复现命令

新入口 b2e_check 明确只接受 N32、指定四响应及 LONG=0，不把短程结果签成完整ADSR/回收。
短程覆盖满32槽/逐槽非零、256控制身份、CC64、重触发/窃取、panic释放启动、
取消及非回滚、身份失效、复位、输出背压和全32槽银行读回。
原短例仅32个panic后采样，不能证明完整释放到Idle退休、长期Sustain或高N长程演奏。

5项新单测核槽31/bit31、tag77、源码32槽日历、833首次valid边界、严格N及短例schema。
12项完整capture反例覆盖 A/F双向移沿、L槽31双向移沿、槽31generation、31→15标签混叠、
占用bit31、发布PCM、银行context和故意清除late；保留完整END及计数，指定语义非零拒收。
两个可编译RTL行为反例（忽略generation、增益置零）在 N32 实际运行并指定拒收。
既有40软件单测及预算工具照原入口执行；全部命令/stdout/stderr/退出码/SHA由新收据记录。

```powershell
& E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe -B -X utf8 code/scripts/run_m3_polyphony_scaling_acceptance.py --stage b2e --output code/output/m3_t061_b2e_reproduce_NEW
```

单步<=900秒、总流程<=1800秒、拒覆盖，无自动工具安装或扩大时限。
本阶段不重跑旧 N8/N16 长程，不复用或冒称新的实际仿真，四配置均从本次实际编译产生capture。
不用独立综合额度、不运行Gowin/PnR/STA/串口/安装/下载/接线/烧录。
旧 RAM 不再使用，新 RAM 另由主对话4及 M2 处理，本阶段与 RAM 版本接入无关。

N32完整长程/Release退休、正饱和RTL、冻结L全top逐时钟等价、资源/物理STA及生产采用未验。
完整T060/T061不关闭；M2决定正式架构、档位、整机接入和新STA。
共享表不改，状态/任务/验证登记提议交M2统一处理。
