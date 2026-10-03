# M2正式音频补丁路径预演（独立TB）

本TB只在output应用拟正式变更；原顶层端口与源码不改，例化实际electronic_piano_top、50MHz、31250/8N1物理字节，原frame_buffer/mixer/I2S。
拟变更的bank/router/已审ADSR流水与controlSnapshot/FCW管线按已验候选复制，不改音频数学或M3parser。

实际运行：18检查，546bank结果，337次调整FCW观测，468752非零PCM周期；验证中心base精确、UART Bend/CC1、CC64按/松、轻重触发、复位静音恢复，无意外underrun/clip。
层级FCW只作接线确认；独立逐样本算法验证已有V0164，不能把18项冒称完整音频验收。

输出GPRJ/replacement8文件/patchscope/lower/compile/run日志只在output/M2_mainline_handoff_20261003/production_patch_rehearsal，补丁文件formal_audio_integration_NOT_APPLIED.patch已git apply --check通过，未正式应用。
编译按rehearsal.gprj全部file.verilog、仅用既有Yosys降低原allocator给Icarus；Defs/SustainPkg先编，include sources/common，另加本TB；仿真使用现有V1wave和velocityROM，原件SHA列于证据。
此目录只保存可复现短TB，不新建第二套生产工程。正式应用先群通知模块私有接口及私发M1 ADSR范围；新正式GPRJ需要同版综合/STA，不能把V0171工具结果当本预演STA。

实际运行原TB字节、Git LF字节分别列证据，不重复已有长测试。未启用T028或Program音色，未烧录、未改CST/SDC。
