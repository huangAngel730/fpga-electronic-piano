# T061 B2g：真实 N32 声音后端正负饱和补覆盖

岗位 M3；依据 D043/D044 的同一独立混合候选任务，补 B2a 交付明确保留的
“正饱和 RTL 路径未命中”缺口。不新建另一套声音算法，不代 M2 决定正式档位。
仅写 B 软件、统一 runner、B 文档及 fresh output；共享表由 M2 统一登记。

## 精确源及激励

声音 backend、B1 scheduler/statebank 按 1c73e8d LF 字节绑定；原 B2a TB、
b2_check.py/b2_clock.py 按 b814096 绑定，冻结 L 的 56 输入绑定 6f3e813。
原 N8/N16 RTL/TB、全部旧封存及八处共享文件前后 SHA 不变。

正常运行原 `b2_audio_backend.sv`，不是生成的功能替代物。测试脚本从原
`tb_b2_audio.sv` 仅精确替换两处初始输入，要求每处原文本恰好出现一次：

1. 初始全槽 velocity=1023，原 f20 的 slot0 velocity=256 重触发保持。
2. 高 N 初始 FCW 39370534→78741068（约 440→880 Hz）。

冻结 piano table0 正峰在 index17；440Hz 正峰落在包络攻击早期，单改满力度仍
不足以在原短程内正削波。880Hz 在相同短程内多走一个周期，后续正峰落在
较高包络阶段。频率只是合法输入，不参与选择期望输出、周期窗口或 PASS 条件。
原 833 拍采样间隔、真实 ROM、连续 ADSR/PitchMod、取消、复位、输入扰动、
结果身份和完成掩码不改。不 force DUT 内部状态、不换合成波表。
生成 TB 的实际原字节、两替换记录及 SHA 均保存在 `generated_test/`。

## 独立重算与拒收

`b2g_check.py` 先调用未改的 B2a 严格模型：从 R/E/C/A 输入、冻结 ROM、
独立整数 DDS/ADSR/PitchMod 得出逐槽相位/波表/包络/FCW/增益/PCM和宽位累加、
立体声饱和；逐项验证后才统计输出分类及已验证槽 PCM 的累加范围。
观察输出不反填期望。要求正削波、负削波、未削波非零、静音及全部 32 槽真实贡献。
严格源日历检查 A/每个 L/O；O 仍只适用原 B2a“停顿后取消、不恢复握手”夹具，
不能宣称新增通用 first-valid/任意握手 checker。

两项可编译行为反例只在新 output 的 backend 测试副本改变一次返回常数：
正上限 0x7fffff→0x7ffffe、负下限 0x800000→0x800001。原 backend 不写入。
要求 compile0/sim0/replay1 且诊断精确为 MATH_STEREO_SATURATION。
此外完整 capture 的 12 项反例只改目标字段，保持 END 计数不变：两方向值/
两 clip 标志、A±1、slot31 L±1、O±1、完成 bit31、最高槽 generation。

4 项新单测包含含等号的正负界限、相消不可中途饱和、32槽宽位和、严格配置/
精确替换及源日历。实际 lane PCM 为256倍数，正端精确累加8388607不可由本
增益链直接构造；“恰等正界不削波”只签软件单测，不冒称真实 RTL 已覆盖该点。

## 复现

在仓库根目录使用现有 IDF Python 3.11.2：

```powershell
& 'E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe' -B -X utf8 code/scripts/run_m3_polyphony_scaling_acceptance.py --stage b2g --output code/output/m3_t061_b2g_reproduce_fresh
```

现有 Icarus/VVP 路径来自 runner 参数，工具版本/二进制 SHA、命令、退出码、
原 stdout/stderr 与所有源 SHA 写入 receipt。每步≤900秒，总≤1800秒；
本轮不使用 capture 复用，不运行综合/Gowin/STA或任何设备命令。

仅 L2 仿真/限定数学 L3：不新增 MIDI路由/B1整链结论、不覆盖 N32 长程
ADSR退休/持续演奏、全局调度/真实DSP排空界限、资源/物理时序/生产32音。
完整 T060/T061 保持 PARTIAL，正式架构/准入/接入/整机STA由 M2 决定。
