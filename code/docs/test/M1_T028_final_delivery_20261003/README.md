# M1 T028独立模块最终交付（2026-10-03）

原ZIP df5bc32d3dba9e44229ddddabaab16d2c681c712b36adacab0469da65e3eff5d。
changes.json保留原交付raw SHA，仓库代码按.gitattributes落LF，两种SHA分别见received_sources.json，不直接把变换后的SHA改写成原SHA。
原五文件接收，不修改算法；验收仅独立模块、当前PCM24/Q0.15算术、E→E+2和launch间隔>=4，DEPTH16/1024。
module_acceptance_contract.json供现有M3验收入口调用，确认当前delay0读取一整DEPTH圈旧历史，**不是真正旁路或零延迟**。
模型process docstring一处旧“无延迟”与合同冲突，以原M1合同3.6及独立RTL/整数参考结果为准；这是非阻断的旧注释，不要求M1重做算法或再返一轮，后续文档维护可修。

再现验收：在新output复制所需原件/模型后生成555向量；调用已收tb_delay_effect，或直接用现成M3入口：

```powershell
python -X utf8 code/scripts/run_m3_delay_acceptance.py --rtl code/rtl/audio/delay_effect.sv --contract code/docs/test/M1_T028_final_delivery_20261003/module_acceptance_contract.json
```

正式音频GPRJ尚未加入此模块；不新增控制接口，不接效果开关，不改ADSR/幅度；新Gowin/PnR、参数切换平滑、无爆音、板级效果与最终容量都未验。
C核心验收由M2复用M3 B入口完成，不要求M3重复76776周期；整个T028仍进行中。
