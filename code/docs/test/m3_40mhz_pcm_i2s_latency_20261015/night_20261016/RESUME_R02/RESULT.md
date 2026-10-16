# C R02：真实R05主窗数字链限定通过

本轮已实际消费A R02成功原件，未只复用汇总或回复就绪。唯一合同差异为两条producer源路径，`STARTUP_SCHEMA.diff`及新schema SHA均核同；原字段/位宽/语义未变。C仅将R01入口原字节复制到新`RESUME_R02`，消费判据无修改。旧源码/旧86项/旧封包/已暂存文件均不改，C无EDA/硬件/Git写入。

输入：A成功receipt SHA`1516a35e6a5852164866aa729f8897ca5a668a4308f8e1ce60e91fa994211dbc`；capture SHA`a2509a2b5555437ff8ee1da4799e8210ad80e95a058881a5d26111a935e5b5d3`；inputs SHA`d001cac94d1520c42b43bcb33ca079c2f1d815c1205deb4a2d87005fe143038b`；boundary SHA`bbc78215e6c1f839a4d7789af93fc4d994c3ef6bab22c59448e2b9e710a5e8e7`。READY、源/ROM、固定工具命令/双流/消费/PREFLIGHT、stage、扁平执行源、输入时间线和所有主窗/侧车身份链接均由C实际只读核验。

## 独立实际结果

- 253456个连续主窗沿；初始epoch0及末尾epoch1复位记录。303接受、303提交、0开放请求；303均在各自下一真实frame_tick前提交，接受→commit均35拍，即0.875μs，不借DUT max替代账本。
- 304帧采样边界，303间隔为833拍202次、834拍101次，每三间隔2500拍。40MHz/48kHz分布成立。
- 606个完整WS半帧、302个完整立体声帧逐样本比较通过；包含首次reset零样本完整帧，301个已提交请求完整串行观察。严格WS低右高左、32槽末16有效、填充、BCLK/WS/DIN边沿与PCM24→PCM16舍入/饱和规则。最后ID302/303虽已按期提交/采样，但在串行完成前遇末尾RESET，明确单列，不冒称303组都完整串行。
- 已完整串行请求的请求→末位最大1673拍，即41.825μs；这是数字公开端口时间，绝非模拟输入→DAC起音≤10ms实测。6个公开演奏事件接受沿原样记录，另表只列与后续请求的时间顺序，不签可听起音或数学因果。
- 本次实际startup_edges=0，首绝对沿1、12500ps/13ns；原始侧车是header/end空前缀，未伪造X。startup依合同仍UNKNOWN_NOT_SIGNED；主窗连续性和后续X拒收不放宽。

正例`CONSUME_R01`实际exit0/8.094s；入口/依赖执行源本体、前后SHA、原双流及精确argv在其`RUN_RECEIPT.json`，逐笔/逐样本结果在`REAL_RESULT.json`。输出原字段level=L1独立消费者；结合已验证A真实ModelSim捕获，仅支持所述主窗的限定数字L2，不签整机功能/数学/物理。

## 损坏原件反例

`real_negative_R01`十个完整真实capture损坏衍生全部以实际Python CLI exit1及预期具体诊断拒收：漏沿、重沿、错序、X、错提交ID、错提交PCM、非下降沿DIN变化、有效位LSB串行损坏、首请求跨下一真实帧未提交、RESET后未观察低沿即END。此组整体exit0/23.5s；每例均保留完整损坏字节ZIP、编辑沿、原/新SHA、命令、双流、退出/耗时及拒收JSON。完整坏例仍用原V1格式，明确标损坏衍生，绝非新RTL执行。原capture前后SHA未变。

## 不能外推的边界

真实轨迹所有已提交左右PCM相同，因此本次**无法区分完整左右交换**；旧不等左右模块/软件边界证据保留但不重跑、不移作本次真实anti-swap覆盖。实际clip=0，数学clip及饱和端点覆盖不因此签收。末尾RESET低期间可见静音，末尾复位后释放/重新发声未在此轨迹观察。first-valid未导出；声部数学、真实PLL/HDMI、完整STA、模拟≤10ms与板级均未由C验证。`board_release_allowed=false`，基础整机任务不因此关闭。

自有子智能体仅只读窄审指定源码/合同/实际结果，未发现具体阻断，未运行程序或重读全部capture；主窗口的真实消费与十个损坏衍生已留原执行证据。审核员制度未启用。

封包`SEAL_R01/C_R02_REAL_R05_DIGITAL_EVIDENCE.zip`含本轮源码、原始A capture/inputs/侧车、源/ROM、原日志/成功receipt/消费链接、C正例与十个完整坏例本体。逐成员SHA/CRC见同目录MANIFEST/SEAL_RECEIPT，主回执`NIGHT_RUN_RECEIPT.json`。未提交、未推送，由夜间总控统一门禁发布及交M2限定复核；正式签收权限不变。
