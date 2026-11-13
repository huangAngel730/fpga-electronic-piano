# N32 C1 R13 李萨如显示增强

这是 `N32_C1_R13_LISSAJOUS` 的独立源码归档。K4（MIDI CC74）在 81–127 进入李萨如页，横纵显示倍率为 2，左上角显示 `Lissajous Figure`。该版本沿用 R12 的 PCM 观察桥和 27 采样延迟。[原交付说明](README_FIRST.md)

[另一个 R13（M3 旋钮与滑块闪烁修复版）](../m3_r13_knob_flicker_20261025_r01/README.md) 有独立的顶层快照、源码清单和位流身份。团队重建时应在各自目录内使用对应工程。

## 核对归档

在本目录运行，使用 Python 3.9 或更新版本的标准库。

```powershell
python -B -X utf8 .\verify_archive.py
```

校验器核对发布清单的文件大小和 SHA-256，确认 Tcl 与 Gowin 工程的 131 个注册输入一致且都在归档内。归档包含 RTL、PLL/DVI IP 与头文件、CST/SDC、ROM 及其拆分表、Gowin 工程和 Tcl。清单分列原包 SHA 和入库 SHA，标出 LF 与文件边缘空白的规范化。原厂 IP 标记随源码保留。原始构建输入清单和历史报告可追溯到同一份原包。原包的 `SHA256SUMS.txt` 覆盖全部 262 个载荷，本目录只收录发布清单列出的子集。[发布清单](ARCHIVE_MANIFEST.json) · [历史构建输入清单](evidence/native/SOURCE_SHA256.json)

## Gowin 重建

从本目录执行。将示例中的 `$gowin` 改为本机 Gowin 商业版 V1.9.12.04 的 `gw_sh.exe`，并使用有效许可证。建议工程路径和输出路径使用 ASCII 字符。目标器件为 `GW5AST-LV138FPG676AC1/I0`（C 步进），顶层为 `pro_audio_minimal_top`。以 [rebuild.tcl](project/rebuild.tcl) 为重建入口。脚本创建新工程，把 ROM 复制到运行目录，并加载 [options.tcl](project/options.tcl)。[pro_audio.gprj](project/pro_audio.gprj) 可用于查看源文件登记。

```powershell
$gowin = 'D:\Gowin\Gowin_V1.9.12.04_x64\IDE\bin\gw_sh.exe'
$previousBuildDir = $env:PRO_EXTENSION_BUILD_DIR
$previousRunPnr = $env:C1_RUN_PNR
try {
    $env:PRO_EXTENSION_BUILD_DIR = 'D:\FPGA\BUILD_N32_C1_R13_LISSAJOUS_01'
    $env:C1_RUN_PNR = '1'
    if (Test-Path -LiteralPath $env:PRO_EXTENSION_BUILD_DIR) {
        throw 'Choose a new output directory for this rebuild.'
    }
    & $gowin (Resolve-Path -LiteralPath '.\project\rebuild.tcl').Path
    if ($LASTEXITCODE -ne 0) { throw "Gowin exited with code $LASTEXITCODE" }
} finally {
    $env:PRO_EXTENSION_BUILD_DIR = $previousBuildDir
    $env:C1_RUN_PNR = $previousRunPnr
}
```

`C1_RUN_PNR=1` 启用布局布线。省略该开关时入口默认只跑综合。每次使用新输出目录，并复核该次构建自己的时序报告和位流 SHA。

## 仿真入口与实测状态

原 [ModelSim 驱动](run_c1_sim.py) 随测试平台及三份辅助源文件保留。以 `top` 为例，第二个位置参数必须是新建的输出目录。

```powershell
python -B -X utf8 .\run_c1_sim.py 'D:\ModelSim\win64' 'D:\FPGA\SIM_R13_LISSAJOUS_01' --kind top
```

`extra` 的历史比对需要 `--reference-r05` 指向原交付 ZIP 内的 R05 参考 ZIP，SHA-256 为 `e14f6326009fbdf611ceb426c7dbc34106d301e19c4ce9ffc86e5000a00482df`。原驱动的 `fx --reference-r04` 是可选对照，需要单独取得驱动指定 SHA 的 R04 包。两份参考 ZIP 均属于仿真对照材料，Gowin 重建入口不读取它们。

本次入库验收覆盖归档文件、重建依赖和仓库门禁。上游历史报告记载同版商业 Gowin 构建退出 0，Setup +0.032 ns、Hold +0.069 ns，均无负余量端点。历史位流 SHA-256 为 `0b994492ecd4ac4a6e504568e2a71ed9f048ef572ceea56ac03193f4bd26363c`。[历史构建回执](evidence/native/receipt.json) · [历史时序结论](evidence/native/STA_VERDICT.json)

原交付说明中的“尚未烧录”记录的是封包时的状态。后续 Flash 写入及编程器校验均退出 0。断电自启动、HDMI 实物显示及整板验收仍待实测。[主开发交接](../../docs/MAIN_DEV_HANDOFF_R13_FLASH_2026-11-13.md) · [Flash 校验回执](../../docs/evidence/r13_flash_20261105/FLASH_PROGRAM_VERIFY_RECEIPT_20261105.json)
