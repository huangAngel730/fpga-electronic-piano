# 精确新版缓存RAM/MIDI/Hold夜间组合工程

工程只读基线：5e1d13c两RAM源、5960d37c...e4d949c独立同沿MIDI候选、原L-v3声画/ROM/PLL/CST和原严格SDC加一条精确Holdmin_delay0.100及两report。prepare生成62输入53项新目录、规范字节冻结收据、执行源SHA绑定，旧目录不覆盖。

2026-10-11已实际完成新组合13UART/3行为反例以及唯一完整Gowin；独立MIDI参考避免共用修改parser。最终全板级门禁只精确允许MIDI23→20SSRAM映射变化，原首次资源拒收/源/报告保留；详细实证和限定离线L5见`M2_夜间新组合整机收口_2026-10-11.md`。不复制模块STA代整机、不回填旧收据、不关闭实物或下载。

复现顺序：prepare_138k_night_cache_combo.py新目录→run_138k_night_cache_combo_sim.py正例及audio/video/response_command三负例→run_138k_night_cache_combo_once.py绑定四份新收据/上限1800秒→首次原gate及独立check_138k_night_cache_combo_final.py（仅精确资源分类）。最终已有结果不重跑或覆盖；若要重新构建另需实际范围与独立新证据，不自动重试。
