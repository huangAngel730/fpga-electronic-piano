# B2M：原 B2K 在途取消与复位后的 PCM 独立重算

M3，2026-10-11。D043/D044 同一候选的软件后续阶段，仅新增 B 授权路径。
不改原 RTL、TB、ROM、捕获、旧 checker 或八处共享文件。
T060 原捕获的剩余观测缺口仍等待 M2 决定，不能以本阶段替代。

## 输入与期望独立性

原 B2K 已获 V0280 限定取消／排空功能签收，明确未重算 PCM。本阶段从其原封存恢复
N4/R1、N32/R1、N32/R64 三组完整连续 PRE-NBA 捕获，不重新运行 RTL。
原 ZIP SHA 为 `ce06a926ce1bc8d3618f361a4aaafec0fd6b010235c04e8a8d8e060f45a21bde`；
载体 SHA 为 `119ddda5956a37f376b5644bf254c4529ae425e0974c9a6b6d11ebc42f46e836`。
先核全部成员、CRC、原执行收据、执行源／冻结 ROM 与当前只读原件身份，再恢复正例。
生成 TB／observer 已有明确来源，不要求重复材料或重新生成。

复用原 B2K 源码日历 checker 核语法、输入握手、取消排空与 phase/FCW 时点；
数学期望另由 `b2m_check.py` 生成，**不从捕获的 phase、FCW、PCM 取期望**：

1. 接受的 A4 NoteOn 进入已有独立 Router 参考，按注册输出延迟产生 note_on。
2. 持续运行原独立 Envelope 定点模型，包含时钟 ROM、乘法与 Attack 准备状态。
   DDS 从独立 note FCW 推进相位、亮度攻击窗和表选择。
3. backend launch、ADVANCE、SETTLE、ROM_START、GAIN 均按独立日历预测，
   不以捕获的 advance/lane_valid 作为数学模型触发器。
4. SETTLE 在接受后第 13 拍保存 pre-NBA 包络；第 `14+s(R+3)` 拍读波表，
   第 `15+R+s(R+3)` 拍计算 signed 乘积、算术右移、16 位结果再左移 8 位。
   全 N 槽算完才饱和到左右 PCM24，逐个首次 valid、HOLD 及发布沿核验。
5. cancel 抑制同沿新工作并丢弃事务／输出，不回滚已发生的 DDS／ADSR 推进。
   只有真实全域 reset 清除数学状态；原捕获的复位恢复也逐帧验证。

只读复用 `dds_model.py`、`envelope_model.py`、`b2c_router_model.py` 与 `b2_clock.py`，
不是另创声音算法；参考源及原 ROM 与运行日志一并绑定 SHA。
软件内部算出的逐槽值不是原捕获中未记录字段的观测证明。

## 验证方式

新 runner 总上限 300 秒／单步 90 秒、全新输出目录、失败非零。
三正常组各 21 次发布，包含取消后立即恢复与四次在途复位后的恢复。
最终真实流程 `code/output/m3_t061_b2m_pcm_20261011_01/receipt.json` 退出 0，
96.640 秒，16 步骤。三组各核验 21 次首次 valid、21 次发布和 63 个 valid/HOLD 沿；
合计 63 次发布／189 个 valid 沿，全部非零 PCM 与独立期望一致。
三组软件内部逐槽渲染数分别 87／675／675，包含取消前已计算的部分槽；
它们不是未记录逐槽 wave/envelope/PCM 字段的观测次数。
详细实际计数、退出码和逐条 PCM 见封存 `receipt.json` 与 profile JSON。

12 项软件自检包含正常原件、不修改输入、左右 1 LSB、正负算术右移边界、全域复位、
错误包络推进／波表／增益／DDS 软件行为变异和缺 END／非法参数拒收。
这些是软件变异，不是新增编译 RTL 行为反例。

六个完整反例保持原输入、时点、phase、FCW、CASE 和 END，只将某个请求全部 valid
沿的 PCM 一致修改：双声道 1 LSB、左 1 LSB、右 1 LSB、清零、反号、增益错 256。
特意保持 HOLD 自洽；原 B2K 时间 checker 必须仍退出 0，新数学 checker 必须
退出 1 且命中 `B2M_PCM`，不以格式损坏或超时代替数学拒收。

复现（仓库根目录，用现有 Python）：

```text
python -B -X utf8 code/software/polyphony_scaling_candidate/b2m_run.py --output code/output/new_b2m_run
python -B -X utf8 code/software/polyphony_scaling_candidate/b2m_check.py --input code/output/new_b2m_run/N4_R1.capture
```

## 验证等级与未验

本次新执行是离线软件 L1／原 RTL 捕获的限定数学 L3 补核，不是新 RTL 仿真 L2，
不能升级为物理 L4/L5。旧 B2K 功能 L2 不被改写为本轮重新仿真。
精确原夹具只有单个 A4 占用，其余 N-1 槽静音；不是 N32 同时演奏。
控制为零 bend／零 modulation，LFO 虽按源码跟踪，但本场景不能证明其完整非回滚；
没有新增完整包络生命周期、负波形舍入、饱和、任意事件交错或通用服务界覆盖。
旧 N32 饱和及指定长程签收继续按各自原范围保留，不混用证据。
R64 仅用于响应排空数学，不准入 833 拍 deadline。

T060/T061 保持 PARTIAL。B2L 仍待 M2 专项复核，N32/R1 资源工程与 N8 备选、正式
架构／接入／资源映射／新整机 STA 由 M2 负责；本阶段不新增综合或 PnR 额度。
旧 RAM 不重启，新 RAM 仍仅使用 5e1d13c 的既有签收边界，不用于本声音候选物理证明。
无设备、下载、烧录、安装、串口或接线操作。
按任务单禁止改共享表，由 M2 统一登记。本阶段发布／远端身份见外层 GIT_DELIVERY；
封存时状态不回填，通知待用户转发，尚未送达。
