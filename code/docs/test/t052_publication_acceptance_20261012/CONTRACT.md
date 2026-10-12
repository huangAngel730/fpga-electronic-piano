# 提议的独立控制/逐沿观察/发布归宿合同

本合同为手写软件夹具与未来静态预检准备，未授权新 RTL 捕获。
基线是精确 T052 v5 DUT，不改成 N32、冻结 H/L 或新 RAM 工程。
时钟按原 TB 50MHz、1042帧节奏；本软件用整数边沿，不借用40MHz整机结论。

## 三份独立轨迹

UTF-8 JSONL，每行一个对象，无空行、重复键、非有限数和额外字段；布尔端口只用
整数0/1，Python/JSON true 不可代替1。原始输入不能取自 capture 缺失名单。

controls.jsonl 的 META 精确字段：

```json
{"type":"META","schema":"T052_PUBLICATION_PRE_NBA_V1_PROPOSED","source_sha":"89ddb8b73bda6e5c83c7b617640cddf3294fb194a9b7955746c28a2e0f2eddeb","sampling":"PRE_NBA","reset_scope":"NO_UNOBSERVED_ASYNC_PULSE","origin":"HANDWRITTEN_SOFTWARE_FIXTURE"}
```

紧跟 cycle 从0到 last_cycle 连续的每沿输入，第一沿必须复位：

```json
{"cycle":1,"rst_n":1,"frame":0,"cancel":0,"sample_req":1,"req_id":7,"enable":1,"mask":15,"fcw":[1,2,3,4],"result_ready":0}
```

尾部唯一 `{"type":"END","last_cycle":11}`，END后无记录。不允许 gap 或把只含
请求的稀疏日志当全控制窗口。输入采样在 posedge 前稳定，不能与 DUT 在同一 active
region 竞争驱动；未来用只读 TB/observer 时必须保证负沿驱动、正沿采 pre-NBA。
当前 reset_scope 仅手写夹具保证无边沿间异步脉冲，不代表实际捕获已证。未来真日志
必须提供独立异步复位事件时间或明确 fixture 无此事件的源身份，先交 M2 审核。

observations.jsonl 每沿：

```json
{"cycle":4,"calc_ready":0,"result_valid":1,"result_id":7}
```

来自实际公开端口的候选字段，不用内部 state/accept 做黄金。完整窗口及 END 与控制
相同；期望 ready/valid/ID 在读取观察前由输入和源码 FSM 推导，逐沿比较，不以实际
result_valid 定义“应当发布”的集合。当前只有手写轨迹，无真正端口实测。

publications.jsonl 的记录：

```json
{"cycle":5,"key":[1,1,7]}
{"type":"END","accepted":2,"published":2,"cancelled":0,"open":0}
```

key=[reset_lifetime,accept_serial,req_id] 为 checker/observer 的软件关联标签，不是
真实 RTL 新端口。serial 在每次真实接受递增，reset 新寿命从1重计；重复 ID 仍是
不同事务。原 v5 没有这些标签，禁止按发布序号或缺失名单回填。未来观察器只能根据
独立输入、已核接受谓词和准确沿号附注，不能从输出反推事务。单纯软件标签不证明
DSP 排空/避免所有 ABA，也不能扩写成无条件32位回绕安全。

## 冻结源码日历与优先级

原 DUT：calc_ready=(state==IDLE)；accept=calc_ready && sample_req && !frame && !cancel。
复位优先于 frame/cancel；后者优先于整个 FSM。即使帧沿 calc_ready 为1也不接受。
即使 frame/cancel 沿旧 result_valid&&result_ready 为1也不记成功发布。

| posedge 前状态 | 无 reset/frame/cancel 时的转换 |
| --- | --- |
| IDLE 且 sample_req=1 | 接受、DDS推进一次、下一状态 CALC |
| CALC | 下一状态 HOLD，旧 valid 仍0 |
| HOLD 且旧 valid=0 | 沿后 valid=1；这一沿不能提前握手 |
| HOLD 且旧 valid=1、result_ready=1 | 发布一次、沿后 valid=0/IDLE |
| HOLD 且旧 valid=1、result_ready=0 | 保持待发布 |

因此接受在 c 时，首次 PRE_NBA valid 可在 c+3 观察，最早握手也为 c+3；
HOLD 首次计算沿发生在 c+2，但 valid 是 NBA 后才出现，不能错把 c+2 算发布。
观察 ID 按 DUT 保留无效期旧值，只有 reset/frame/cancel 清零，非握手后立即清零。

frame/cancel 只终止未完成事务，不回滚已经发生的 DDS推进；reset 才清相位。
软件 phase ledger 仅检查接受 FCW 增量和取消不回滚，没有重算 ROM/声音数学。
enable/mask 不决定接受或相位推进，仍记录并严格验证以保持输入合同。

## 完整性判定

先从 controls 推导 accepted、cancelled 和 required-publications，每个接受必须唯一
归属于发布或明确控制取消，END时 open=0；未完窗口拒收，不默认为已取消。
然后将 publications 与独立所需的有序完整集合逐项比较，重复/漏掉/旧寿命/错代次/
错沿全部拒收。END各计数由独立控制重算，不从捕获 END 或 min样本阈值决定。
正常取消受支持；已合法发布不能因后续帧被改写为取消。

PASS/0 仅适用于本手写软件合同。格式或可证的集合矛盾 FAIL/1。
v5 只有 ACC+capture 时，即使结构通过也 UNKNOWN/3、publication_complete=false，
不把 UNKNOWN 写成 FAIL 的实测丢失定罪，更不能写成 PASS。

本轮不验证 PCM 值/左右声道/held PCM稳定/clip 来源；它们保留原数学结论和任务4
投影边界。没有模拟设备、综合、资源映射、物理时序或正式音频运行。
