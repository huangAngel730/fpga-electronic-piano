# 第二任务 E1 双滑块复用核查（2026-10-17）

## 结论与执行边界

**E1 已有离线候选覆盖本次任务单列出的隔离自检条件，可直接复用；未发现必须新增的候选代码修法。E1完整拓展仍为PARTIAL，正式Pro接入/完整STA/实屏与同版音画待件。** 本次仅L0来源、Git blob、原ZIP CRC/成员SHA及覆盖差额核查，新增E1功能测试/编译/仿真/EDA/设备调用均 **0**。旧1轮100.282秒L2记录保留，不改写为本次新运行，不恢复或消费旧剩余额度。

本次唯一写入为本文件；不改旧source_audit、实现、原封存及共享文件，未读E2/E3/E4新实现，未联系其他聊天。新单允许E4 N32离线工作的变化已识别，但本子任务仅负责E1，不启动E4。

授权输入：

- 用户原文件 `E:/FPGA/GAOYUNFPGA/night_task/10.17/M3_四项完整拓展主责任务单_2026-10-17 (1).md`，SHA-256 `b8e6372b7cd9261f276247754a8f2f9bc8841c31344edc3116a78827d964ed0e`。
- 总控 `task2_coordinator/NIGHT_PLAN_20261017_TASK2.md`，读取SHA `12380780313e42766cd2c35a434675b0e58614bee40757e4ff13027dd9bdfb97`；E1复用、不重跑，原夜间05:21硬截止保持。
- 当前读取HEAD：`ad2de2169230dc8fd9f4b6f8157d384306c2479a`。原验证执行基线仍是 `b6f289110a0b7341f1f9234c945bcb8d31d95aff`，不能把发布提交写成原运行基线。

## 1. 发布源码与原件身份

对下表六文件，使用 `git rev-parse ad2de216…:<path>` 与只读 `git hash-object -- <path>` 核Git blob一致，再对工作树原字节计算SHA-256。路径根为三个既有 `pro_parallel_20261016/` 目录。

| 对象 | SHA-256 | ad2de216 Git blob |
|---|---|---|
| RTL/dual_slider_pro_parallel.sv | `c0bbcc715edb573a160ce54c4d01982f15881dd311bdd38131d379059a48fc70` | `d9aef0239b90a24d82449917110acea9759344ef` |
| TB/tb_pro_parallel.sv | `02337b8db37f849fdbe1b4c8a3f1200a117ea0a0e60ce7c15a1f923325823d9c` | `b451af92dce14d6e549ba184f2adfb5d4bd05466` |
| docs/DELIVERY.json | `93c06ca429a6f93e281f3d058b114496abe01586d136eafc32f8b869f6fc1b50` | `70c1f78b82f0424c913c18c2c2f96dd20eefcb4f` |
| docs/NIGHT_RUN_RECEIPT.json（汇总） | `875bc5fb27fda0134f1dbbfac2bce88290127642b479d5f67892559b25265e9d` | `886667f057020802daf3403fb34237f37e8a7875` |
| docs/RESULT.md | `fb11beb33298ba485978f9e9763f2a43064070510af85d635b07dec3b5e6d14a` | `68622d20a7cf4729a96d4bfe502742fb26da07cc` |
| docs/INTEGRATION_DIFF.md | `f1ae6a7d6bbc526c3d5cf0f5ab374a5464ca654b75d7454b9c8879f98c545d53` | `abd39396b9a24375e8d43316af166cb805fd71c2` |

原封包本体 `code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/M3_DUAL_SLIDER_DEFAULT_FIFO32_ISOLATED_20261017.zip`：542997字节，SHA **`2de22e136aa074604407592b7df91af9ff2db05357b1d508a61de9ec7c313757`**，与DELIVERY一致。它及展开MANIFEST未列在ad2de216该目录Git tree中；本次可核的是本机原ZIP与Git已发布的身份索引，不能宣称ZIP本体已随这六文件进入Git。

只读Python标准库解压到内存核CRC及成员SHA（未调用候选代码或功能测试）：129成员CRC全通过，MANIFEST列明128成员的字节数/SHA全部匹配；第129成员为MANIFEST本体，包内与本机文件字节相等，SHA `9902e0801b06bc977783ec98f73b1455a1cd143d6cf8ad8f0ce04ef9f732a005`。未向磁盘解包或覆盖任何原件。

包内 `ROUND_01/NIGHT_RUN_RECEIPT.json` 原始SHA为 `e222e545b87fa865263ddf066ef46d236ac93d53bfb1a5b79a67a0305c24bdee`，与根目录汇总收据是不同文件。原收据passed=true、1轮、100.28199999999924秒；compile/positive退出0，negative_1..4退出1。原stdout含487条CHECK、82条EVENT、10条SCORE及最终PASS；摘要events/scores为0来自末次共同reset，不是没有刺激。原DELIVERY/RESULT的未提交未推送描述属于子窗口封存时点；上述源码/摘要现已由ad2de216发布，历史原件不回填。

## 2. 实际工具身份

旧记录为Python3.12.4、Icarus/VVP14.0 devel；版本来自原封存双流，本次不启动版本/预检/仿真命令。现存三个EXE的字节数与SHA实核均等于ROUND_01/before.tools：

| 文件 | 字节 | SHA-256 |
|---|---:|---|
| C:/Users/songdongkuan/miniconda3/python.exe | 104208 | `4e5a83fcdcd12bcb9ae4dc98c5405effe35dc5ac10d89982c6a6a3646493f88a` |
| E:/FPGA/GAOYUNFPGA/138K/tools/icarus_oss_copy/bin/iverilog.exe | 457576 | `5c1f4e38c6dc0807aeab8814d63af97313bef5813e815e17021ae8e36e0a0bab` |
| E:/FPGA/GAOYUNFPGA/138K/tools/icarus_oss_copy/bin/vvp.exe | 325265 | `d38cc76e6946136aaf46db8a3bf34bec2a54bad564dfe146686579ca2d39c9ed` |

原EXE/DLL/Python依赖前后清单、argv/cwd/起止/双流/退出在包内保留；本次没有重新哈希整个安装树或执行环境准入。已签工具身份不产生新仿真许可或新Pro商业许可。

## 3. 对照本次E1完成条件的复用表

| 新单E1条件 | 已有可复用证据 | 必须保持的限制 |
|---|---|---|
| 默认640×480、八槽、preview120 | 默认参数；上飘八槽、下落140帧×8槽整数几何及第141帧退出；原坐标后处理原件在ZIP | 下落八槽同hit/duration、不同note/id，不冒称任意曲谱时间安排黄金 |
| 显示FIFO32/满空 | 32排队+1在途mailbox，33条有序drain、第34条溢出/drop1、desync与reset恢复 | 八个画面槽不等于八深事件队列；生产不得静默缩到8 |
| 模式/CDC入口/复位 | mode valid/ready、两toggle奇偶、frame边界及同沿旧mode/下帧生效；score98位背压稳定、8槽+第9mailbox/第10源保持；在途共同reset无ghost | 只验证合成TB生产者及逻辑CDC，未签物理payload路径/所有异步相位 |
| 上飘按/松、下落移动/退出 | 按下增长、松键快照旧end480/下次476、退出；下落连续几何/退槽与未来隐藏 | 旧命中闪光FAIL仍暂缓；flash固定0未修未验 |
| 音频不被显示回压及负例 | 实际pcm_frame_buffer+i2s_tx、诊断PCM；显示队列满/暂停时frame和commit前进、underflow0；错误门控calc_ready被拒 | 非M1/R05算法、非PCM→串行逐样本黄金、非新Pro同版整机 |
| 扫描节奏 | 800×525/25MHz三raster、两420000周期区间、921600活动像素、消隐黑；音频帧833/834 | 长运动窗使用加速frame_start；没有真实TMDS/实屏/色彩像素签收 |
| 四真实RTL坏例 | 错接源mode脉冲→MODE_CDC_DELIVERY；屏蔽接受事件→EVENT_LOSS；mode固定→MODE_SWITCH_STALL；显示暂停门控音频→AUDIO_DISPLAY_BACKPRESSURE | 各为真实VVP mutation运行exit1、首断点对应；不能把工具失败或改日志当坏例 |

上述功能、原487检查、四mutation、原几何后处理和旧99项均**不应因第二任务重新运行**。E1本次无需另造wrapper、FIFO、CDC桥或显示实现；不应为用尽六轮新增无目标测试。新发现的具体缺陷或正式同版来源到件才构成后续定向增量依据。

## 4. 完整E1仍缺的精确输入与责任

本次Test-Path确认M2新Pro目录 `code/rtl/board/m2_138k_pro_fourvoice_candidate_20261016/`、对应constraints/build/docs-test均不存在；旧 `formal_geometry_successor_20261016/` RTL本体亦未到。现有M2 L0接入合同为 `code/docs/M2_双滑块同版接入边界与待定生产者_2026-10-16.md`，原SHA `06abb92e16e00ecaa5ee15e858897611cda8480c2d1015024f14970fdde41244`，它引用旧138K C输入，不能替代Pro工程。

1. **M2新Pro身份与接线**：完整FPG676器件/步进、精确top/source/ROM/IP/工具清单、四声与前项双音色真实同版出口、唯一音频事件接受点。accepted_valid须来自shared_event_valid&&shared_event_ready；显示ready不得进入音频接受路径。
2. **mode正式生产者**：经批准的实际按键/协议来源、去抖、valid保持至ready、每操作一次接受。现有SOURCE_MODE/诊断自动切换不能充作用户模式控制；不私定新引脚。
3. **score正式生产者**：真实曲谱入口、note_id生命期、98位payload、帧零点/复位epoch及时间映射；40MHz读25MHz current_frame须独立CDC合同，不能照TB直接采多位计数。需说明未来/迟到score和同帧行为。
4. **时钟、复位和视频出口**：Pro实际40/25/125MHz PLL、共同失锁/复位断言与各域释放、唯一扫描/RGB寄存/TMDS链；诊断display_event_enable生产拟系1，由M2固定同版接线。
5. **完整物理与准入**：新网表七个控制异步首级及二级逐实例命中，64/98/1位bundled payload路径约束/保持检查，完整setup/hold及clock/reset覆盖；正式CST/Bank、完整STA、唯一 `.fs` 与恢复SHA和本次下载许可归M2。旧STA或旧PG484码流不复用为Pro通过。
6. **M3同版实物原件**：上述精确Pro版本准入后，板型/电气/设备及实屏按松动作、下落/切换/reset、同版音画共存原件；当前无板/仪器，不编造实屏或恢复旧SRAM额度。

最小后续动作是保留本轮E1复用结论，等待M2上述身份/生产者/接线合同与正式准入，再由M3采同版实屏和音画原件；目前没有在现有E1写集内必须新增的代码修法。旧闪光FAIL按新单继续保留，不能将“连续下落显示”写成“下落完整交互通过”。

本报告自身仅L0，引用既有L2不升级；`E1_new_tests=0`，`E1_full_feature=PARTIAL`，`board_release_allowed=false`。本文件未提交/未推送；由总控统一封存发布。真人M2交接仍待用户转发，尚未送达。
