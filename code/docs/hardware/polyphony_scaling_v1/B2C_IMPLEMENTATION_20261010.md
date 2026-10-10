# T061 B2c：同一混合候选 N8 事件到 PCM

仅 D043/D044 B 五路径内独立候选。原 B1/B2a/B2b、冻结 L/7 ROM、旧封存不改。
本轮新增 `b2c_*`：将分配器、CC64、控制快照和 wrapper 的槽数参数化；
仍复用原 B1 双银行和 B2a 真声音后端，不另做第二套声音算法。
本文件是实现合同，实际结果见新运行收据和 DELIVERY，不能以合同冒验证通过。

## 接口、状态及宽度

统一事件64bit、source4/channel4/generation32、256身份的bend12/mod12/range5及CC64均保留。
支持并验证 N=4/8，SW=log2(N)，tag={request32,source4,channel4,generation32,slotSW}。
N8 tag75bit，context仍74bit={PCM24,note8,velocity10,baseFCW32}；不得混用tag/context宽度。
槽位LRU秩0..N-1，优先同身份重触发→空槽→最旧槽；延音及退休扫描包含全部N槽，
retire_generation仍32bit；不截断身份，不把全局pedal替代256身份状态。
状态来源为冻结voice_allocator_4、polyphonic_event_router、sustain_controller和
performance_control_snapshot的明确扩展副本，独立模块名，不改原源码/原include。
分配器采用18+SW bit显式packed字段，语义与原结构体字段一一对应。

每槽持续ADSR/Pitch、DDS/亮度/LFO是持久状态，cancel只丢未发布token、不回滚声音推进。
所有N槽同沿推进，每帧N个真实ROM/增益结果完整回写且B1原子提交后才公开PCM。
混音复用signed32累加及最终signed24饱和，原gain的>>>15负无穷取整不变。
前端cancel仅在后端非empty时转发到backend，保留已接受事件同沿on/off不会丢失的修复。
clk单域40MHz仿真；rst_n异步拉低，释放由调用方同步。无新CDC/引脚/板级接口。

## 按源码扩展的时钟合同

采样J后首个router静止且无on/off的沿W，Q=W+8接受控制快照。
控制器串行读取N槽，Q+N产生snapshot；wrapper Q+N+1读取。
随后2N沿装载control/config，B1首个G=Q+3N+5，G(i)=Q+3N+5+3i。
后端C=Q+6N+3；A=C+8；L(i)=C+15+R+(3+R)i。
首次结果F=C+16+N(R+3)，独立检查首次valid和之后P握手；P可背压而不改变F。
计算年龄为F-J-1，>=833报late，不把ready等待当计算延迟。
这些式子由状态机读/装载/推进/ROM/提交逐沿推导，不是用capture输出拟合周期范围。
N4应保持已签B2b短例原语义trace；N8静止R1/R3/R64的计算年龄分别107/123/611拍。
router在采样时仍有派发/退休会增加前置等待；完整外部事件服务上界未承诺。
128拍drain fence只针对本已界定backend工作域，不能直接推广整机无条件ABA/排空。

## 独立验证及观测

`b2c_router_model.py`在M3新范围扩展已签Router整数参考；原四声部model只读保留。
`b2c_check.py`仅R/I/J/X和冻结ROM作为输入，不用U/G/C/L/W/F/P反填期望。
按全部槽状态独立推导分配/CC64/退休/控制、FCW/phase/table/envelope/gain/PCM和时点。
TB观测route_tuple改用完整119N bit（旧TB375:0会截高位）；不是修改设计逻辑。
N4比较所有非U行完全相同，旧U须完整包含，新补的U亦须独立模型通过。
测试包含全256控制身份、满N占用、各槽真实非零声音、重触发/窃取/不匹配off、
source/channel隔离、延音/释放到真实Idle退休、取消前后推进、身份失效、背压、
全N银行读回、工作中复位/恢复。长例含完整attack/decay/sustain/release。
至少两个可编译行为反例：忽略generation由真实res端口注入指定拒收；
gain向零取整须仿真完整END退出0，再由数学checker指定拒收，不以编译失败当通过。
时间/身份/快照/提交/bank的新capture反例保持完整END且须指定错误拒收。

## 边界和复现

本轮无候选综合、Gowin、PnR、物理STA或设备操作；不宣称生产8音、32音或完整T061关闭。
N16/N32后端/协议旧子项不等高N事件整链，尚未本轮验证。冻结L整个top逐时钟等价未证。
所有结果限独立统一事件输入，未含实际UART/MIDI解析、I2S/硬件音频/整机deadline。
原RTL数学的正饱和路径与长程多样演奏覆盖限制继续保留。
共享状态/取号由M2统一登记。RAM新方案已另交主对话4，与本候选不混提交或资源结论。

仓库根目录、已有工具、输出必须全新：

```powershell
& E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe -B -X utf8 code/scripts/run_m3_polyphony_scaling_acceptance.py --stage b2c --output code/output/m3_t061_b2c_reproduce_NEW --repo-gates
```

总1800秒/单步900秒，原命令/cwd/工具版本/源及产物SHA/stdout/stderr/exit绑定收据。
编译器constant-select sensitivity提示是现有Icarus限制：扩大always_comb敏感集；
不得把提示隐去，也不据此宣称厂商综合已通过。
