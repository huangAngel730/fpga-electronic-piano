# M3 R13 旋钮与滑块闪烁修复版：源码及工程归档

这是用户指定 R13 原包的派生源码归档。生产源码和原始证据按字节复制，保留完整 source 的 126 个文件（913,402 字节）；不接合或替换仓库现行生产树。

## 来源与范围

- 原包：R13_KNOB_FLICKER_TIMING_PASS_20261025_R01.zip，10,340,752 字节。
- SHA256：39e0a44621c51bfecec958276cbba809a00f668aad791ad4896f5ebd4cbefb9e。
- 原包 819 成员、818 载荷的 CRC、完整成员集合、大小与 SHA、Windows 路径和解压读回已由准备窗口独立核验；原回执保存在 provenance/LOCAL_PREPARATION.json。
- UPSTREAM_MANIFEST.json 是完整原包清单的原字节副本。本目录只收录明确子集，不能用它或原 verify_package.py 声称本目录包含整个交付包。
- ARCHIVE_MANIFEST.json 列出本目录实际文件与来源映射。原始文件 SHA 和由根 .gitattributes 规定的 LF 检出变体分别记录；没有另改换行规则。
- FS、VG、大型 TR、重复报告和运行副本不进入此代码归档；完整原件继续保留在本地原 ZIP 和准备目录，来源及精确 SHA 由原清单追溯。

## 校验及重建

先在本目录运行：

    python -B -X utf8 verify_archive.py

此命令只检查所列派生归档文件身份和成员集合，不运行 HDL、EDA 或硬件。
工程入口为 source/project/pro_audio.gprj；推荐用 REBUILD_ON_TEAM_PC.ps1 的 -GowinExe 参数指定本机实际商业版 gw_sh.exe，调用 source/rebuild.tcl 和 source/options.tcl。
目标为 GW5AST-LV138FPG676AC1/I0、C 步进、pro_audio_minimal_top。90 个工程注册输入、包内 IP、ROM 和头文件已作静态齐套核对。商业版 Gowin V1.9.12.04 build2743 和许可证不随包提供。
输出在 source/REBUILD/pro_audio；已有输出时原入口停止，避免覆盖。实际重建必须在获准的独立副本中进行，并重新核验新报告与新 FS，不能继承旧时序数字。
source/project/impl/pro_audio_process_config.json 是 GUI 配置输入；本目录 .gitignore 仅为它保留精确例外，其他 impl 生成文件仍忽略。

## 已有验证与限制

上游 RELEASE_RECORD 记录 Setup +0.741 ns、Hold 0.000 ns，Setup/Hold 违规端点均 0；本机核对的是报告身份，未重新执行这些仿真或 EDA。
R03 诊断 UART 消费支路与位置约束修改适用原记录中的同周期对照；其余未变 HDL 复用 R02 系统回归。不得称本机重新跑过整套 R03 回归。
原始发布记录保存在 evidence/bitstream/RELEASE_RECORD.json，保留 hardware=NOT_RUN、board_release_allowed=false、full_CDC_or_C9_signoff=false。
本归档、静态核验及 GitHub 发布均不构成烧录或板级验收。

SOURCE_DEPENDENCIES.json 列出辅助脚本的可移植性限制：build_candidate.py 和 run_checks.py 含原机工具路径，后者还缺少五个历史辅助输入；这些不属于推荐生产 Tcl 的重建依赖。
历史 verification 和 handoff 中的路径是上游实际来源记录，不是任意电脑可直接执行的保证。冻结源码和原件未为消除这些路径而改写。

## 控件范围

K1/CC7 音量；K2/CC91 上飘或下飘；K3/CC71 音色选择；K4/CC74 波形或频谱预留页。波形、频谱实际算法尚未接入；曲谱只控制下飘，真人 MIDI 发声。
完整上游说明见 provenance/UPSTREAM_README_FIRST.md；Git 发布状态、提交和远端包含证据由固定 Git 窗口的独立发布回执记录。
