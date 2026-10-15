# 原缺陷与软件执行失败历史

## V0355 原缺陷（本轮实际复现）

旧core SHA `f6a2a695a7ffa1d61b6691cd7fc76dcba71bac131ba9943f3cf942f9b2d3cfe1`。
在synthetic有效fixture分别向vlog/vsim加 `# Error: synthetic diagnostic`，
保持精确PASS、exit0和相同输入快照，旧版两例均误收。
本轮 `reproduce_diagnostics.py --baseline` 实际退出1，完整双流、源码原字节、
两份完整坏材料保留于RUN_20261015_R01（及SYNTHETIC_DIAGNOSTIC_CASES.zip）。
该1是指定缺陷复现结果，不是未解释的新工具失败。

## 子代理首次环境失败

命令：`C:\Users\songdongkuan\miniconda3\python.exe -X utf8 -m unittest -v test_diagnostics`。
cwd为仓库 `code/software/m3_r04_receipt_audit_20261015/`。
默认沙盒调用chunk `dd30ac` 退出1；36项均在setUp创建临时ZIP时报
`PermissionError: [Errno 13] Permission denied`，位置是沙盒重定向临时目录
`C:\Users\songdongkuan\AppData\Local\Packages\sandbox.{e4970e6a-8de1-442e-9a8b-568eda51e450}\AC\Temp\tmp6tupy4t3\r04.zip`；
后续tempfile清理也报WinError5。没有执行checker断言。
工具输出被截断，未保存本地完整原始双流；此处仅保留子代理转回的准确关键异常，
不能声称已保留该首次环境失败的完整原日志。

同命令在获批require_escalated后调用chunk `d63518` 退出0，36项通过/0.251秒。
统一runner后续显式绑定TMP/TEMP至本任务新输出目录，再执行有界全量软件自检，
完整新双流保留，不以环境失败改写业务结果。

## 发布网络状态

本轮开工本地与缓存origin/develop均为904ccfb。
首次 `git fetch origin develop` 实际退出1：`Recv failure: Connection was reset`。
不把缓存远端身份冒称本轮在线已核，不使用force或改远端绕过。
后续发布状态以实际Git结果为准。
