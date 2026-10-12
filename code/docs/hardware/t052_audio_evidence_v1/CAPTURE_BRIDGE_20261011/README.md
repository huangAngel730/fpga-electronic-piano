# T052 捕获到 WAV 独立适配器（任务 D）

M3，2026-10-12。仅新增任务单 D 两处目录，不修改 M1 的 DUT／模型／TB／checker／runner，亦不修改 ee0273a 已签 WAV 工具或共享表。复核、统一登记归 M2；本交接待用户转发，尚未送达。

## 实现和验收范围

入口为 `code/software/t052_audio_evidence_candidate/capture_bridge_20261011/bridge.py`，只使用 Python 标准库。输入是固定格式请求及四路 signed16 捕获；两文件无 END，以固定版本原 SHA 和显式 4137 行绑定完整性。ASCII 整行匹配，不忽略空行、未知 tag、附加字段或尾记录。检查 8-bit ID 范围及逐行 ID 对应、32-bit FCW 的八位十六进制格式、4-bit mask、ACT=mask 位数、CLIP 严格 0/1、signed16 值域。重复／回绕 ID 合法，以 ordinal 定位，**不要求 ID 全局唯一或逐行递增**。

四份 mono PCM16 WAV 保留每条原 lane 整数，无增益、滤波、插值、混音或重采样。每路全部 PCM 字节重新读取并比较；`sample_mapping.jsonl` 给出每条原请求／捕获行号、ID、mask、ACT、原 CLIP、四值、FCW、WAV frame／PCM 区及文件字节偏移。CLIP 只保留来源，不做其数学／提交链削波判定。

运行新桥软件自检（最终 31 项），包括负数与 ±16-bit 端点、16 masks、ID 重复／回绕、精确 WAV 样本偏移和错误结构／身份／计数／速率。另执行 12 项 CLI 指定拒收。没有重跑 ee0273a 的旧 29 单测、M1 数学 checker 或专项 RTL。首轮桥 29 自检及其封存保留于旧输出；最终新增两项测试并重封，不回填首轮。

等级只为 **L0/L1：格式、身份约束、无损 WAV 导出与软件自检**。M2 原 4137／16548 lane 数学结果只列 REUSED V0289，未重新运行或提升结论。

## 固定输入与时间口径

原件来自仓库 `code/docs/evidence/m2_t052_modelsim_delivery_review_20261011/RAW_REVIEW.zip` 中的 `original/T052_repair_v2_pkg/`。精确成员和整个来源 ZIP 的 SHA 见封存 `reference_inputs.json`。原包源／TB／日志和只读 ROM 等依赖按原字节随包保留，仅作来源参考，不导入或执行。

| 对象 | SHA256 |
|---|---|
| `logs/tb_t052_polyphony.capture` | `5c67ab75d74537aca9c9c3c69d20eb3be0a0c65d7b940dd027576454cca68fc0` |
| `logs/tb_t052_requests.log` | `4e5ceaf804dca473cd81270f3add4ce7dc2808554d676dca314ea2ac27946570` |
| 原 TB | `7e1fcd31698cb3778f13b3edc4566504e1ddbe4b175af8193fe9cad258090c4c` |

显式选择容器整数速率 **48000 Hz，仅 `logical_replay_rate`**，供统一逻辑播放，不证明真实时钟。原 TB 为 50 MHz／1042，即 `50000000/1042` Hz（约 47984.644914 Hz），以有理数原样记录；不能用整数 WAV 精确表示该物理时间率，申请 `physical_time` 模式会明确拒收，不默取整或插值。

每条 FCW 的逻辑重放频率均按 `FCW × wav_rate / 2^32` 给出精确分子／分母。`04b17e4d` 在 48k 约为 880.000021 Hz，不沿用旧 440 标签。随机 FCW 长段不标固定四频率 PASS，也不运行频谱验收。

来源标 `RTL_CAPTURE_REPLAY`，不是 `physical_recording`。以下恒 false：`provenance_verified`、`independent_voice_count_proven`、`physical_validation`、`sample_timing_verified`、`T052_complete`。导出不证明 ModelSim 执行源身份、请求真正接受握手、背压、PCM24 commit、独立四音／生产32音或物理 STA。完整 T052／T060／T061 保持 PARTIAL。

## 可复现命令

在仓库根目录，用 Python 3.11；每次替换成**全新**输出目录，不覆盖历史：

```powershell
python -I -S -B code/software/t052_audio_evidence_candidate/capture_bridge_20261011/delivery.py qualify --output code/output/NEW_BRIDGE_QUALIFY
python -I -S -B code/software/t052_audio_evidence_candidate/capture_bridge_20261011/delivery.py verify --sealed code/output/NEW_BRIDGE_QUALIFY --output code/output/NEW_BRIDGE_VERIFY
```

资格执行包含新自检、实际 4137 行结构导出和 12 CLI 拒收；每子进程最多 90 秒、整轮最多 300 秒。隔离 verify 从封存恢复桥和原输入，用 `-I -S` 单独导出，逐字节对比四 WAV、完整 mapping 和 receipt，不读工作树模型。执行前后桥三源 SHA、实际 Python exe SHA、原 stdout／stderr、退出码均入包。运行脚本不启动任何仿真器、Gowin 或设备。

仓库版封存为 `SEALED_20261012_01/BRIDGE_EVIDENCE.zip.b64`，SHA/大小见同目录 `seal.json`；verify 也直接支持该 Base64 版本。完整转发 ZIP 额外给出直接可解压的 `BRIDGE_EVIDENCE.zip`，M1／M2 不必访问 GitHub 即可获得全部原输入、参考源依赖、新代码、四 WAV、映射及日志。

独立资格结果与发布门禁分开记录。最终 staged tree 必须跑仓库九门禁才提交／普通推送 develop；其中强制短 T007/T019 基础检查不作为本项新音频验证。遵照此次任务单，不改共享看板／编号表，由 M2 复核登记。没有新 T060 RTL 补采许可，没有综合、PnR、串口、安装、接线或烧录操作。
