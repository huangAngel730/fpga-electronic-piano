# P1 R06 后继日历准备工具

仅软件／静态准备；原 R05 6ms FAIL，现有捕获属于 R06 7ms 后继＋observer 增量。
不生成真实 capture，不执行 HDL/EDA，不复跑303数学/原专项。

入口（仓库根目录，运行目录必须全新）：

```powershell
& 'C:/Users/songdongkuan/miniconda3/python.exe' -B -X utf8 code/software/m3_r05_functional_integration_20261015/real_trace_successor_20261016/prepare.py NEW20261016A
```

prepare 核封存内原 M1 ZIP、数学判据、90项 stage 身份和既有两捕获 SHA，生成逐字段来源绑定、合成正负例与每例真实 Python 命令/两流/退出码。
总预算180秒，单检查5秒。实际结果见 docs 同名目录收据；运行前将示例 ID 换成尚不存在的唯一纯字母数字 ID，不得复用已有 RUN01–03 或任何其他已存在运行目录。脚本拒绝覆盖。
contract.py INPUT.json 只接受 SYNTHETIC_CONTRACT_SELFTEST；REAL 一律退出1。
schema阳性 exit0 不代表真实输入合同实现、事件完整、数学正确或硬件通过。

字段及未实现语义见 docs 的 FIELD_MATRIX.md。最小隔离接线设计 diff 尚未应用/编译，需要确认后另建精确后继。
本轮禁止 Git 写；不编辑旧封存和共享状态。由总控统一发布及最终交接。
