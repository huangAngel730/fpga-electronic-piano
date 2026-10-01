# 音色研究参考模型

piano_v1_legacy_model.py为M3隔离V1参考原件，只有通用概念验证：平方根近似力度、简化包络、音体切表按音符年龄。因此不作为正式velocity_gain_rom/ADSR/相位回绕切表的逐样本金标准，不覆盖正式模型。

正式V1对照命令：python -X utf8 code/scripts/run_piano_v1_audio_core.py。它使用原PianoADSREnvelope/冻结力度ROM（逐值校验）与真实V1状态机/波表，比较真实四路输出。V2研究仅通过此参考进行相对比较，不能把研究报告扩大为正式音频误差结论。
