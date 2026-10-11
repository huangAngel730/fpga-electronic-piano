# B2M 软件闭包最小返修（2026-10-12）

本阶段仅修 V0284 指定的软件交付问题，交 M2 复核；完整 T060/T061 仍 PARTIAL。
不改 b2m_check、数学模型、原 RTL/TB/ROM/capture、共享表和旧封存。

## 实现与来源

- `b2m_run.py --closure-only`：独立新入口，单步 90 秒、总 300 秒，新输出拒覆盖。
  原 16 步数学／旧 12 自检不调用；历史入口必须明确指定 legacy 参数。
- `b2m_closure.py`：以固定 SHA 的原 B2M ZIP 和 M2 RAW_EVIDENCE.zip 为双锚，
  原件内 7 个本地数学源码加 M2 精确 Git 补充的 envelope_model/strict_capture，
  合计 9 个实际 import 文件。补充件不能写成旧 M3 运行已测依赖。
- 保留原 5 ROM、3 捕获和 M2 原收据／首轮缺依赖失败日志，原字节不变。
  新运行记录依赖前后 SHA、实际隔离导入路径/SHA及原始 stdout/stderr/退出码。
- `deliver_b2m.py closure-seal/closure-verify`：验证只用包内模型；历史不自足 verify
  入口明确拒绝，防止继续借工作树模型成功。历史旧封存工具副本仍在原 ZIP。
- 验证子进程采用 `python -I -S`，只允许标准库及包内精确路径、原 SHA 的 9 模型。
  包外同字节模型同样拒收；不依靠修改 PYTHONPATH 使旧包“成功”。

数学结论仅 REUSED M2 V0284：原单 A4／零调制／指定取消复位，63 发布、189 valid-HOLD 沿。
本次不调用数学 checker 的 check/Mathematics，不新增数学等级或逐槽观测。
新软件自检与缺件、重签坏依赖、包外导入拒收单独记录，不重复原 16 步／12 自检／5 篡改。

## 命令

从仓库根目录使用当前 Python 3.11（以下以 `python` 代称）：

```powershell
python -B -X utf8 code/software/polyphony_scaling_candidate/b2m_run.py --closure-only --output code/output/m3_b2m_closure_20261012_01
python -B -X utf8 code/docs/hardware/polyphony_scaling_v1/deliver_b2m.py closure-seal --run code/output/m3_b2m_closure_20261012_01 --package code/docs/hardware/polyphony_scaling_v1/B2M_CLOSURE_20261012
python -B -X utf8 code/docs/hardware/polyphony_scaling_v1/deliver_b2m.py closure-verify --package code/docs/hardware/polyphony_scaling_v1/B2M_CLOSURE_20261012 --output code/output/m3_b2m_closure_verify_20261012_01
```

重复执行应另用全新目录。新包包含精确旧锚、全部模型、ROM、原 capture、REUSED 来源、
新工具、隔离测试及原始新执行日志；无需 GitHub 或工作树数学模型即可解包验证。
`committed_at_seal/pushed_at_seal=false` 如实保留生成时状态，后续提交／推送另交收据。

## 状态和边界

状态以新 receipt.json 为准，不把文档当测试通过证明。新软件阶段目标 L0/L1；
原有限数学 L3 来自 M2，非本次重算。无新 RTL 仿真、综合、PnR、STA或设备操作；
不签生产 N32、通用多槽演奏、LFO 非回滚、R64 deadline 或完整 T060/T061。
T060 下一阶段只整理机器 scope 和最小两组补采静态预检，补采执行仍需 M2 确认。

交接通知：待用户转发 M2，尚未送达。
