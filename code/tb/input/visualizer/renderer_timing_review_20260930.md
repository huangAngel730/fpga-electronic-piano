# 渲染器常量几何优化验证（2026-09-30）

M2 隔离候选，基于 `b61ec93` 中 M3 `74cae4c` 渲染器。用户授权接手 renderer/TB；M3 真实私发接手通知仍待用户确认。主集成 M2 已确认不并行修改本次源文件。本轮成果只作本地提交，未推送或取验证编号，由主集成M2复核后发布。

## 改动和保持条件

唯一功能改动是 `visual_scene_renderer.sv` 的横向几何：把音轨倒数乘法/校正、按音符计算的横边界乘法和键盘动态索引，改为参数展开的常量区间比较及一热编码。RGB 仍为组合输出，没有新增像素延迟。参数与端口逐字保持，8实时槽+8曲谱槽、较高槽覆盖较低槽、hit优先于miss、键盘/失步提示覆盖顺序均保持。

依据为 HDL 源码分析，不是 CodeGraph 索引（HDL 未被索引）。

对于音轨 k，像素归属为 `[ceil(k*W/N), ceil((k+1)*W/N))`；边框仍为旧版 `floor(k*W/N)` 口径。音符内域为 `floor(k*W/N)+1` 至 `floor((k+1)*W/N)-2`，不足三像素宽时为空。所有乘除仅用于生成期常量。tracker、live_state、wrapper、正式顶层、CST、SDC、时钟与复位源码保持原字节。

## 实际验证

- `code/scripts/run_m3_visualizer_sim.ps1`：41 live、84 score、669 wrapper 自检 PASS。
- `code/scripts/run_visual_path_integration_sim.ps1`：13 项 PASS。
- `code/tb/input/visualizer/run_renderer_geometry_equiv.ps1`：独立整数几何参考，四组参数共738568次RGB比对 PASS：640/49/BASE36（277280）、37/13/BASE100（153764）、17/49/BASE36（155172）、1/128/BASE0（152352）。覆盖全部16位X、分数边界、所有占用掩码、8槽重叠优先级、hit/miss颜色、屏外/消隐、失步覆盖和确定种子随机场景。
- `code/scripts/check_repo.ps1`：全项 PASS；`git diff --check` PASS。

运行命令（工作树根目录）：

```powershell
.\code\tb\input\visualizer\run_renderer_geometry_equiv.ps1
.\code\scripts\run_m3_visualizer_sim.ps1
.\code\scripts\run_visual_path_integration_sim.ps1
.\code\scripts\check_repo.ps1
```

## 物理验证状态

新源码的独立完整探针完成综合/PnR/码流生成，但全链STA门禁 **FAIL**，因此没有达到L5，不得下载生成的`.fs`。没有实屏测试或正式音画共存验证。串行复位专项PASS与全链失败分别记录。

| 指标 | M3 74cae4c原版 | 本轮候选 |
|---|---:|---:|
| Logic | 9728/59904 | 8985/59904 |
| Register | 892/60780 | 892/60780 |
| DSP | 40/118 | 17/118 |
| video_pixel实际Fmax（目标25MHz） | 17.487MHz | 18.004MHz |
| Setup违例端点 | 64 | 63 |
| video_pixel Setup TNS | -941.290ns | -902.928ns |
| 全局Hold违例 | 0 | 0 |
| 最差Setup（High_Fanout pixel_clk行） | -17.182ns | -15.542ns |
| Recovery最小 | +0.400ns | +0.400ns |
| Removal最小 | +0.284ns | +0.396ns |

工具：Gowin V1.9.11.03 Education；器件GW5AT-LV60PG484AC1/I0。使用原50/125/25MHz时钟、8+8槽和原SDC，保留先前measured串行复位FF位置。官方参考目录已不在原路径，本轮直接复制主集成工作树中已核验的vendor副本，构建脚本重新核验固定SHA256：PLL `ededfd3e361c7e9b4523de6b3b50e00c98baed5b9900a361c606ab574376f9ba`，GUI DVI `b378c6a41d06a14215dc9ec54ed20bfc91309a0bb1543c589246717da3aee2ab`。没有重跑旧版蓝灰探针。

完整STA检查器唯一错误为Setup端点63；引脚、时钟、定向CDC等其他门禁保持通过。存活CDC载荷路径为event6/score19，不代表全64/98位覆盖。PR1014保留。综合层级报告中renderer为2个MULT12X12、tracker为8个MULT27X36；这是综合原语口径，不与上表物理DSP资源数相加或互代。

## 哈希及原始资料

- renderer：`f617887c69c809db899503e0349f5f9a3af0e9f78ae45380cbf1456047710cf6`
- 原始STA HTML：`f3cc9cb6920bb1436f13fbb4ac3d1b97ca2a539d21914d0239a400f5bb696cb0`
- 原始PnR文本报告：`d60beef64582f1b65469313bffb62f9a8910eaa28b2abf1674018b1de88dae22`
- 本工作树 `code/output/renderer_timing_evidence_20260930.json`：完整输入/报告SHA256、参数与门禁结果。
- 报告和输入快照包 `code/output/renderer_timing_review_20260930.zip`：SHA256 `8ae16ded82e02286c5dd0cd4860f36999ded1921f6bb861d41033b519724a800`，125484字节，不包含失败码流。
- 全部原始PnR产物仍在 `code/output/visual_full_path_probe/measured_serial_reset/impl/pnr/`；行为/仓库日志在本工作树 `code/output/`。

## 后续复核边界

横向几何收益已测得，但25MHz目标未完成。现SDC只导出CDC定向路径，仍没有失败像素路径的完整起止端点；不把67级逻辑或High_Fanout行冒称完整路径定位。主集成M2需先补全失败像素路径报告（仅增加报告，不改变原约束）再决定下一补丁。若需改tracker、wrapper/像素延迟对齐、顶层、复位或SDC约束，必须先协调扩大范围。此轮没有擅自扩大。不得因为面积下降或仿真通过把T034/S5改为完成。
