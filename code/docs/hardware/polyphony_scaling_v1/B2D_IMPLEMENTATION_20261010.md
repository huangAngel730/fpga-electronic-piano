# T061 B2d：同一混合候选 N16 参数检查点

依据 D043/D044，仅 B 五路径及全新 output。N16 不是第二套声音架构。
保留 develop 33c8b70 的全部五份 b2c RTL 和 tb_b2c_event_audio，逐份 Git LF SHA 核验；
原 B1/B2a 算法仍固定 1c73e8d；冻结 L 的 56 输入/7 ROM 固定 6f3e813。
不改这些原件、ROM、旧封存/失败证据、共享状态或正式工程。实际结果另见 DELIVERY。
N16后继新增 b2d_control_snapshot、b2d_event_audio 和 tb_b2d_event_audio；
不是第二架构：wrapper只改模块名/控制器实例名，后端/分配器/CC64/银行/声音数学不变。

首轮 m3_t061_b2d_dev_20261010_01 的原N8参数实例RTL退出0，checker拒收
B1_FULL_TAG_CONTEXT_CONTROL_PEDAL，精确失败源码/日志另封存，绝不回填PASS。
4030328沿的空槽1与活跃槽15同为source3/channel3：B1按身份共享表回送真实控制，
旧参考却按空槽默认值检查，首次暴露了槽默认/身份共享的合同冲突。
源码进一步确认：若同身份较高槽先退休，其默认控制会在后装载时覆盖较低活跃槽。
最小修复为N16控制快照始终读取该source/channel的真实控制，空槽只由occupied屏蔽声音，
不允许空槽默认值写坏身份共享表；时钟日历、身份位宽和声音算法完全不变。
新长例定向让槽11 note75先释放、槽3 note72继续发声（都为f/f），验证这一路径。
新增恢复旧occupied掩码的可编译RTL行为反例，不用篡改数据或跳过字段换取通过。
第二轮_02四个正常配置均实际编译/仿真/复算通过，但将旧掩码放回普通短演奏夹具时
未触及真实退休，错误反例仍被接收，故总收据保留FAIL，不把它写成最终验收。
最终_03将该反例移入真实B1银行的公开接口定向TB：高槽空闲仍须保护低槽活跃控制，
正例三种占用/四次读回通过，恢复旧掩码必须sim退出1并报ACTIVE_IDENTITY_CONTROL_CLOBBER。
最终runner修正_02沿用旧描述的scope/new_candidate_HDL标签，不回填旧收据。
_03可SHA核验复用_02已完成的真实RTL步骤，重新独立复算并执行完整新正负验收；
每份复用均交原compile/sim/replay命令/退出码/日志/产物及原FAIL收据。
它不是新RTL仿真或mock；复用前全部RTL/TB/数学输入仍须与原编译身份一致。

## 实现及合同

N=16、SW=4、tag76bit={request32,source4,channel4,generation32,slot4}；
context74bit 与原 N8 完全相同。16 个持续 ADSR/DDS/Pitch/LFO、真实波表读取、
增益与混音、全16槽 B1双银行提交/读回沿用原模块，无 fixture ROM 或 XOR 声音替代。
clk 单域40MHz仿真；rst_n 异步断言、由调用方同步释放。无新 CDC/引脚。
取消、身份作废只丢未发布 token，不回滚持续声音状态，不丢已接受事件的 on/off。

独立参考模型的 N 白名单扩至16，公共 replay 新增显式可选尺寸/响应参数；
原 b2c_check 默认仍仅接受 N4/8、R1/3/64及旧空槽合同，N16由新 b2d_check入口
显式选择按身份的控制快照合同。新长例仅多一个指定Note Off，严格END计数同步核对。
模型算法不变：仅 R/I/J/X、冻结 ROM 推导路由/退休/控制/数学/首次结果，
不读 U/G/C/L/W/F/P 输出反填期望。原 N8 短例从旧封存只读取出复算，
逐项比较旧报告全部字段；不重跑旧 N8 长程 RTL。

## 源码日历与时限

J 为接受采样；W 为 router 静止且无 on/off 的首沿；Q=W+8。
G(i)=Q+3N+5+3i；C=Q+6N+3；A=C+8；L(i)=C+15+R+(3+R)i；
首次可见 F=C+16+N(R+3)；计算年龄 F-J-1，>=833 才报 late。
F 与后续 P 握手不同，输出背压不能推迟首次 valid 或改变 PCM/身份/late。
公式由源码状态日历推导；router 前置派发/退休会另加等待，不能从 capture 拟合放行范围。
静止 N16 的 R1/R3/R32/R64 年龄分别187/219/683/1195拍。
R1长例覆盖完整ADSR/真实退休；R3/R32短例检查慢ROM；R64是故意超时限的功能反例。
R64 正确返回数学结果和 late=1 仍不满足48kHz单帧deadline，不计作可接入配置。
128拍 drain fence限原界定工作域，不推广整机无条件 ABA 或外部事件服务上界。

## 验证与复现

同一旧 TB 的N16后继（仅新增同身份高槽释放事件）覆盖16槽占用/非零声音、256身份、CC64、窃取/重触发、
真实 release→Idle 退休、取消非回滚/身份作废、复位恢复、背压及完整银行读回。
三项真实可编译RTL行为反例（忽略generation / 增益置零 / 恢复空槽控制掩码）须指定拒收。
12项完整 capture 反例包括 A/F 双向移沿、槽15 L双向移沿、槽15 generation、
高位占用、路由source、PCM/银行及故意清除late；保留END计数和完整排序日志。

仓库根目录、已有工具、新目录运行：

```powershell
& E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe -B -X utf8 code/scripts/run_m3_polyphony_scaling_acceptance.py --stage b2d --output code/output/m3_t061_b2d_reproduce_NEW
```

总1800秒、单步900秒；原命令、工具版本、源码/配置/日志SHA、退出码由收据记录。
有原轮完整证据时可加 `--reuse-b2d-run code/output/m3_t061_b2d_dev_20261010_02/receipt.json`；
只有完整指定正例步骤compile/sim/replay均退出0、全部日志SHA一致且数学/RTL源未变才可复用。
原流程总体FAIL不代表所选正常步骤失败，仍保留原总体错误并由最终流程补齐缺失反例。
原Icarus敏感集constant-select提示保留，不据此推断厂商综合结果。
不使用候选综合额度，不运行Gowin、PnR、STA、设备/串口/安装/接线/烧录。
功能L2/数学L3与仿真时钟合同不等物理40MHz收敛、生产16音或完整演奏通过。
N32整链、生产接入/档位/资源/整机STA由后续阶段与M2决定，完整T060/T061仍未关闭。
T060已签冻结capture阶段不重跑；其原未覆盖项保留。RAM另由主对话4处理。
共享状态和任务看板更新提议：登记N16独立检查点及R64未达时限，正式编号由M2取得。
