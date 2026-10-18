# member3：R02更正与最小接合适配

**最新结论：R10只有prepare、未接D4 PROCESS_CAPTURE是M3整链接合遗漏，不能归给M2。已按总控追加派工提供唯一新application_adapter.py；静态READY，尚未执行验收。**

原RESULT.json保留。“入口仅有意挂起、不构成代码遗漏/当前没有可实现项”的判断由本R02更正；旧例去重、真实材料缺口和不恢复额度的结论不变。

## 已提供的最小修法

- [application_adapter.py](E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017/capture_link_r01/application_adapter.py)只导出build_application(request,out)，固定SHA委托既有R10 admission/adapter.py。
- 根控在新的D4式module_bindings中仅替换application descriptor，写其它新capture_link接续文件。旧D4 chain/common/assembler和冻结文件均未改。
- 输出限R10 output严格子目录；不改旧模块/cache，保留原report shape，执行/真实/板测权限恒false。
- 只读子智能体未发现本文件具体阻断；成员未导入、编译、自测、Git或网络。

由根控封首个具体LINK缺陷，决定并唯一消费现有<=60秒定向增量，只验新接缝，不重跑旧7、D4 114或H54。成员未消费或新增额度。

## 去重和剩余依赖

| 范围 | 已有实际结果 |
| --- | --- |
| D4 | 75旧+39新=114匹配；初组1、修复3已消费 |
| R10原LINK | 7匹配，exit0，9.391秒 |
| 备用19..24 | H54匹配，exit0，1.734秒，分别6/9/9/13/8/9例；14个当前文件同H收据 |

M2 finish相位、可信执行/动态依赖/真实HDL许可，M1独立数学实件，实际raw/结束双流，audio_stable/背压决策及物理原件仍缺。新adapter只补M3代码接合，不伪造这些依赖。

H21只验归一化设置/校准身份声明，H22只消费event_evidence，不代表已解析实际设置/WAV。真实格式/校准/阈值/共同时间基准到件后，由原写者按实际范围和许可接入，不借本次LINK增量扩H组。

## 报告入口

- [最新机读RESULT_R02](E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017/intake_20261018/member3/RESULT_R02.json)
- [原核对、15项证据SHA、H和R10逐文件身份比对](E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017/intake_20261018/member3/RESULT.json)

原START北京10-17 21:52，截止10-18 02:52，已有Goal不重开。未提交/推送，由夜间1统一验收发布；真实数字/数学/板测仍PARTIAL。
