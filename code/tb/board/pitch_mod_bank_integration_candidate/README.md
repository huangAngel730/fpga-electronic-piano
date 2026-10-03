# 四声部实际银行Pitch/Mod接入候选（M2）

**仅隔离工程，功能L2/L3和综合L4完成；最新音画STA失败，L5未通过，禁止烧录。**
生产bank/router不改，formal_integration_NOT_APPLIED.patch未应用；router只导出已注册来源/通道/代次，正式接口变化需群通知。
外部bank/PCM接口不变，使用已审ADSR流水与6/4等待，不改包络曲线/时间/幅度。
成功演奏事件同时交router/control RAM；采样前冻结身份/base，四读快照后算FCW，验tag才同时推进DDS/ADSR。
frame_tick取消并排空，暂存帧缓冲下一拍请求；不复位已接受控制/LFO不回滚。闲槽DDS保留base相位生命周期。

复跑：`python -X utf8 code/scripts/run_pitch_mod_bank_integration_candidate.py --output code/output/pitch_mod_bank_newrun`。
实际502188银行检查、1886消费、4353非零控制Python匹配；784无控制样本对已审ADSR流水银行参考匹配，两个行为mutant拒收；真实V1/CC64/PCM560帧无欠载/Q15混音精确，最长30clk。
不宣称与旧未流水化ADSR逐周期相同，也不宣称端到端模拟延迟。

组合准备：`prepare_pitch_mod_bank_combo.py --output <new> --frozen-project <V0161 gprj>`；报告门禁`check_pitch_mod_bank_combo.py <physicaldir>`。
实际音画综合/PnR工具完成但Setup430/Hold2770端点失败：系统Setup−7.872/Hold−.390/Recovery−.334；资源19711Logic8671Reg46DSP20BSRAM。
当前Setup瓶颈是M3最新parser32槽本拍更新选择；M2控制tag短路径和Recovery也失败，均待同版修复，不屏蔽。
V1/CC64/PCM实现只读复用，不接T028或Program音色映射，不改正式top/CST/SDC或M3解析器。
详见code/docs/Pitch_Mod实际四声部接入候选_功能与音画STA复核_2026-10-03.md。
