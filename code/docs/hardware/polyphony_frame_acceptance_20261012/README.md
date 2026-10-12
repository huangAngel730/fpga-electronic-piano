# N32 接入前帧事务独立软件材料

M3 主责，M2 复核。依据 Callback3 的《M3后续：T060预检状态与独立N32帧事务软件任务》，只新增本目录及对应新软件目录；共享登记由 M2 收口。本阶段仅 L0/L1，完整 T060/T061 仍 PARTIAL。通知待用户转发，尚未送达。

## 内容与复现

`code/software/polyphony_frame_acceptance_candidate_20261012/`：

- `frame_reference.py`：从初始软件状态和外部输入推进事务，不读观察输出生成期望。
- `trace_check.py`：严格 META/RESET/EDGE/END 解析及逐沿重放。
- `vectors.py`：固定输入日历，11 份完整合成正例及六份完整单目标坏观察轨迹。
- `test_frame.py`：手写期望时点、身份、保持、复位、回绕、限幅计数和格式异常测试。
- `run_checks.py`：隔离复制执行，300 秒总预算、每步 min(90 秒, 剩余)，失败不重试，保留日志/退出码/输入及实际执行源码前后 SHA。
- `deliver.py`：封存本次实际执行快照、完整轨迹和原始日志；核成员 SHA，不执行包内代码。
- `publish.py`：推送后只读核验 Git HEAD/远端/精确树门禁并生成完整转发 ZIP，不自行提交或推送。

运行（仓库根目录，Python 3.11 标准库；输出必须是全新目录）：

```powershell
python -I -S -B -X utf8 code/software/polyphony_frame_acceptance_candidate_20261012/run_checks.py --output code/output/m3_n32_frame_software_20261012_01
python -I -S -B -X utf8 code/software/polyphony_frame_acceptance_candidate_20261012/deliver.py seal --run code/output/m3_n32_frame_software_20261012_01 --output code/docs/hardware/polyphony_frame_acceptance_20261012/EVIDENCE_20261012
python -I -S -B -X utf8 code/software/polyphony_frame_acceptance_candidate_20261012/deliver.py verify --base64 code/docs/hardware/polyphony_frame_acceptance_20261012/EVIDENCE_20261012/SOFTWARE_SEAL.zip.b64
```

软件预算不包含随后必须执行的仓库九门禁。九门禁的原有短 T007/T019 属仓库发布检查，不是本任务新增 RTL 捕获，不增加本任务验证等级。

离线交付 ZIP 包含上述源文件、合同、执行快照、全部正负轨迹、参考文件原字节、日志/退出/收据、封存 SHA 和发布核验。`SOFTWARE_SEAL.zip.b64` 用标准库 base64 解码即可获得内部原始 ZIP；不要求拉 GitHub。目录和成员以封存清单为准。

## 证据边界

所有轨迹明确 `origin=SYNTHETIC_SOFTWARE_TEST`。生成器和 checker 共用本独立事务模型，这不是两个独立数学模型；其独立性指从输入合同推导，而非从 DUT/观察结果反填。手写时点断言和六份完整坏观察用于限制共同实现错误，仍需 M2 复核后用于未来真实 adapter。

N32 只是接入上下文标签，PCM 是外部 signed24 payload，不证明 32 槽发声、混音、DDS、ADSR 或饱和数学。clip 是拟议元数据，不从 PCM 极值推断；epoch 为软件寿命注记，不冒称现有 RTL 端口或硬件 ABA 证明。可控 result/PCM 接收门只用于软件背压环境，不是要求增加生产端口。

只读冻结 M2 V0299 adapter 源及说明、原任务单、V0291 条件日历说明的 SHA/原字节。没有导入原数学模型，没有修改原 RTL/ROM/TB/接口/约束/共享表，没有新 RTL、EDA 或设备操作。原 C 及其它已签阶段不重跑、不回填。

833/834 为指定合成帧间隔，348/351 只在引用条件下成立，未用作固定超时或通用服务上界。真实资源、正式接入和物理 STA 由 M2 决定。RTL/math/physical/admission/complete 全 false；不签生产 N32 或完整 T060/T061。
