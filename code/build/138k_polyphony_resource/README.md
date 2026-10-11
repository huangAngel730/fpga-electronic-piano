# N32/R1 精确资源工程准备（未授权执行综合）

此目录由 M2 管理。固定功能源52ad3dc、B2L准备辅助源2bc96a5，profile为`audio_and_public_read_no_injection`，N32/R1代表、N8备选。原业务RTL/ROM/生产顶层/约束均不修改。

生成目录`prepared/`只放本地机器绑定的工程，不提交生成输入、镜像、资源报告或码流。原件和已封存历史不覆盖。

## 可运行的准备/预检命令

在仓库根目录用现有Python，每次prepare必须选择新目录：

```powershell
python -B -X utf8 code/scripts/prepare_138k_polyphony_resource.py --output code/build/138k_polyphony_resource/prepared/全新ASCII目录
python -B -X utf8 code/scripts/prepare_138k_polyphony_resource.py --output code/build/138k_polyphony_resource/prepared/已生成目录 --check
python -B -X utf8 code/scripts/preflight_138k_polyphony_synthesis.py --project code/build/138k_polyphony_resource/prepared/已生成目录
python -B -X utf8 -m unittest discover -s code/scripts -p test_138k_polyphony_resource.py -v
```

上面`全新ASCII目录`应替换成实际ASCII名称，例如`N32_R1_NEW`；输出只能在prepared/下全新子目录。verify按固定Git源/本机工具文件SHA/自身脚本SHA重建整个输入，不允许改文件后重签清单、布尔/浮点替换、额外CST、run all或隐藏文件。

工程包含13原功能源+1已验wrapper、2include、7ROM、SDC、15项GPRJ、`run_synthesis_only.tcl`和冻结收据。工具器件取本机138K C数据库和原已验C项目，`GW5AST-LV138PG484AC1/I0`/gw5ast138c-007；固定工具文件SHA及安装包官方发行说明身份。

clock.sdc保留25ns、Setup1ns/Hold650ps，只是独立单域资源工程约束，无CST/板级I/O/reset全分析结论。工具Tcl只有run syn，无run all/PnR/bitstream。**没有实际执行过这个Tcl，不要直接运行它。**

预检入口`--execute`明确退出1/SYNTHESIS_NOT_AUTHORIZED，本版本没有综合启动实现。计划参数为单次、最大900秒、无自动重试/改seed/降到N8；只有后续获得针对精确工程的明确许可，再受控实现执行入口，不把清单中的许可字段自改成true。此准备不消费额度。

## 报告解析边界

`inspect_polyphony_synthesis_report.py`仅可读取已有真实层级XML，保留报告SHA、原属性和每个层级Register/Logic/LUT/BSRAM/SSRAM/DSP字段；缺字段为null/UNKNOWN，不将层级总量重复相加，也不从MULT个数推DSP数。它不验证工具运行来源，不能单独授予资源准入；实际运行收据和身份门禁必须另核。本轮测试使用合成fixture，未形成新候选资源结果。

正式整机接入、新40MHz STA、设备/下载仍未放行。新RAM基线5e1d13c、旧RAM停用；本模块不混入RAM时序证据。完整T060/T061保持PARTIAL。
