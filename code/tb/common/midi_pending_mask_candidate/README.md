# M2一次隔离试验：直接授权掩码与pending并行更新

本轮仅候选，正式M3 parser未改。基线de68038 raw SHA834887a9…331c6。
保持原第一/第二排名、payload和RR更新，新增组合one-hot候选并旋转回绝对槽；每个pending bit按解析更新优先、同槽已grant则清除，原parsed优先规则不变。
pending寄存器只有复位与无条件vector next-state赋值，不添加寄存器、流水拍或容量。

运行：python -X utf8 code/scripts/run_midi_pending_mask_candidate.py --output code/output/<new>
参考从de68038原字节Git读取，完整DUT四配置含burst16与冻版逐拍对照；实际原组合切片+独立Python线性参考比较mask/grant/pending_next，并编译后拒绝错同拍清除负例。

只有功能逐拍等价、同条件Gowin Setup≥+.5ns、额外Logic≤128且无任何新时序/CDC/引脚违例才考虑采用。否则保留de68038。实际证据完成后写报告；此文件不代表已测PASS。
本目录不能进入正式GPRJ或烧录，candidate_NOT_APPLIED.patch尚未应用。M3正式变更须用户私发交接，M2不直接覆盖M3负责文件。

补丁采用零上下文格式，以 `git apply --check --unidiff-zero` 预检；仅历史/隔离交付，本轮未正式应用。此格式避免补丁自身空白上下文触发仓库尾随空白门禁，不改变RTL。
