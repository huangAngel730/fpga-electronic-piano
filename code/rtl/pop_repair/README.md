# 拍频听感研究候选（V2保留，V1已提取）

2026-10-01，用户确认M1/M3协作范围已转发，M2按方案整理。此目录现在只保留V2研究源码/模型/表/TB，不进入正式Gowin工程。

V1已原样提取至code/rtl/audio/piano_dds_oscillator.sv、code/model/piano_wavetable_gen.py、code/model/generated/wavetables/piano_band_4x256_8191.mem、code/tb/audio/tb_piano_dds_oscillator.sv。旧简化包络/平方根力度模型只留code/model/research/piano_v1_legacy_model.py，不充当正式黄金模型。

原3515c31目录187个追踪文件完整归档到忽略目录code/output/v1_formal_integration_20261001/pop_repair_original_3515c31_20261001.zip，SHA256 2a7b3a58be0e8b8e71b726843c07688f6ad890ee87807dd97d617b8fe306d24c，每一移除文件均与归档原件匹配。Git历史3515c31保留；原.fs/实物录音如果只在M3电脑，须由M3保留，本次不删除未收到原件。

已移除追踪树里的旧build/source、build_v2/source、工具exe/obj、原始ZIP以及已提取V1的重复源码。V2仍是研究候选，不能拿其旧54774f1顶层、约束或报告覆盖最新正式音色/延音工程；正式资源/时序/新码流见M2集成报告。

V2源文件保留原目录及模型相互导入路径；未补做V2动态/新基线Gowin，未将用户对V1的偏好扩大为V2优越结论。运行研究脚本只在本目录工作，生成输出必须留output/，严禁再提交完整厂商构建树。
