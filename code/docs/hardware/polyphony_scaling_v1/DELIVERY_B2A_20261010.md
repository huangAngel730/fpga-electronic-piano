# T061 B2a 真实声音后端阶段交付（2026-10-10）

结论：`B2A_REAL_MATH_BACKEND_PASS_T061_PARTIAL`，`task_complete=false`。
实际等级仅独立候选编译/仿真与 Python 整数逐样本复算 L2/L3，**不是完整 B2/T061 收口**。
前阶段 develop `9f02adc`；最终推送身份另见转发包 `GIT_DELIVERY.json`，不预填提交号。

## 实际验证

合格原收据：`code/output/m3_t061_b2a_final_20261010_01/receipt.json`。
总耗时354.188秒，退出0；全部命令在1800秒总/900秒单步上限内，无超时。
末尾仓库九门禁全部PASS（132.703秒）。发布前对最终暂存树再跑一次九门禁，
其真实命令/退出码/耗时/输入SHA及远端身份放转发包 `publish_gate/` / `remote_verification/`。

| 同一候选配置 | 完整结果 O | 声部记录 L（含后续取消的部分工作） | 实测后端周期 | 超833结果 |
|---|---:|---:|---:|---:|
| N4，响应1，长程 | 10,230 | 40,925 | 29 | 0 |
| N4，响应3，短程 | 106 | 428 | 37 | 0 |
| N8，响应1，短程 | 106 | 857 | 45 | 0 |
| N16，响应1，短程 | 106 | 1,713 | 77 | 0 |
| N32，响应1，短程 | 106 | 3,425 | 141 | 0 |
| N32，响应32，慢后端 | 18 | 576 | 1,133 | 18 |

共10,672个完整结果、47,924条公开声部记录。周期只从本后端接受请求到生成结果，
不是 MIDI/CC64/反压在内的整机服务时限或 STA。响应32是适配器延迟，不是RAM物理延迟。
慢例仍完整处理32槽，不能跳过声部换取预算通过。

N4长程独立核相位/FCW/波表/envelope/gain/左右PCM/身份/完成mask/clip/超期；
覆盖ADSR五状态、四档亮度窗、4次亮度到期/4次pending换表/4次LFO回绕，
17,865条负数非整除gain。普通连续请求10,225次精确833拍间隔。
四次取消包含推进前/后、部分渲染和输出反压；整域复位与请求/代次回绕保留原记录。
N4同时通过冻结DDS/Pitch/gain公开输出对照；ADSR/Pitch是只读复用，不冒称新算法实现。

N32短例实际出现6次负饱和；正饱和的RTL实际路径**本轮未命中**，仅独立混音单测覆盖
正/负边界。高N短例不等于各档都跑完长Release；这两项列为后续定向覆盖缺口。
没有声称本阶段覆盖所有事件并发、临界第833拍、所有cancel同沿排列。

两份新RTL行为反例均编译退出0、仿真退出1：

- gain向零取整变异：`CHECK_GAIN_FROZEN`，不是编译失败或超时。
- 漏末槽变异：`CHECK_ALL_VOICES`，不是少量声部被静默接受。

九份完整capture仅改一项语义，实际CLI全部退出1并核定原因：phase/table/FCW/wave/
envelope/gain PCM/立体声/身份/END计数。六项新checker单测、原40项B0单测通过。
原stdout的Icarus14最终 `$finish` 工具行保留；只允许真实END后末行的精确工具格式，
不任意跳过未知行或放宽END/结果数检查。

## 身份、工具、旧失败与封存

源码/配置包括实际候选RTL/TB/Python及runner；收据对运行前后逐个SHA核对，
冻结L56输入/7ROM按原manifest和Git基线 `6f3e813` 核对；原T060/B0/B1封存、八共享文件不变。
只改D043/D044 B五路径；共享状态/看板按任务禁区留M2统一登记。
只读参考模型未改，expected来自输入事件/接受快照与ROM，不将观测数值喂回expected链。

实际工具Python3.11.2、Icarus Verilog/VVP 14，路径/二进制SHA及完整原版本输出在收据内。
候选 `.vvp`、原stdout/stderr、退出码、每条命令、elapsed、全部capture及checker报告封存。
不存在Gowin物理产物；一次新B独立综合额度未使用。

开发失败 `code/output/m3_t061_b2a_dev_20261010_01` 原样保留并随包：
原checker未识别Icarus末行，退出1；开发过程中源码有修改，故不是合格最终证据。
修正后新目录从头运行，另纠正普通请求间隔834→833。
旧目录额外诊断 `replay_repaired_new_NOT_FINAL.json` 不是最终验收、不得替代原失败收据；
旧capture间隔834不用于本轮833结论。旧文件未回填PASS；旧源码只保留原收据SHA及编译像，
没有声称恢复其全部原始源码字节。

`B2A_20261010/evidence.zip.b64` + manifest + seal_receipt封存本阶段，验证器核ZIP CRC、
成员SHA、合格命令退出/超时、前后源不变，并重新执行六配置独立数学解析。
新交付资料和打包脚本另由最终暂存树门禁/提交树绑定，不倒填合格运行的源码清单。

## 复现与下一阶段

仓库根目录、已有工具环境、不安装依赖：

```powershell
& E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe -B -X utf8 code/scripts/run_m3_polyphony_scaling_acceptance.py --stage b2a --output code/output/m3_t061_b2a_reproduce_NEW --repo-gates
& E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe -B -X utf8 code/docs/hardware/polyphony_scaling_v1/seal_b2a.py --package code/docs/hardware/polyphony_scaling_v1/B2A_20261010 --verify
```

下一独立阶段接MIDI分配/CC64 256身份扫描/Release-retire ACK/source-channel控制存储，
明确B1 token可丢弃与真实DSP已推进不可回滚的边界，再核全链N4等价和8/16/32。
当前混合后端不是原B0全共享635bit context的实现，不能倒填旧预算；正式路线留M2决定。
无正式工程/顶层/公共包/CST/ROM算法修改；无安装、flash、串口、接线或实物操作。
T060既有收口事项与完整T059/T061不因本包自动关闭。
