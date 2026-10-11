# T061 B2h：同一复音候选 N32 完整长程生命周期

M3 按 D043/D044 在原 B 五路径内继续，补 B2e 仅短程留下的 N32 真实
ADSR/释放/逐槽回收缺口。不是新建第二套引擎，也不替 M2 决定生产档位。
原功能 RTL、TB、ROM、算法、旧 capture 和封存全部保留；八处共享文件不写入，
本阶段状态/验证等级交 M2 统一登记。旧 RAM 布线与本任务无关，不重启。

## 精确源码与运行条件

- 原 `b2d_event_audio.sv`、`b2d_control_snapshot.sv` 和 `tb_b2d_event_audio.sv`
  按 0ca4515 LF 字节绑定，仅编译参数 N=32、RESPONSE=1、LONG=1。
- B1/真实 B2a 声音算子按 1c73e8d、原日历与数学输入按既有冻结 SHA 绑定。
  b2c_check/router、b2d_run、b2e_check/tests 按 c3576cb 固定；不是重写期望。
- 40 MHz 仿真时钟、原 48 kHz 采样契约和普通最短帧 833 拍保持；每帧所有
  32 槽独立 DDS/连续 ADSR/PitchMod/真实 ROM/增益/混音完整求值并回写。
  不跳槽、不加速包络、不 force 内部状态、不以软件预算代实际 RTL。
- 原 TB 保留 256 个 source/channel 身份、抢占/重触发、CC64、准确 off、
  generation、双银行原子提交、反压、取消/非回滚及忙/持有结果时复位。
  原长程已有 5400+4900 帧段及高槽 NoteOff；本轮不改激励来配合 checker。
- slot3/11/27 共享 f/f 身份；检查三者同活跃，以及 slot11 先真实退出后
  slot3/27 仍活跃。全部 32 槽必须真实回收，slot31 必须经历全部五种 ADSR 状态。

原 N16 同一长程实际 VVP 曾用 761.8 秒，N32 更慢。用户在本轮明确允许
**单步最多 1800 秒、全流程最多 2700 秒**，仅扩大此次 B2h 仿真/复算时限。
runner 默认仍 900/1800；非 B2h 不接受扩展参数。不新增综合/Gowin/STA/设备许可。
实际源码、Python/Icarus/VVP 二进制 SHA、命令、退出码和时间由原 receipt 记录。

## 独立验收与反例

`b2h_check.py` 先严格要求 `B2C 32 1 1`，调用未改的独立事件路由/声音模型。
只从 R/I/J/X 与冻结 ROM 推导控制/路由、全部声音数学、源码日历 A/逐 L/首次 F，
不使用观察 U/C/G/L/F/P 输出反填期望。首次 F 与 P 握手分开；取消保留已发生
DSP/路由副作用，身份失效不得发布旧结果。完整 schema/顺序/尾计数保持。

数学/语义逐项一致后，才统计真实逐槽回收、slot31 ADSR、共享身份和原833节拍；
复位清域不冒充真实退休，要求所有32槽回收且总数与独立路由模型一致。
本夹具至少10000个精确833间隔、deadline_misses=0，缺覆盖一律拒收。

10 项完整长 capture 反例保持完整 END 计数：A±1、首次F±1、slot31 L±1、
高槽 generation、slot31→15 tag 别名、occupied bit31、P PCM 篡改。
要求指定语义诊断，不靠坏 schema 或残缺尾部拒收。4 新单测覆盖严格配置、
高槽独立 generation/77位 tag 和精确源码日历，另保留原40项软件自检。

两份原 RTL 可编译行为变异采用 N32 原短程，错误首次出现即可证明，不重复跑长包络：
忽略 generation 要 compile0/sim1 且指定 B2B_STALE_GENERATION_ACCEPTED、非 WATCHDOG；
gain强制0要 compile0/sim0/replay1 且指定 MATH_GAIN_PCM。原功能文件不改。

## 复现与无损封存

仓库根目录，使用本机已有工具：

```powershell
& 'E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe' -B -X utf8 code/scripts/run_m3_polyphony_scaling_acceptance.py --stage b2h --step-limit 1800 --workflow-limit 2700 --output code/output/m3_t061_b2h_reproduce_fresh
```

`--b2h-preflight-only` 仅编译和单测，明确 NOT_LONG_PASS，不冒充长程通过。
首次预检因测试 import 顺序失败、第二次预检通过，原收据及日志随封存保留，
不回填旧结果；真实完整长程必须另有新 run 的 compile/simulate/replay 成功。

封存器 `deliver_b2h.py` 的 `seal/verify/restore/forward` 不调用仿真、EDA或设备。
正常原 capture/stdout/stderr 完整保存；10份重复长反例保存为**单一字节区间替换**，
包含原 capture SHA、显式CRLF→LF变换和变换后SHA、prefix/remove/replacement、
原完整反例字节数及 SHA；正常原stdout本身不转换或覆盖。
封存时逐字节比较还原结果与实际测试文件；验证时按 receipt 和反例报告分别核 SHA，
不是只保存摘要、删尾或用重新生成日志替换实际正常日志。
8还原自检和5篡改拒收保持。下载仓库后可只验证或在全新 output 还原完整原件：

```powershell
& 'E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe' -B -X utf8 code/docs/hardware/polyphony_scaling_v1/deliver_b2h.py verify
& 'E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe' -B -X utf8 code/docs/hardware/polyphony_scaling_v1/deliver_b2h.py restore --output code/output/m3_t061_b2h_restore_fresh
```

归档清单分 physical members 与 lossless_derived_members，两者全部核验后才签封存成功。
发布另执行精确暂存树九门禁、普通 develop 提交推送及 GitHub 远端 SHA 实核；
形成时未提交/未上传的历史说明保留原状，实际发布身份见 GIT_DELIVERY.json。

## 结论边界

只申请本 N32 指定夹具完整生命周期的 L2/限定数学L3，不等于通用长时间演奏、
全部未来事件交错、完整冻结L逐拍等价、全局DSP排空/ABA无条件消除、I2S/实体音频，
也不是综合、资源、PnR或物理STA。B2g饱和结果与本长程分列，不拼为一份工程L5。
正式N32/接入档位/资源/新整机STA由M2决定；完整T060/T061仍PARTIAL，无设备动作。
