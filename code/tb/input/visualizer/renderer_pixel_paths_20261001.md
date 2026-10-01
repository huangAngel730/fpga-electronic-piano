# 像素失败路径定位与槽位选择候选（2026-10-01）

M2本地阶段，基于`2d874f1`。本轮没有改变原时钟/复位/CST/SDC约束、tracker、wrapper或正式音频；只追加报告副本并落实现授权renderer的一热槽位选择补丁。未推送，验证编号由主集成M2最后fetch后发布。

## 诊断实际执行

使用`code/output/pixel_path_diagnostic_20261001/`新目录，保留上一轮的报告/码流。原SDC所有约束逐字保留，只有下面两条报告请求追加在副本末尾：

```tcl
report_timing -setup -from_clock [get_clocks {video_pixel}] -to_clock [get_clocks {video_pixel}] -max_paths 80 -max_common_paths 1
report_timing -setup -mod_ins {u_scene/u_renderer} -max_paths 20 -max_common_paths 1
```

实际命令是Gowin `open_project` + `run pnr`。虽然已复制综合网表，工具仍重新综合；不得声称完全复用旧网表。原SDC SHA256 `f3f591f383b650e4fadb5130306763e2b357b1c356bedd1f3c1c4032ce181692`。原网表与新网表哈希不同，本轮按自己的原始报告定位。Gowin V1.9.11.03 Education / GW5AT-LV60PG484AC1/I0；8+8槽，50/125/25MHz，保留measured两级串行复位位置。

结果与上一轮的物理指标相同：像素18.004MHz，Setup63、TNS−902.928ns，Hold0；完整门禁唯一失败项Setup63。新增加的Setup_Slack_Table10含80条路径，其中63条负余量、17条正余量，完整分析路径保留于HTML和JSON。

## 已定位的两类路径

| 类别 | 路径 | 最差余量 | 逻辑级数 | 数量 |
|---|---|---:|---:|---:|
| RGB输出 | tracker `current_frame_1_s0/Q` → `dvi_g_4_s0/D` | −15.542ns | 67 | 24负路径 |
| tracker内部命中 | 扫描 `pixel_x_6_s0/Q` → tracker `hit_mem_7_s1/CE` | −15.415ns | 53 | 39负路径 |

最差RGB路径数据延迟55.479ns，cell32.642ns/route22.469ns/tC2Q0.368ns。经过tracker的32位减法、MULT27X36，再经过渲染器层级组合节点和槽位索引MULT12X12；索引单元自身4.163ns。综合节点可能跨层级优化，不能只以节点前缀宣称某一模块唯一负责全部延迟。

tracker内部路径没有DSP，属于另一类组合链。因此不能宣称只收窄距离乘除就能全部收敛。下一阶段需协调允许修改tracker的距离计算和最近命中选择结构，保留最近匹配/同距低槽优先、帧/命中窗口/停留语义逐拍等价。此轮tracker没有改动。

## 现授权renderer补丁

将“最高槽索引→索引乘10→变量位选”换为静态一热winner和逐槽固定字段的掩码OR。较高槽覆盖较低槽，hit优先miss，模式/琴键/失步覆盖不变，参数端口和组合RGB无新增延迟。

- 最终静态写法四组整数几何参考共738568 RGB对照PASS。
- 41 live、84 score、669 wrapper与13联合项PASS。
- Gowin综合通过，renderer的两MULT12X12消除，LUT4647→4035，ALU174→176；仅综合原语统计，不能换算或外推物理DSP/Fmax。tracker的8个MULT27X36保留。
- 本一热补丁没有执行新PnR，不能沿用诊断基线18.004MHz作为新补丁频率，不声明25MHz或L5完成。

运行renderer参考和现有回归命令同`renderer_timing_review_20260930.md`。原代码/参数/端口边界以提交diff和哈希为准。

## 证据

- 新renderer SHA256：`73a44958a150e91621fa3f01d88fd951ac1cdd6b75bba4fd67c2a845f55e37a0`
- 诊断原始STA HTML SHA256：`94f3373b472681c1cd896c4186eb6d52fbeef13d8166b7ecc1f17338726b2f14`
- 一热综合层级XML SHA256：`679d8cc88c757b1b827f58da56762c40437985ab3c75c094153070052aa3d218`
- 报告包：本工作树`code/output/renderer_paths_onehot_review_20261001.zip`，SHA256 `e1d604e987760202cf90db4055f56273fe8cc5a5021ce62fa5abb3b94734ea1e`，163499字节，不含.fs。
- 诊断输入/路径/哈希：`code/output/pixel_path_diagnostic_20261001/path_evidence.json`、`worst_pixel_path.json`、`worst_tracker_internal_path.json`，及同目录`impl/pnr/`原始报告。
- 一热源码/综合/行为证据：`code/output/renderer_onehot_candidate_20261001/final_evidence.json`、四组static_sim日志、`code/output/renderer_onehot_synthesis_20261001/`。

主集成M2已收到tracker扩范围申请；真实M3私发停止并行改写通知仍未确认。不能将这份跨窗口消息冒称真实M3已通知。T034/S5不关闭，禁止下载失败探针，不需要M3重复旧版试验。
