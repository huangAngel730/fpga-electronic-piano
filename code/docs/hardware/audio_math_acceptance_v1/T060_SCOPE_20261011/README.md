# T060 B：新增身份与范围拒收检查

2026-10-12，M3；交接复核归 M2。只对应新四项任务单中的 B，不包含 A/C/D。

## 与已有交付的关系

95e8bc2 已完成初版机器 scope 和五项自检；该代码、收据及原封存保持不变。
本后继在任务单新指定目录补齐身份、必要收据及范围伪造的定向拒收。
不把新要求倒写成旧交付从未做过，也不回填旧执行或上传状态。

## 实现与边界

scope_bundle.py 只读三份固定 SHA 的原收据：V0283 ACCEPTANCE_SCOPE/SUMMARY，
以及原 router/audio receipt。prepare 从既有固定载体提取第三份，verify 只用包内原字节，
不依赖 GitHub、工作树数学模型、ROM 或原大 capture，不 import/执行旧 checker。
信任根写在程序中；修改依赖身份后重签输入 manifest，不能把新身份冒充已签身份。

机器摘要分列 REUSED / EXCLUDED_METADATA_EXPECTATION / UNCOVERED / NOT_RUN。
capture2 两原 SHA、七 ROM、56 原冻结输入、13 原候选软件身份来自原 receipt。
这些是**历史身份引用**，不是本轮重新执行数学或测得旧源执行 SHA；原 raw/LF 差别不抹除。
本轮实际新软件、读取的原收据/载体、两个旧 scope 文件的执行前后 SHA 另存新 receipt。

仅三 END 诊断次数的独立期望和两个精确 fixture flag 期望排除；原值保持，expected=null。
不扩大成时间窗口或全部 flag，PCM/数学/身份/时序不排除，也不用 flag 选择黄金。
真实退休/接受 panic、frame/math 重叠两缺口仍 UNCOVERED；物理 STA/设备仍 NOT_RUN。
旧主入口 PARTIAL/exit3/unsupported 原样保留，完整 T060/T061 均不关闭。

## 新检查

新增 29 项软件单测，不运行原五项或旧音频套件。涵盖输入/ROM/依赖/源 SHA 错、
缺必要收据、改收据再重签、窗口/全 flag/额外点排除、误排 PCM、零/PASS 冒未验期望、
bool/int 混同、假 complete/STA/物理/RTL 许可、移除功能缺口、假称新数学重放、
旧 exit3 改绿、未知字段/重复键/NaN 以及拒覆盖。

run_scope.py 使用新目录、总 300 秒/单步 90 秒：29 新自检、prepare、包内隔离 verify，
八份完整坏摘要、缺实际收据和重签坏收据两 CLI 坏例、一次拒覆盖，共 11 CLI 非零拒收。
逐步命令、stdout/stderr 原字节、SHA、退出码/超时、执行前后 SHA 写入 receipt。
测试失败与首失败保留，不自动提限或覆盖；源码更新必须换全新输出目录。

本任务实际验证仅 L0/L1 软件结构/身份/拒收，不新增声音 L2/L3 或物理 L5。
不重放原 capture2/56 坏例/B2M 数学，不运行新 RTL/VVP/Gowin，不改共享表或 M1 源。
正式登记由 M2 收口。

本轮新软件有界执行：29 项单测通过、11 次 CLI 定向非零拒收通过，正常包内 verify 退出 0；
运行总计 0.875 秒，原步骤日志及执行前后 SHA 见封存 run/receipt.json。
此时尚未提交/推送，发布结果以后续独立 GIT_DELIVERY 收据为准，不回填此封存。

## 运行和离线复核

```powershell
python -I -S -B -X utf8 code/software/audio_math_acceptance_candidate/t060_scope_20261011/run_scope.py run --output code/output/t060_scope_new_run
```

封存 ZIP 解压后，任意工作目录可运行：

```powershell
python -I -S -B -X utf8 run/bundle/scope_bundle.py verify --bundle run/bundle
```

该 verify 不联网、不回放捕获、不从仓库补模型。需要全量重跑新软件单测时应在仓库执行
上面的 run；封存内 sources 保留本次三份源码，未声称离线 run 自动获取旧 Git 载体。
新封存及转发包清单列所有原字节与 SHA。发布门禁/提交/推送状态以单独实际收据为准。

交接状态：待用户转发 M2，尚未送达；尚未获得 M2 本后继专项签收。
