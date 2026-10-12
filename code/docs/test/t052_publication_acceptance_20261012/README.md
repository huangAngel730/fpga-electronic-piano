# T052 发布完整性独立软件后继

2026-10-12，M3 分担 M1，按《M3_四项独立代码任务与T052分担_2026-10-12》任务2。
复核主控为 M2；本说明/给 M1、M2 的通知均待用户转发，尚未送达。

## 当前交付结论

仅新增 code/software/t052_publication_acceptance_candidate_20261012/ 和本目录。
没有修改 M1 DUT、TB、模型、原 checker/runner，未改共享登记/接口/ROM。
软件 L0/L1 准备完成，不代表实际 T052 发布完整性闭合；完整 T052/T060/T061 保持 PARTIAL。

新检查器分两个明确模式：

- legacy：只做 v5 格式、范围、END 自洽和必要的有序成员检查。即便数量相等，也不能证明真实接受/取消归宿，返回 UNKNOWN/3，绝不把未匹配请求推定取消。
- controlled：只验证带明确标签的手写软件 fixture。先用独立输入控制和冻结 DUT 源码 FSM 推导日历/每个接受事务的归宿，再核观察和完整发布集合；不是以 result_valid 或发布名单构造期望。

后者是未来最小控制证据合同的静态软件准备，目前 META 强制
HANDWRITTEN_SOFTWARE_FIXTURE，故不能拿未经预检的实际端口日志冒充本轮通过。
本轮不需要新增 TB：格式和 pre-NBA 口径见 CONTRACT.md，先交 M2 静态审核，再由
M2 决定最小补采范围。没有执行任何新 RTL、声音数学回放或 EDA。

## 已运行的新软件检查

资格输出 code/output/m3_t052_publication_20261012_01：总 1.047 秒，退出0，
SOFTWARE_ONLY_QUALIFICATION_PASS。300 秒总限/90 秒单步限；原始命令、
stdout/stderr、逐步退出码、Python exe SHA、四源执行前后 SHA 完整保留。

- 7 个 unittest 方法通过（含10组完整轨迹及严格类型/解析等子场景）。
- 两份完整手写正例 CLI 退出0：重复 ID 两次独立代次；CALC 取消、帧优先、背压、复位/同 ID 再分配。
- 八份完整手写坏轨迹 CLI 均退出1，命中指定诊断：自洽 END 的丢结果、重复发布、旧 epoch、错代次、帧沿旧发布、valid 提前一拍、ready 无真实接受、伪造取消 END。
- v5 原始正例、M2 删第101条发布和截前4096条发布反例均格式检查通过，但完整性 UNKNOWN/退出3，拒绝完整性签收。

这里不是声称从 v5 原字节已经证明哪32条被真实取消，或已经独立确定两个坏例
的逐事务丢失原因；现有取消控制证据不足，三份均不获 PASS。手写完整轨迹中
有独立控制时，丢结果才明确 FAIL/1。该区别不能用固定4207阈值替代。

已签新4207条声音数学引用 M2 V0300：REUSED/NOT_RERUN；M2 原 checker 两次
误收结果引用原日志，不再次执行旧 checker 或旧数学。已过六短 RTL/commit/WAV
不重跑。仓库发布强制九门禁另列，短 T007/T019 不属于新 T052 补采。

## 只读身份与充分性

v5 原 ZIP 在本机交付路径未找到；不宣称重新获得/验证原外 ZIP。
使用已在仓库封存的 M2 RAW_EVIDENCE.zip 原始成员，核归档 SHA 和逐成员 MANIFEST：

`86704ddd20ee755d3d77ebe7a1379f3a8f2992e9a867a251fc1e3574ff4817a0`

M2 received_identity 原记录的 v5 ZIP SHA（来源引用，不冒本次原 ZIP 实测）：

`c7981d106d162a45ee3580188a401f9dad81da64bd00e085c2dbf2fb49558e2c`

DUT 原成员 SHA：89ddb8b73bda6e5c83c7b617640cddf3294fb194a9b7955746c28a2e0f2eddeb。
REQ SHA：97e8edceacb3e49fff9d602b921a6567af913caf0a30e6e09f6a40e1e121407d。
正常 capture SHA：1a6de37a14d14bbc405e74ec6cc174548ab9e0290c6567edbc031b08534633b0。
两坏 capture SHA：

- 8e425f8ea7dffd6c91a65d20ea0f980a7e68c24639ff4adcdbffcd46621a322c
- c324882c0509b4c9433134f4ef499ea2a9226a802867764b917051fda5c68e6e

实际输入充分性分析：

1. do_one 在 negedge 驱动 sample_req 后直接写 ACC，未逐 posedge 记录接受。
2. 仅有 RESET 文本，缺少 frame/cancel/reset 的准确沿号和覆盖窗口。
3. capture 在 negedge 观察并写出，然后拉高 result_ready，不是 pre-NBA 的完整握手记录。
4. RESET/重复 ID 后不能仅凭 ID 搜索确定寿命。取消场景代码还把实际 req_id 设为
   0x90000001，而 ACC 写 acc_id；静态记录该口径差异，不改原件、不推断该差异导致新错误。
5. 两份修 END 坏例仍满足 v5 自洽 END；不能由差集反推取消，也不能从正常 capture
   取一个应发布名单冒充独立黄金。已签数学不等于发布完整性。

## 复现

在仓库根目录，Python 路径为：
E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe。
标准库即可，无安装；将下面 python 替换为该绝对路径，输出必须全新：

```powershell
python -I -S -B -X utf8 code/software/t052_publication_acceptance_candidate_20261012/delivery.py qualify --output code/output/m3_t052_publication_review_new
```

离线收包者无需 GitHub：解压转发包和内部 SOFTWARE_EVIDENCE.zip，运行其中
evidence/snapshot/test_publication.py；原始日志和手写完整轨迹位于 evidence/readonly
及 evidence/corpus。检查单份控制例：

```powershell
python -I -S -B -X utf8 evidence/snapshot/publication.py controlled --controls evidence/corpus/normal_repeated_id/controls.jsonl --observations evidence/corpus/normal_repeated_id/observations.jsonl --publications evidence/corpus/normal_repeated_id/publications.jsonl
```

此命令仅新软件，不能据此运行 M1 原 runner 或申请外的新采集。

## M2/M1 后续动作

M2 请复核新增合同、checker、完整正负例及 UNKNOWN 边界；决定最小输入控制/只读
日志补采范围。M1 请提供已有逐沿请求、frame/cancel/reset、ready/valid握手及输入身份
记录，或明确现有记录不存在；不并行重写同一 checker。不以此交付替换生产入口。
任务3的独立 runner 和任务4端口投影尚未开展，不混入本任务。
无安装/串口/接线/烧录/下载，实际资源、整机接入和 STA 仍归 M2。
