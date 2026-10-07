# T058旧验收器最小返修（2026-10-08）

按M2 V0214反馈和用户本轮授权，只修软件验收。原RTL、原TB、原L/ROM、原capture、
原编译/仿真/综合收据及原证据载体均保留。本轮没有新RTL仿真、Gowin、PnR或设备动作。
不改共享任务看板/当前状态，不关闭整个T058；等待M2复核。

## 修改与精确判定

- `reference.py`把原prepare中的定向计划提取为共用生成函数，原673932拍刺激不变。
- 固定旧TB SHA、两个原A流SHA和定向向量LF摘要；从固定计划独立重建R/T/V/I
  24357条完整记录，逐条校验类型、边沿周期、顺序、seq、左右PCM、restart与publish。
  不信任capture自报EXPECTED；正常5849包按原TB每500拍偏移200调度。
- 精确检查数为673932 + 1 + 8×800×525 + 3 = 4033936，不再只检查大于下限。
- 保留原独立像素行hash和状态反例拒收原因，不改变生产绘图语义。
- 新辅助run.py只通过原公开`--check-capture`入口离线重算，不调用Icarus/Gowin。
- 原verify_delivery区分历史执行源与新checker：旧reference按原SHA独立快照保留，
  新checker/执行命令/日志/收据另存；不改旧receipt的source_sha256。

## 实际结果

`m3_wave_checker_repair_20261008_a2`退出0，约30.813秒。
原正例：4033936检查、3360000完整扫描像素、4200行、正常5849/诊断41，错误0；
全部24357条公开刺激身份一致。两个原行为反例仍以PIXEL_REFERENCE和STATE_REFERENCE
各退出1，原编译0/完整仿真0只核其封存日志，不冒称本轮新仿真。

27种新损坏capture均完整通过公开CLI执行且退出1：END−1/+1/0/很大非零数、合法错
左右PCM/seq/周期/restart位、缺失/重复输入/复位/restart/publish、错publish/restart、
末尾输入缺失、末尾公开记录缺失、像素hash、帧数/计数及未知记录；空/截断也拒收。
不同拒收原因记录于新receipt，不以“任何异常退出”代替指定语义检查。

原第一轮辅助程序a1未PASS：损坏记录生成存在重复扫描的效率问题，且缺末尾V后先遇L
会按ROW_IDENTITY拒收，与测试预定的STIMULUS_COMPLETENESS不符。仅修新辅助程序，
第二轮用同时缺末尾V/对应L来验证完整性拒收；旧checker/RTL没有因此改动。a1日志保留。

## 复现与证据

```powershell
python -B -X utf8 code/tb/input/pcm_waveform_candidate/review_repair_20261008/run.py --output code/output/m3_wave_checker_repair_NEW
python -B -X utf8 code/scripts/run_m3_pcm_waveform_acceptance.py --check-capture <original_capture.txt>
python -B -X utf8 code/docs/hardware/pcm_waveform_v1/verify_delivery.py
```

本机使用现有bundled Python，路径：
`C:/Users/songdongkuan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`。
新evidence/raw_manifest封存原capture的重算副本、新损坏输入、stdout/stderr、原checker
快照及新receipt。FILE_LIST更新到本次版本，旧FILE_LIST/DELIVERY原件独立封存。
新源/原件SHA见清单及收据。仓库门禁结果另附gate原日志，不外推既有ROM报错已修复。

最终门禁`m3_score_ble_review_repair_20261008_gate2`：check_repo.ps1九项全PASS、exit0。
另对本轮7份Python执行AST语法检查通过；git diff --check通过。门禁子链既有
sine/triangle相对ROM readmemh ERROR原文另附child日志，不宣称音色问题已修复。

等级只增加离线验收器修复证据。实际CDC/HDMI接入、目标整机STA/实屏仍M2负责；
原单模块L4综合只是原证据保留，本轮不能写成新综合或整体T058已签收。
