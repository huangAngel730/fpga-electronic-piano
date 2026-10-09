# T058 retained_payload_v2

本版本只新增waveform mailbox源payload的GSC syn_preserve，原59输入字节不变，60inputs/51projectentries。三个新prepare/check/once入口和24项预检保留全部旧门禁，拒overwrite、不自动重试、1800秒上限、无program。

2026-10-08一次Gowin393.451s/exit0完成综合→PnR→STA→bitstream，但check入口1：Recovery−3.738/-1.309（4端点）、Hold−0.011（1端点），普通Setup+1.846/Removal+0.002，无法签L5。payload56实际路径已存在，10ns/maxdelay最差+8.5ns，原TA2003不再出现。RAM实际audio20+wave3+observer0BSRAM/28SSRAM，23总BSRAM，不满足v2构建前预声明observer2or3；旧门禁不为追認通过改值。

原九功能仿真因RTL无变化仅核身份复用；没有本次新RTL仿真。新STA资源Logic20242/Register9109/DSP46/BSRAM23，仅此run有效。文件/原log/失败gate/完整report原SHA封存；.fs只存在ignoredbuild，不是允许下载版本。后续修复另明确版本/资源和复位/短路径影响，不覆盖本次结果。

准备新副本：`python -B -X utf8 code/scripts/prepare_138k_waveform_integration_v2.py --output code/build/138k_waveform/<NEW>`。
预检：`python -B -X utf8 code/scripts/test_138k_waveform_integration_v2.py --output code/build/138k_waveform/<NEW_TEST>`。
一次构建入口`run_138k_waveform_integration_once_v2.py`必须有全部九场景原SHA，拒旧目录。此版本结果已知失败，不要直接重复Gowin。
只读验本次拒收：`python -B -X utf8 code/scripts/check_138k_waveform_integration_build_v2.py code/build/138k_waveform/runs/run_20261008_payload_preserve_v2`，预期exit1。

详见code/docs/M2_T058_payload保留版_构建与STA复核_2026-10-09.md。本次未改公共接口/生产/M3源/原L/ROM/PLL/CST/SDC，board_release_allowed=false。
