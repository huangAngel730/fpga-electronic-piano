# R13 李萨如显示增强

本工程从已通过时序的 R12 单独复制。K4（CC74）81–127 进入李萨如页面。横纵共用 2 倍显示倍率，坐标中心保持不变，PCM 观察桥和 27 采样延迟沿用 R12。8 倍和 4 倍的对照仿真均触碰绘图区边缘，最终采用 2 倍。它只影响显示幅度。

左上角的浅青白色标题为 Lissajous Figure，左上像素坐标 (16, 24)，5×7 字模以 2×2 像素绘制。位置、字符、字模行、点阵取位和输出分五拍，与原 HDMI 像素流水对齐。

ModelSim 整机回归记录了 140×140 像素的轨迹包络、3 次发布、4,559 个轨迹像素和 2,848 个标题像素。11,135 个音频帧，启动后零漏帧。其余七组回归通过。R13 尚未烧录，实物 HDMI 显示待测。

使用 Gowin 商业版 V1.9.12.04。项目入口 project/rebuild.tcl，采用 R12 的 Place3／Route2、面积优先、资源复制关闭和 Hold 修复。

    $env:C1_RUN_PNR = '1'
    $env:PRO_EXTENSION_BUILD_DIR = Join-Path (Get-Location) 'BUILD_R13'
    & '<Gowin 商业版 V1.9.12.04 路径>\IDE\bin\gw_sh.exe' (Join-Path (Get-Location) 'project\rebuild.tcl')

## 同版构建与码流

首轮 Setup −0.488 ns、81 个违规端点，Hold 零违例。后继将音频事件和逐帧频控字分路，用相位加法进位判断回绕。仿真加入等价断言并通过。修复后 Place3／Route2 用时 23 分 58 秒，工具退出 0。

Setup +0.032 ns，Hold +0.069 ns，Recovery +2.878 ns，Removal +0.080 ns，最小脉宽 +6.815 ns，均零违例。Setup 有两条正余量路径低于额外 +0.050 ns 目标。保留 Gowin PR1014 参考时钟警告。码流 42,340,876 字节，SHA-256 为 0b994492ecd4ac4a6e504568e2a71ed9f048ef572ceea56ac03193f4bd26363c。
