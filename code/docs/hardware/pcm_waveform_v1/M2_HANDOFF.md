# 给M2：T058独立候选交接

T058完整像素域候选已交，按D038/D039仅新增四处，原L/ROM及生产文件和共享登记不改。
入口pcm_waveform_candidate为25MHz单域、无ready、三银行/2048包/4点signed min-max、
固定x64..575/y64..319、左声道、2拍RGB/mask、仅frame_start发布快照。
restart保留累计诊断计数并清所有流有效元数据；pixel reset清计数；细节见RTL README。

真实正例4,033,936检查/8全帧/5849正常A+41诊断A/零像素状态错误；两个完整编译运行行为
变异按特定语义非零拒收，五损坏capture拒收。47份原证据Base64/raw SHA和真实命令齐套。
一次独立Gowin综合C版25MHz合同通过：375Logic/196Register/3BSRAM，DSP unknown；
无PnR/.fs/STA/下载。RTL SHA052c4e79095152410bdd42e4d5c3cd47a00b91ad7bdf848a3c0914ab9aec0160。

请独立复核本提交与原证据。后续观测pre-NBA帧装载、80bit CDC、复位重同步、原动画合成、
RGB/HS/VS/DE对齐、正式工程/完整整机STA/音频无扰动仍由M2完成，勿沿用旧L结论。
T059随后独立推进，不混入T058提交。源/文件清单和门禁日志随交付，仓库九项实际全PASS。

待用户转发，尚未送达。实际提交号由用户转发时附上；本文件不声称已通知或已正式接入。
