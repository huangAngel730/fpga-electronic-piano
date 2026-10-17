# M1 第17批：Pro 四声基础软件准备

本批 A0/A1/B0 的离线软件交付齐套。实际范围为 **L0 来源／软件合成准备**；Pro 实际数学比对仍 `PENDING_REAL_CAPTURE`。尚未同步最新远端，本批未暂存、未提交、未推送；未执行本批精确树仓库九项门禁，旧 PASS 不移签。

- [任务原件](TASK_RECEIVED.md) 与 [实际执行边界](EXECUTION_PLAN.md)。
- [A0 来源和 Pro 缺件](A0/SOURCE_FREEZE.md)：73 个既有文件、32 个 R06 归档成员身份闭合，七项冻结依赖及三 ROM 字节核同。
- [A1 增量判据](A1/README.md)：14 个新自检方法通过，五场景各256，共1280行。增加逐 lane 原始输入身份及混音／效果历史；复用既签算术，不重跑旧测试主入口。非零 clip 场景未覆盖；false→true 的错误 clip 作为拒收例。四独奏效果后相加在请求1为4476，真实合奏黄金为4479（均合成），不能相互替代。
- [B0 字段合同](B0/字段合同_B0.md)：先验全部身份，再做0 LSB比较；未发布／取消工作仍推进相应 DSP 和接受的效果历史。仅接已签 settled profile，拒收 stagger、同沿等未签调度。
- [B0 CLI 原件](B0/cli_R01/QUALIFICATION_RECEIPT.json)：四项退出0/1/2/3，分别为合成接受、1 LSB拒绝、身份先于PCM拒绝、伪装REAL仍待验；这些是修复前源码的过程记录，不冒充最终源码全重跑。
- [晨间交接文字](晨间回执_待用户转发.md) 与 `FINAL_RECEIPT.json`。所有运行命令、Python版本／EXE SHA、源码前后 SHA、原始双流和退出码在 `RUNS/`；Git 原件在 `SESSION/`。

B0 首轮30个新方法通过后，静态自审发现“缺公开PCM时跳过已交日历身份／计数”的具体缺陷，最小修复保留历史。最终生产源码 SHA `7213e9fdce5fcab4dd5828b282613def88e8f5d7566986e3af6b89ae9c899267` 上，修复轮32项通过；其后只新增的第33项可见计数／lane拒收方法单独通过，生产源码未变。没有将两个测试文件版本冒称为最终33项单次全跑。

A0 初次冻结外层 stdout/stderr 未单独保存，原执行收据／退出码和工具回显仍保留；最终独立静态核验重核其73份源和32成员，使用统一运行器保存原双流，不覆盖初次冻结。

复现时在仓库根目录运行本目录 `RUNS/*/RECEIPT.json` 中的 Python argv，输出必须换新目录。新目录下的 `capture_run.py` 可保存命令原双流；不为复现本批软件准备运行旧 `test_oracle.py`、旧13/50组或旧303项重算。

Pro top/source/ROM角色映射、端口/复位、异步 RESET_EDGES、M3独立应用/slot/全部lane_tick/取消/FX配置接受日历和同次公开PCM原件仍缺。M3继续主责日历、串行和期限，M2负责Pro集成与最终限定复核。本批不启动ModelSim、Gowin、PnR、STA、板测、双滑块、波形、传谱、T052或N32；`board_release_allowed=false`。
