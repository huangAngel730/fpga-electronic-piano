# T052 下游最小 WAV 证据工具（M3 独立交付）

2026-10-11。用户授权 M3 分担 M1 后续工作；主交接／复核对象是 M2，M1 仅知会。
本工具是成果收缩方案保留的必要离线分析，不是新增完整 GUI、音色算法或生产接入。

## 范围与状态

仅新增 `code/software/t052_audio_evidence_candidate/` 和本文所在独立文档目录。
不改 M1 T052 的 source／参考模型／TB／runner，不修改 RTL、ROM、CST、工程、八处共享文件。
只读复用原 `code/model/analysis.py` 的周期 Hann 窗和指定频率 DFT，另实现 radix-2 FFT；
两份只读依赖均绑定 SHA，不满足时拒收，不安装第三方依赖。

实际验证等级是 L0 静态／文档、L1 Python 加载及软件自检。
合成信号的数值对照属于软件数值测试，不宣称 T052 RTL 的 L2／L3 或硬件 L4–L7。
没有真实 FPGA 导出 WAV 或物理录音，本交付不关闭 T052、T060 或 T061。
M1 v2 的六份外部文件仅作前后 SHA 不变清单，不因本工具运行而视为其仿真通过。
共享任务表／验证编号仍交 M2 统一登记；本文为本阶段状态及复现入口。

## 输入及判定

- 小端 RIFF/WAVE、PCM 编码 1、单／双声道、16／24／32 位有符号整数；拒收 float、
  extensible、压缩格式、重复数据段、截断、尾随字节、字节率／帧对齐错误。
- 文件最多 8 MiB；采样率 8–192 kHz。配置采样率必须与 WAV 完全一致。
- 显式选择 `start_frame` 与 `frames`，后者为 4096–262144 的二次幂。
  所有统计、频谱只代表该段；不足时失败，不自动补零或挑选好看的片段。
- 1–32 个目标频率，间距至少 `max(8 个 FFT bin, 4×频率容差)`。
  这是软件输入容量，不代表对应 N 声部硬件已实现。
- 两声道独立检查，必须都通过；不平均左右声道掩盖反相或右声道静音。
- 统计归一化 DC、RMS／AC RMS、绝对峰值和数字正／负满幅命中。
  数字满幅命中不是一般模拟削波检测；失真在满幅以下也可能存在。
- 去 DC 后加周期 Hann 窗；FFT 寻找目标邻域峰，三点对数插值估频，
  在估计频率处用旧直接 DFT 重算峰值幅度。单边幅度按 `2/sum(window)` 校准。
  dBFS 指正弦峰值幅度，RMS 字段另行标记；零能量使用 JSON null 而非 NaN／Infinity。
- 阈值全部来自配置。示例 48 kHz、四频率 263／431／659／997 Hz 和容差仅供合成自检，
  不覆盖 M1 当前业务参数，真实验收阈值由 M1／M2 决定。

`criteria_met` 仅表示配置的频谱／DC／满幅条件均满足。频谱可能是谐波，
不证明声音来自多个独立振荡器；也不证明逐样本等价、事件生命周期、延迟或 STA。
`provenance.kind` 是调用方标签，即使写 physical_recording 也不认证来源。
`provenance_verified`、`independent_voice_count_proven`、`physical_validation`、
`t052_complete` 始终为 false。不能把合成 WAV 当成 FPGA 录音。

## 使用

在仓库根目录运行，下例 `python` 为可用 Python 3.11；不需要 pip 安装。

```powershell
python -B -X utf8 code/software/t052_audio_evidence_candidate/test_evidence.py
python -B -X utf8 code/software/t052_audio_evidence_candidate/qualify.py run --output code/output/t052_audio_fresh --m1-reference E:/FPGA/GAOYUNFPGA/M3_HELP_M1/T052_repair_v2/T052_repair_v2
python -B -X utf8 code/software/t052_audio_evidence_candidate/evidence.py --wav YOUR_INPUT.wav --config YOUR_CONFIG.json --output code/output/t052_audio_recording_fresh
```

输出目录必须全新，拒绝覆盖。退出 0＝仅配置条件满足且输入未变；
退出 2＝有效 WAV 不满足配置条件；退出 1＝格式／参数／依赖／输入变化／执行错误。
异常执行不写成功收据，已有半成品必须连同 stderr／退出码视作失败，不得单取图表作为通过证据。
单次 CLI 的耗时与段长／目标数相关；自动 qualification 每步 60 秒、总计 300 秒。
最大段长／32 目标的所有组合未作性能上界证明。

有效 WAV 输出：`analysis.json`、`spectrum.svg`、`input_config.json`、`receipt.json`。
收据记录 WAV／配置／工具／依赖 SHA 和产物 SHA。SVG 为自包含代码生成图，
峰值保留抽样仅用于显示；机器判定使用完整频谱。频率搜索不保证分辨任意相邻或极弱音。
这是目标驱动的最小观测工具，不是总谐波失真、SNR、噪声底或通用多音辨识仪。

## 自检与证据复现

软件单测覆盖 PCM 三种位宽、双声道反相、缺音／错频／静音／DC／满幅、
格式和配置类型、参考依赖身份、FFT 对独立直接 DFT、幅度标定、显式片段、
32 目标输入容量、覆盖拒绝、缺文件、运行中输入变化不写成功收据。
CLI 夹具全部为明确标注的软件合成输入：3 正例、6 条件反例、3 输入错误，共 12 例。
每个子进程保存原 stdout／stderr、命令、实际退出码、耗时；不以非零即视为正确反例，
须匹配具体判定／诊断。有效 WAV 的 JSON 再经 API 全量重算一致。

```powershell
python -B -X utf8 code/software/t052_audio_evidence_candidate/qualify.py verify
python -B -X utf8 code/software/t052_audio_evidence_candidate/qualify.py selftest --output code/output/t052_seal_negative_fresh.json
```

`EVIDENCE_20261011/` 保存压缩证据、逐成员清单、SHA 和复算结果。
校验封存身份／原退出码／原日志，并重新从 WAV＋配置算 9 份有效输入报告。
三项封存反例包括损坏压缩包、缺成员和连同清单重新哈希的伪造分析，均须拒收。
封存是完整性／复现机制，不是签名或采集真实性认证。Windows 上换仓库位置可复算，
跨操作系统的历史 Windows 路径转换尚未验证。旧收据中的提交／上传状态按生成时保存，
最终发布状态以外层 Git 交付收据为准，不回填旧证据。

## 后续交接

M2 复核独立工具与阈值语义，决定正式验收接入。M1 继续自己的 T052 RTL／仿真工作，
未来只需提供精确版本的合法 PCM WAV、目标频率／窗口／阈值和来源记录即可离线分析。
本轮无新增专项 RTL、Gowin、综合、PnR、设备安装、串口、接线、下载或烧录。
发布门禁若执行原仓库必跑 T007／T019 短仿真，应如实单列，不能声称完全没有 RTL 执行。
