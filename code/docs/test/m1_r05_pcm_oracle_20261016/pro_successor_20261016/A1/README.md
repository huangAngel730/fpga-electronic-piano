# A1 四独奏与四音同发增量软件判据

本目录仅承载 M2/17 夜间任务 A1 的**合成输入**与新增身份/历史自检。算法直接引用父目录的 `oracle.py`、`solo_chord_vectors.py`、`timbre_switch_pairs_R01.py` 及其 SHA 冻结依赖；不复制 DDS、ADSR、音色、混音或延迟算法，不运行历史 11/13 项等旧套组。旧五场景重生仅用于本次 A1 元数据增量夹具。

五个场景 `solo60`、`solo63`、`solo67`、`solo70`、`all4` 各独立复位，各 256 个采样（40 MHz、48 kHz、833/833/834 周期）。四音已在相同首个 DSP 采样前接受，**不代表前端事件同沿**。四个不同音高分别是 Note 60/63/67/70；音色、精确 FCW、力度、应用周期沿用已签合成模型。独奏 lane0 与合奏对应 lane 按原始身份匹配。

每个采样保留 phase/FCW、wave16、env_q15/level_q16、每 lane PCM24、饱和前四声部和、混音、左右 PCM24/clip，新增：

- 每个占用 lane 的 `input_identity={scene_id,source,channel,note,generation}`；空 lane 为 null。校验采用固定输入映射，先判身份再判数学，布尔值不能冒充整数世代。
- `mix_history` 保留四路贡献、和、饱和混音、clip 及操作顺序。
- 左右各自的 `effect_history` 保留接受序号、场景/请求、配置、读写指针、延迟来源请求、延迟样本、输入混音、输出与反馈写回样本、clip。

效果历史按各场景独立的**混音后** PCM 驱动未改动 T028 模型。`all4` 黄金直接由四路贡献先混音/饱和再效果得到；严禁把四个效果后独奏最终 PCM 相加当合奏黄金。资格报告保留已生成的反例见证，容差固定为 **0 LSB**。

14 个新增测试方法覆盖正例、原始身份每字段、空 lane、错 lane/音色/clip、左右各 1 LSB、混音历史、效果历史指针/来源/1 LSB、独立复位、错误相加、禁止升级 Pro 实证。错 clip 可用 false→true 拒收；合成报告实际计数之外不扩张覆盖，真实捕获非零 clip 始终未签。

在仓库根目录执行（由主窗口统一保留原始 stdout/stderr、退出码、命令与 SHA）：

```powershell
python -B -X utf8 code/model/m1_r05_pcm_oracle_20261016/pro_successor_20261016/test_a1_vectors.py
python -B -X utf8 code/model/m1_r05_pcm_oracle_20261016/pro_successor_20261016/a1_vectors.py --output code/docs/test/m1_r05_pcm_oracle_20261016/pro_successor_20261016/A1/generated_R01
```

输出只能创建在本 `A1` 目录的新子目录，拒绝覆盖原件。生成器写五场景 JSON/CSV、资格报告、依赖/源码/产物 SHA 清单。这里的命令为待执行命令，实际结果以主窗口封存的运行回执为准。

新 Pro top/源码清单 SHA、端口/复位合同、ROM 角色映射、同次独立日历与公开 PCM 捕获均未齐；继承 R06 源字节不能替代 Pro 同版核对。全部真实结果固定 `PENDING_REAL_CAPTURE`，等级限 L0 软件参考，不签 Pro RTL、PnR、STA、码流、上板或 `board_release_allowed`。
