# 精确 RAM 整机隔离自检

M2 T062 后续正式接入准备范围。被测源只来自 `prepare_138k_score_bram_integration.py` v2 核验的 62 输入／53 项工程，原 CRC 流水／RAM 候选不改。所有 Icarus 语言兼容处理和错误实现仅生成在新的 `code/output/` 副本，原源与 ROM 保持；每步有限时且拒覆盖。

正例沿用原已验 13 场景独立协议向量，真实串行上传／序列错／COMMIT 原子切换／丢 ACK 重试／READ／CRC 错／ABORT／共享复位／STATUS，同时参考原无 score 接收器的冻结 v3 top，逐拍比较 PCM／提交／事件／状态／I2S，逐像素比较同步与 RGB、波形 valid／seq／左右样本／restart。新 TB 另检查共享复位后 score 元数据清零。名义 PLL 与 DVI stub 用于功能验证，不证明真实 LOCK、MTBF、TMDS 眼图、完整新整机 STA 或外部电平。

入口 `code/scripts/run_138k_score_bram_integration_sim.py`，`--project` 指向新 v2 准备工程，`--output` 必须全新 ASCII 目录；有效`--negative`使用 audio_isolation／response_command，视频使用下述独立入口。回复错例真实 checker 进程必须非零且指定诊断匹配；音频／视频错例真实编译成功并由指定比较断言退出 1。runner 在已知错误被正确拒收时返回 0，含义是反例测试通过，不是错误设计通过。

`test_checker.py` 仅合成 capture 的解析防假绿测试，不能代替真实 RTL capture；`test_prepare.py` 只验证工程准备身份。真实执行结果另记报告／收据。本短例只上传两个事件，不覆盖完整 512 容量／所有复位相位／长时间运行；既有模块专项证据与本精确整机证据分别绑定源和日志。

视频反例必须使用`run_138k_score_bram_video_negative.py --project ... --output ...`，该入口给参考 top 单独的未变异显示模块定义；原通用 runner 直接 video_isolation 会同时变异共享模块，不能作为有效负例。本轮已识别并停止04号无效尝试，日志/中断观察保留，未宣称通过；独立参考版另用新目录执行。正例的全部原源身份及既有运行不被此次反例适配改变。

2026-10-10实际正例通过：13场景/12回复/3事件，1962509音频及1226567像素比较，总868.283s，真实compile/sim/check均0；三个有效行为反例指定拒收。所有旧试验/输入保持，本精确工程实际到功能L2/限定L3，未跑新整机综合/PnR/STA。只读物理门禁完整继承原板级检查，缺报告拒收；合成XML自测不算实际L4/L5。
