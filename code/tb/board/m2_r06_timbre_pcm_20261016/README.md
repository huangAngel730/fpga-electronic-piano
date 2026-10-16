# R06 Program 0/1 到 PCM24 的隔离对照（40 MHz）

从同一冻结 R06 ZIP 精确抽取 M1TD 音频链、ROM、接口包；不改原源码。并行运行三个相同 Note60/velocity1023 声部：复位默认钢琴、NoteOn 前 Program1 的三角、Program1 后保持原设定的三角参考。第64帧后只向第二路送 Program0，三角参考不送；已在响的三角音必须继续逐帧等于参考。关闭延迟效果，仅看音源 PCM24；测试台用 40 MHz 时钟及 833/833/834 拍帧请求循环，不把模拟采样率当实测。

在仓库根目录运行，需要已有 OSS CAD Suite（可用 `--cad` 指定安装目录）：

```powershell
python code/tb/board/m2_r06_timbre_pcm_20261016/run.py --output code/output/m2_r06_timbre_pcm_20261016_03
```

输出目录必须全新且位于 `code/output/`。runner 核 R06 ZIP SHA；保存每个输入源/ROM、工具可执行文件的 SHA、命令、cwd、耗时、退出码及原始 stdout/stderr。Yosys Slang 仅把原 M1TD 分配器转换为 Icarus 可编译的 Verilog；Icarus 编译其余冻结模块，VVP 各运行一遍正例和跳过 Program1 的反例。反例须实际失败并带 `TIMBRE_PCM_NOT_DISTINCT`。工具输出、截取的原始流和可复跑源码见 `code/docs/evidence/m2_r06_timbre_pcm_20261016/M2_R06_TIMBRE_PCM_ISOLATED_20261016.zip`。

最终 `_02`：Yosys/Icarus/正例/反例退出码 0/0/0/1；128帧，钢琴/三角各127帧非零，128帧不同；切回 Program0 后的64帧保持三角参考逐样本相等。`_01` 曾在帧间多等待一拍，原双流及该版TB按哈希还原保存；修正后 `_02` 重跑两例。此处的 L2 仅为**统一事件输入到冻结 M1TD PCM 结果**；另一个隔离回归核真实 MIDI 字节到 Program 路由，两者不属于同次贯通执行。未证真实键盘原始PC字节、同版完整帧缓冲/I2S、效果开启、模拟发声、实物起音延迟或正式码流；`board_release_allowed=false`。
