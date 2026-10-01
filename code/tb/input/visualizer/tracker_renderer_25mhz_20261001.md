# Renderer＋tracker 25MHz独立探针收敛（2026-10-01）

负责人M2。本轮用户明确授权扩大到 `visual_score_tracker.sv`，主集成M2确认不并行修改renderer/tracker。仅本地阶段交付，验证编号和develop发布由主集成M2协调；真实M3私发停止并行修改通知仍待用户确认。

## 先定位，再优化

原`2d874f1`在保留8+8槽/25MHz条件下Fmax18.004MHz、63个Setup负端点。新的诊断副本只追加报告，取得80条pixel路径，其中24条到RGB输出、39条到tracker命中状态。最差分别是tracker帧计数→RGB（−15.542ns，67级，含距离运算及动态槽位索引）与扫描X→tracker hit CE（−15.415ns，53级，无DSP）。两类路径不能混为一个乘法瓶颈。完整失败路径保留在 `code/output/pixel_path_diagnostic_20261001/worst_pixel_path.json`、`worst_tracker_internal_path.json` 及原STA HTML；先前失败码流不作为新交付。

诊断尝试复制旧综合网表并`run pnr`，工具实际重新综合，不宣称完全复用网表。诊断结果与旧版物理指标一致，完整输入/报告哈希分别留存。

## 实现范围

1. `visual_scene_renderer.sv`：在此前常量横向几何上，将“最高槽索引→索引乘10→变量位选”换成静态一热winner与固定字段掩码OR。较高槽覆盖较低槽；命中颜色优先于漏判；RGB仍为组合输出，没有引入像素延迟。
2. `visual_score_tracker.sv`：距离计算保留FRAME_WIDTH的时间比较、减法及饱和，只有已证明 `remaining_frames < PREVIEW_FRAMES` 的分支缩窄乘除。默认remaining7位、TRAVEL9位、乘积16位；除数保留足够位宽，输出零扩展/截位与旧版一致。最近匹配从串行搜索改为平衡比较树；左子树包含较低槽，等距选择左子树。无效叶不抢占有效最大误差叶，非二次幂槽数填充无效叶。
3. 专用tracker新旧对照TB及runner；原renderer整数几何测试继续复用。

两模块参数/端口逐字保持；32位时间与回绕行为、窗口、最近命中/同距低槽优先、预告/停留/帧语义、ready/valid握手逐拍保持。没有改变wrapper、live_state、探针/正式top、音频、CDC、时钟或复位；原CST/SDC有效约束不动。新工程只引用output内追加report命令的副本。

## 行为验证

| 验证 | 结果 |
|---|---|
| Renderer整数几何四参数矩阵 | 738568次RGB比较PASS |
| Tracker新旧状态对照 | 201857次状态/隐藏存储比较PASS |
| Tracker距离函数对照 | 307680次PASS |
| Tracker最近搜索对照 | 1113次PASS |
| 既有模块/封装 | live41、score84、wrapper669 PASS |
| M2联合链路 | 13项PASS |
| 仓库门禁/补丁格式 | check_repo全PASS；git diff --check PASS |

Tracker参数矩阵：8槽/32位/preview120/travel400；3槽/8位/119/400；1槽/32位/1/400；5槽/32位/127/0；8槽/32位/2147483647/400。覆盖所有占用掩码、相同距离低槽优先、同pitch/不同pitch、已判定过滤、最大误差有效叶、窗口边界与同拍frame_start、32/8位帧回绕、存储/visible输出、复位、失步、接收和释放。TB层级赋值只用于旧新双方的边界状态设置，不进入RTL或正式工程。

```powershell
.\code\tb\input\visualizer\run_renderer_geometry_equiv.ps1
.\code\tb\input\visualizer\run_tracker_timing_equiv.ps1
.\code\scripts\run_m3_visualizer_sim.ps1
.\code\scripts\run_visual_path_integration_sim.ps1
.\code\scripts\check_repo.ps1
```

参考tracker固定到已入库的b61ec93733bd99630f87d91fa8440ef61fa4355f，不受后续实现修改影响。

## 实际综合/PnR/时序

Gowin V1.9.11.03 Education、GW5AT-LV60PG484AC1/I0；50MHz sys、125MHz serial、25MHz pixel，8实时+8曲谱槽，measured两级串行复位布局。命令 `gw_sh.exe code/output/tracker_renderer_probe_20261001/run_build.tcl`，实际run all成功。完整全链门禁与串行复位专项均PASS。

| 指标 | 2d874f1基线 | 本轮组合候选 |
|---|---:|---:|
| Logic | 8985/59904 | 6037/59904 |
| Register | 892/60780 | 889/60780 |
| DSP | 17/118 | 4/118 |
| 像素实际Fmax（目标25MHz） | 18.004MHz | 26.112MHz |
| 像素最差Setup | −15.542ns | +1.704ns |
| 像素逻辑级数 | 67 | 28 |
| 全局Setup/Hold违例端点 | 63/0 | 0/0 |
| 所有时钟Setup/Hold TNS | 像素Setup−902.928ns | 全部0 |
| Recovery最小 | +0.400ns | +0.400ns |
| Removal最小 | +0.396ns | +0.281ns |

80条导出的pixel Setup路径全正余量；新最差为视频复位同步末级→tracker hit CE，Setup+1.704ns，数据37.976ns。导出Hold表最小+0.335ns仅是现有定向表口径，不宣称全局最差Hold；全局Hold端点0由STA总表证明。

两组存活CDC载荷仍为event6/score19，10ns界限和7组精准后级报告保持PASS，不外推完整64/98位物理覆盖。引脚门禁通过，PR1014仍存在。综合原语renderer无乘法器；tracker8个MULT12X12，与物理DSP4不是同一计数口径，不互相替代。

## 证据与哈希

- renderer SHA256 `73a44958a150e91621fa3f01d88fd951ac1cdd6b75bba4fd67c2a845f55e37a0`
- tracker SHA256 `b9d2d7da2aa80ba0e9db01fd2426d35ebf1c5c3a32f74a8cc27b7e24211baa22`
- 本轮STA HTML SHA256 `990094336d046de56ad11c61974c22723e6c17ca024522ba14fe0e7b34b25ae6`
- 独立探针.fs SHA256 `5b7a14b14963c7a158e348e282ebd9778dc15b9b32dd444a926a664d6f4afb22`（合成事件/曲谱激励；不是正式演奏版本，不因L5通过就自动烧录）
- 所有输入/报告哈希与门禁摘要：本工作树 `code/output/tracker_renderer_probe_20261001/evidence.json`。
- 源码/报告复核包：`code/output/visual_25mhz_tracker_renderer_review_20261001.zip`，SHA256 `48017752a060e0fd5d6678060f2cd883ba784363dd48433b9d6941a1286e4ef1`，183332字节，不包含.fs。
- 原始PnR与完整路径：同工作树 `code/output/tracker_renderer_probe_20261001/impl/pnr/`。旧失败诊断仍保留，未覆盖。

## 等级与下一步

实际达到L2行为等价和**独立探针L5工具侧**。没有上板、没有真实曲谱源/键盘/音画共存、没有蓝灰探针L6或双模式L6。T034最终报告/S5整机任务不据此关闭。

由主集成M2独立复核输入哈希/等价范围/路径和门禁后协调发布与正式接线。若需要wrapper像素流水、有效约束、正式top或其他写集变化，重新走受控流程。M3负责之后安排的实屏取证；本候选不自动占用板卡、不自行烧录。
