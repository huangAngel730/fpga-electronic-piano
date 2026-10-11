# B2i：实际混合候选的源码预算与周期准入账本

本阶段承接 D043/D044 允许的源码状态／资源／运算日历工作。只新增软件、测试、交付脚本和文档；不改 RTL／ROM／TB／旧封存／共享表，不运行新 RTL 或 Gowin。N32 完整长夹具已在 52ad3dc 交付，本轮不重复。

## 可运行实现

- `code/software/polyphony_scaling_candidate/b2i_audit.py`：绑定已推送 52ad3dc 的功能源与 ROM，按当前真实 N 参数扫描、核对 10 模块／180 个 NBA 载荷目标，生成同一对象 JSON／Markdown。
- `test_b2i.py`：12 项软件测试，包括所有四档字段、全部 256 N/R 日历、身份／双银行／叶模块副本、未知传播、833 边界、坏类型／表达式、漏字段及位宽变异可见性。
- `b2i_run.py` 和统一 runner `--stage b2i`：默认步骤 900 秒、流程 1800 秒，拒覆盖，原命令／stdout／stderr／退出码和输入前后身份绑定。B2h 的独立延时授权没有扩展到 B2i。

命令（仓库根目录，使用已有 Python）：

```text
python -B -X utf8 code/scripts/run_m3_polyphony_scaling_acceptance.py --stage b2i --output code/output/全新目录
python -B -X utf8 -m unittest discover -s code/software/polyphony_scaling_candidate -p test_b2i.py -v
```

## 账本口径

现候选为 N 份连续 ADSR／PitchMod＋单共享 piano ROM／有符号增益／串行 signed32 混音；B1 上下文实际 CW=74，不是早期 635-bit 软件／fixture 工作域。旧 B0 预算及其 21 拍单声部合同只保留历史解析比较，不能当现实现的测量值。

字段扫描器只服务精确源，不是通用 SV elaborator。安全 AST 计算声明范围，人工审定的 NBA 字段集合必须完全匹配；`if (...) <= ...` 比较不作为赋值。寄存输出、重复快照、未使用的声明状态全部保留；排除 wire、组合临时量、循环变量、ROM 和仅 initial 使用的 `sub_source`。声明位数是**源级载荷**，不是物理 FF 下界或映射结果。工具可能去掉死状态、合并或复制内存。字段含行号、SHA、宽度、份数及生命周期，256 身份／32-bit generation 不压缩。

运行 ROM 为单份 piano、N 份 velocity/oct/sub/LFO，总 bit=16384+54248N。`sub_source` 的 20480N bit 初始化置换暂存单列，不双算运行 ROM；note_pitch 为 12 项半音 case 和八度移位，另列组合逻辑，不假造 128 项 RAM。源级乘法表达式为 8N+1，其中含常数乘、各自位宽／舍入由精确源固定；绝不等同 DSP 块数。

空闲路由假设下，从 J 接受到 C 接受 `12+6N` 拍；C 到首次 wrapper F 为 `16+N(R+3)` 拍；F−J=`28+N(R+9)`。原 capture 报告 min/max 是 age=F−J−1，833 判断用 age。本轮明确命名，不修改旧报告。Pitch 输入 II=1、E+6 NBA／E+7 消费，逐槽渲染 II=R+3；不得冒充整帧 II 或整机 deadline。

router 清空等待、首次结果后的输出握手、归还 idle、完整事件服务最坏界、无条件 ABA 排除、生产持续演奏均 UNKNOWN。输出背压可无限，取消保留 DSP／LFO 非回滚副作用；排空仍只原实际工作域证明，不由本预算升级。

## 原证据的使用方式

核验 B2D/E/F/H 原 Git 载体、archive SHA、选中 report／receipt 成员 SHA、receipt 输出绑定及功能源 LF SHA，引用 12 份报告。核对源码空闲日历与每份报告 min-age 一致，保留 R64／R16／R32 的真实晚到失败；**没有新音频重算或 RTL 仿真**。

容量仅源自 B0 已封存的原工具报告：Logic 138240（不是纯 LUT）、Register 139095、DSP 298、BSRAM 340 blocks（不是 KiB），SSRAM capacity unknown。该报告 ignored，按 B0 封存成员 SHA 绑定，不要求虚构 Git blob。报告中旧整机 used 不当作当前候选开销或剩余额度。

## 验证与后续边界

本轮只 L0 源码审计／L1 软件自检；原限定 L2/L3 交付保持原等级。当前候选物理 Logic／FF／DSP／BSRAM／SSRAM、复制／打包、40MHz STA 全 UNKNOWN。正式架构／接入档位／资源准入／代表综合配置和额度／新整机 STA 由 M2 决定。未使用综合额度，不自行追加综合。完整 T060/T061 不关闭。

任务单禁止改共享表，本轮状态／登记建议仅放交接文档，由 M2 统一处理。通知待用户转发，尚未送达。
