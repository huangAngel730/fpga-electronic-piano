# A0：Pro 后继来源冻结（2026-10-16）

实际等级 **L0 来源／合同核对**；`real_result=PENDING_REAL_CAPTURE`，`board_release_allowed=false`。未提交、未推送。已签算法、ROM、向量仅按路径和字节引用，没有复制重写或重跑旧套件。

本机 HEAD `228879b6713188d71e1e97ae1170eaa53c523168`，缓存 `origin/develop=8b129dee4248e055d97d2910675f1c4b23473c96`。本轮开工 fetch 已受网络阻断，缓存不能证明最新远端。M2/17 新单明确 Pro FPG676；本机任务卡仍是旧 R06/PG484，记冲突，不猜新 Pro 卡内容。

直接复用 `code/model/m1_r05_pcm_oracle_20261016/oracle.py`（SHA `cb2cda8b6c9c17d7e5f93be4e48407383173934437c0592d2da64f778535d4a3`）及 `DEPENDENCIES.json` 所列四模型、三 ROM。七件预期 SHA 全核同；三 ROM 与原 R06 ZIP 成员逐字节相等。原 delay 候选目录当前缺失，但已签冻结副本字节齐全，其签收不因原路径缺失或历史变动失效。每件工作树 SHA、HEAD Git blob OID、blob SHA、版本相等性和归档内成员身份详见 `SOURCE_FREEZE.json`。

三 ROM 精确绑定：Piano `c117230f43c7efce36be445f851140d3155aa2a35e71ea8a41f529ea2b5d32a1`；Triangle `a6ee3195ad3a3310de5102531aac9d7773eebc6c31633d72c01b72a7d2461e3c`；velocity `1bc0fd4430884604224a20620368afa50805b4efbf57d9703cae7a09132ffe64`。载体原 R06 ZIP SHA `4be2b4c185691a3e493827a3a95303fa90f49ba6336eb4a8e0183942c8f05483`。这些是现有黄金的已证来源，尚未获 Pro 源树同版证明。

算术直接引用：32 位环绕 phase/FCW；Piano tick 后相位、Triangle tick 前相位；ADSR 逐时钟整数流水、Q16 level、signed33 delta/step、signed59 product；`voice24 = signed16((wave16*env_q15)>>15)<<8`，负数右移向负无穷取整；四路 signed32 求和后饱和到 signed24，严格超界才 clip；效果的两个 signed39 乘积各自右移15位，再 signed25 相加/饱和。效果历史按接受事务推进，接受后取消发布不回滚；enable/length 变更清历史。详见 JSON 的原件路径和规则引用，不新增算术定义。

已签 R02 四独奏＋合奏向量仍是五场各256行的 `SYNTHETIC_ONLY`（`code/docs/test/m1_r05_pcm_oracle_20261016/m2_13_solo_chord_R01/run_R02/vectors`）；source0/channel0、四个 note/FCW/velocity/timbre 仅绑定原合成/R06条件。四份经过效果的独奏 PCM 不能相加当合奏黄金。原 M1 A/R02 等级 L0 软件准备，R06 指定音频仿真 L2、旧 PG484 物理指定端点 L5，均保留原范围；Pro CST/原理图仅 L0。

| Pro 对象 | 状态 | 最小缺件／限制 |
| --- | --- | --- |
| 引脚/CST参考 | 已证实（L0） | `138K_Pro` 有PDF、202项CST与静态核对；不等实物Bank、器件或新top通过 |
| 最新任务卡 | 冲突 | 新单要求FPG676，本机卡仍R06/PG484；fetch失败，等待可核新卡 |
| Pro top端口／源ROM树 | 缺失 | 当前Pro目录没有SV/V/GPRJ/SDC；需完整part/top/PLL/reset及源ROM SHA |
| Pro复位／epoch | 缺失 | 需真实极性/同步释放/PLL保持和异步`RESET_EDGES(time_ps,rst_n,epoch)` |
| Pro真实trace | 缺失 | 当前仅旧R06合成schema；旧303重放不证Pro |
| 独立事件/slot/取消/效果日历 | 缺失 | M3已有字段提议及来源绑定，尚无同版真实应用沿、每lane_tick、FX/config接受取消完整输入 |
| 旧NEO/PG484迁移 | 冲突 | PA极性、引脚、PLL/复位/器件不同，旧码流与STA不能签Pro |

M3 现有 `code/software/m3_r05_functional_integration_20261015/real_trace_successor_20261016/contract.py` 的 schema 是 `R06_DERIVED_PRE_NBA_CALENDAR_PROPOSAL_V1`，只接受 `SYNTHETIC_CONTRACT_SELFTEST`，REAL一律拒收；已有 math、四lane、applications、cancellations、FX/config/result 字段，但其自身明确异步复位边沿仍缺。B0 应先验原始 scene/source/channel/note/generation，再按全部独立接受日历计算；不能从 DUT wave/env/phase 或 commit 汇总反推。真实 Pro 源/ROM SHA 和日历未齐，一律 `PENDING_REAL_CAPTURE`。

本包仅执行 Python 文件/ZIP SHA和只读 Git blob 核对，无模型导入、HDL/EDA、旧测试、联网或消息发送。可复现命令与双流／退出码见 `A0_RECEIPT.json`。需重新冻结时使用新目录，保留当前原件。
