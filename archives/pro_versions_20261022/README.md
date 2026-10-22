# Pro 三版本历史归档 · 2026-10-22

[下载完整源码、码流与资料包](pro_versions_20261022_sources_bitstreams_docs.zip) · [文件清单](ARCHIVE_CONTENTS.json) · [SHA-256](SHA256SUMS.txt)

本文件夹按用户要求保存当天已交付的三个历史版本；没有创建新的 GitHub 仓库，也没有改动正在调试的工程。归档以 ZIP 保存原始文件及换行字节，配合本仓库不直接跟踪 `.fs` 的规则；内容明确如下。

| 版本 | 包内源码目录 | 包内原始码流文件 | 原报告最差 Setup |
| --- | --- | --- | --- |
| 基础四声部 A08 | `versions/01_basic_A08/` | `bitstreams/01_pro_audio_basic_A08.fs` | +2.823 ns |
| 传谱、回读、播放、双滑块 R10 | `versions/02_score_slider_R10/` | `bitstreams/02_pro_audio_score_slider_R10.fs` | +1.812 ns |
| 波形显示、键盘切页 R01 | `versions/03_waveform_R01/` | `bitstreams/03_pro_audio_score_slider_waveform_R01.fs` | +2.697 ns |

解压后顶层目录为 `pro_versions_20261022/`。其中还包括：

- 三版实际冻结的 RTL、真实 IP HDL、头文件、ROM、CST/SDC、重建脚本、原生时序报告及验证交接资料。
- `shared/ble_pc_software/`：ESP32-C3-Zero-M 固件源码、最终 4 MB 镜像、PC 传谱工具、示例与测试。
- `shared/android_score_transfer/`：安卓源码、APK、示例 JSON 和测试资料；不含私有签名密钥、个人 SDK 路径或构建缓存。
- `docs/`：使用、键盘映射、接线、工具版本、Pro 原理图与原始引脚参考。
- `provenance/`：原件路径及逐文件 SHA-256；未使用的旧物理数据库排除说明。

固定工具为 Gowin 商业版 V1.9.12.04，目标 `GW5AST-LV138FPG676AC1/I0`、C 步进；50 MHz 参考、40 MHz 音频核心，显示版 25/125 MHz。每版工程以其根目录 `rebuild.tcl` 为重建入口。原 GUI 工程、报告里的本机绝对路径属于历史证据；跨机器优先使用相对路径 Tcl 生成新工程。

**这是历史备份，不是故障修复完成版。** 本批 R10 原始码流曾被实测报告双键松开后约 15 秒异常拖尾、HDMI 后续显示异常；本归档未替换为后续修复版。波形版已有源码仿真与原生时序证据，尚未上板，不推定它已解决 R10 现场问题。频谱仅预留，无 FFT。完整 C9、精确最小 N/尾窗与完整实机验收未签通过。本次上传不执行 EDA、烧录、串口或设备操作。

校验方法：下载本目录文件，在本目录运行 `python -B -X utf8 verify_download.py`，会校验 ZIP 本身及内部每份文件。也可解压后运行包内 `verify_archive.py`。三份码流按原交付 SHA-256 核同；归档不保证重新布局布线得到逐字节相同码流。
