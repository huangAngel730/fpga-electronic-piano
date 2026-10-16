# chat9：完整冻结包到件与 R05 正常窗口 PCM 独立重算

2026-10-16，M3／主对话2。Git 基点 57ad4aeb8ef0a1dad3fcfaf68f83aad6d08b0af3。
本轮延续两个 chat8 独占目录，仅新增软件、软件结果和说明；没有修改旧原件或已封存包。

## 当前结果

**M1 完整包已核准，缺包阻断解除。已有真实 capture 的 303 次发布与独立期望完全一致。**
本轮是基于旧真实采集的新软件数学复算，申请限定 L3，不是新 RTL 仿真、M2 已签收、
生产四声部/32声部、整机 STA 或实物音频通过。旧 chat8 缺包说明保留为当时搜索状态。

- M1 第11包：750224字节，SHA256
  `842fa8f75356090440a5e8237acafc209620d114f9e3c0ce2eab5ffdf30862da`。
- 77个清单成员逐字节长度/SHA和ZIP CRC通过；内部完整算法包416469字节，SHA256
  `5c18926ae307301e91ec0e44dcf4a48b2fb57adec71ad46c494b14df59913b06`，CRC通过。
- M1模型/辅助ROM身份逐项核；全部90个实际执行树成员与原运行前后SHA一致，
  包含真实 board、运输、observer 和依赖。M1合同31个相同绑定＋1个已声明include-guard差异
  均按R05实际执行身份验证，不把原候选注释当实际运行版本。
- 冻结函数直接从已核ZIP原字节加载，没有从工作树同名模型导入，没有修改M1数学。
- 实际输入/原capture SHA核准；生成黄金的函数不接收实际PCM/clip/commit列表。
  先从输入、reset/frame/request和源码日历生成全部期望，再逐项比对输出。

## 新适配器的精确范围

只支持该原件的正常请求窗口：单reset寿命、一次启动配置、正力度NoteOn和合法Program选择、
无bend/mod/off/pedal/panic；每个请求前分配流水已结束，窗口内没有frame/配置/复位/事件打断。
不满足前置条件明确拒收，不跳过不支持的请求，不从已提交行反推效果器历史。

以真实请求接受沿 r 为基准，源FSM推导：

| 阶段 | pre-NBA观察/更新沿 |
|---|---|
| WAIT_DISPATCH / SETTLE进入 | r+1 |
| 控制快照请求 | r+9 |
| 控制结果生成 / pitch请求 | r+13 NBA / r+14 |
| pitch结果生成 / bank消费 | r+21 NBA / r+22 |
| lane_tick | r+23 |
| bank SNAPSHOT | r+28 |
| mix寄存 / 效果输入接受 | r+29 / r+30 |
| 效果输出生成 / result_hold接受 | r+33 NBA / r+34 |
| buffer成功提交，组合commit_pulse | r+35 |

注意：r+35不是注册commit的后一拍观察，而是result_hold新增一拍之后的真实buffer握手。
该时点依据 `premixed_frame_adapter`／`pcm_result_hold`，不是根据输出寻找最佳偏移。

事件E接受后E+1分配、E+2锁槽、E+3注册note_on、E+4波形/包络看到note_on。
Program在E+1更新，只影响后续分配；第五音由冻结allocator Oracle推导为抢占槽0，
generation由1到2，相位和ADSR现有level不清零。空槽同样经历lane_tick，FCW=0。

Triangle取tick推进前相位，Piano连续ROM＋三级寄存后在snapshot取推进后相位/表。
ADSR使用冻结逐沿Envelope和quiet_until；Q15负值按算术右移向负无穷取整，再左移8，
四路累加sat24。中性bend/mod下固定LFO相位为0只作数值等价，不宣称完整LFO状态重放。
效果器按每个推导的r+30接受推进，不以成功提交决定是否写历史。
实际配置引用同SHA board常量 enable1/delay1/dry32767/wet16384/feedback0；
载荷没有动态导出，不能把静态常量绑定写成已采到config payload。

## 数学结果与限制

303个期望与原观察的epoch、ID、提交沿、左PCM、右PCM、clip逐项一致。
预测PCM范围 -2024151..2282322；当前clip全0，左右相同。
从输入计算的基频约为69=440.000005、64=329.627562、60=261.625562、
67=391.995437、72=523.251124 Hz；这不是FFT/录音频率测量。

黄金分解中67个请求（ID237..303）四槽各有非零贡献；完整最终PCM与实测一致。
这是独立模型分解＋整和比对，不是额外逐槽采集，不能唯一识别任何可能内部抵消的错误。
旧C串行证据仅覆盖其中至ID301的完整播放；ID302/303被末尾复位截断，不能说全部303已播出。
不重跑旧303期限/302完整串行帧；这些结论按原SHA复用。

本次没有通用取消/HOLD/Release/退休数学覆盖，没有左右不等交换或非零clip错拍覆盖，
没有首次valid动态观察、启动未知段或末尾reset后恢复发声证明；模拟延迟仍未验。
完整T052等其他任务不由本项关闭；board_release_allowed=false。

## 实际软件执行

仓库根命令（输出拒覆盖，勿原样重跑）：

```powershell
& 'C:/Users/songdongkuan/miniconda3/python.exe' -B -X utf8 code/software/m3_r05_functional_integration_20261015/chat8_20261016/run_chat9.py --run-id CHAT9R02
```

- CHAT9R01：首次独立正常重算，退出0，约3.156秒；原源码和日志保留。
- CHAT9R02：增强全执行树身份核、执行前后身份及新增拒收测试后，退出0，约7.172秒。
  两个顶层Python子命令均0；单步90秒、总180秒，timeout=false。
- 10项新增软件测试通过：六份完整303结果的修改副本（左/右1LSB、clip、ID、时刻、
  删除1结果）分别实际运行比较器，均退出1并命中指定诊断；另四项合成输入取消、
  分配重叠、复位打断和未支持事件，均触发预期范围拒收。
- 这六份是**软件坏capture副本**，不是RTL行为反例。四项是内存合成输入拒收。
  不运行M1既有自检，不复跑任何RTL/ModelSim/Gowin，真实工具调用0。
- 实际Python调用累计：R01子命令1；R02顶层子命令2＋测试内比较器6。
  两次外层Python调度另计。只读归档检查命令不冒充验证子命令。

原双流、完整argv/cwd、机器/Python及执行源码SHA、timeout见各轮RECEIPT.json。
R02的SOURCE副本、PLAN、CLOSURE、GOLDEN、OBSERVED_COMMITS和10项结果均保留。
比较器 `--compare-only` 只是软件反例入口，不负责来源验真，不能单用其exit0签收外部材料。

实现窗口自审及自用只读子智能体检查了参考输入依赖、源码日历、位宽/相位/Program、
303项结果和10项正负例记录；当前固定capture范围未发现阻断。没有启用审核员/预审员制度。
增量封存包包含M1原ZIP、执行源/ROM副本、新代码和两轮软件证据；约123MB的旧连续轨迹
不重复装包，以原仓库路径/完整SHA引用，复算时需这些原件。旧封存没有覆盖。

## 给总控／M2

M1第11完整冻结包已到，已完成正常窗口参考桥。使用原真实R05输入与capture、不改模型/RTL，
303次发布左右PCM/ID/时刻/clip独立重算完全一致；10项新增软件拒收检查通过。
缺包问题关闭，当前申请的是该精确日历的限定数学复核，不申请重跑R05或扩大硬件许可。
通用取消/HOLD、内部逐槽动态观察和模拟/物理边界保持；由总控统一Git发布。
给真人M1/M2仍待用户转发，尚未送达。
