# P1 准备交付与自审

任务的“缺真实字段则交缺口＋最小接线建议”分支完成；真实日历仍未完成。
仅 L0 静态／软件 schema 自检（非 L1）；本任务没有 HDL 编译，不签完整数学、router、RTL、整机、STA 或实物。
REAL_RESULT=PENDING_REAL_CAPTURE，board_release_allowed=false。

## 原始执行

工作树起点 `f4502b99092b4c8d94e6aac755b850e274136730`；执行机 LAPTOP-KSS1MRR7。
实际 Python 使用既有 `C:/Users/songdongkuan/miniconda3/python.exe`，执行 SHA/版本在各 PLAN.json。
最先 `python` 命中了 WindowsApps 执行别名，在 CreateProcess 启动处报“系统无法访问此文件”，未运行 Python；没有修改系统或安装。随后依据旧真实收据选用已存在的 miniconda Python，不涉及 ModelSim 替换或恢复额度。

实际命令分别为：

```powershell
& 'C:/Users/songdongkuan/miniconda3/python.exe' -B -X utf8 code/software/m3_r05_functional_integration_20261015/real_trace_successor_20261016/prepare.py RUN01
& 'C:/Users/songdongkuan/miniconda3/python.exe' -B -X utf8 code/software/m3_r05_functional_integration_20261015/real_trace_successor_20261016/prepare.py RUN02
& 'C:/Users/songdongkuan/miniconda3/python.exe' -B -X utf8 code/software/m3_r05_functional_integration_20261015/real_trace_successor_20261016/prepare.py RUN03
```

- RUN01：79 子检查，exit0，6.078秒。早期字段范围，未保存脚本原字节快照，只保留前后SHA、输入及两流；不作为最终源码测试替代。
- RUN02：增补 math 接受日历、应用kind、重复JSON/尾后记录拒收、来源锚定和源码快照；85 子检查，exit0，7.890秒。
- 自审发现序列引脚的源码名为 i2s_bclk/ws/din，旧拟议绑定写成输出JSON别名；时钟/复位也应绑定已有 observer 文件而不是空身份。只修 prepare 的映射和精确时间表达式，未改业务源。
- RUN03：最终映射版85子检查：1合成格式正例、84指定拒收，全部符合预期，exit0，8.094秒；各例命令/实际exit0或1、stdout/stderr、源前后SHA及 Python 身份齐套，无超时。最终 contract.py SHA `8e6f47e9c3bb6207073897a5ef9a25f01effb92650fbef37719959b384df3fb3`。prepare 的最终 SHA 见 RUN03/RECEIPT.json。
- 合计实际 schema 子进程调用249次，真实RTL/ModelSim/Gowin/设备调用0。这是三轮开发自检，不是249次RTL或新真实捕获。原已签软件/303数学不重跑。

## 自审边界

1. M1 原 ZIP 与根判据完整SHA核同；stage原收据SHA固定，90项原输入逐件核同；两捕获原SHA核同。未重新打原ZIP、重命名R05或改任何旧证据。
2. 真实捕获的旧格式行被 ROW_FIELDS 拒收，缺的应用、tick、fx日历不填零、不按固定周期猜测；格式REAL即使完整也以 REAL_CAPTURE_NOT_QUALIFIED 拒收。
3. 每标量字段及每lane字段均列原源身份/接点；应用kind与event_seq、自主退休关联、完整异步复位流仍是需确认的提议，不伪称已有公共端口。
4. 仅做字段合同拒收，不能证明现场记录真实性或事件完整性。测试中的合成 tick 组合只测格式，不代表冻结 bank 的合法业务场景。ready乘valid只是观察一致性，不是独立资格判定。独立 FSM/PCM oracle、应用seq完整检查、真实reset子周期检查仍未实施，本任务不以这些未实施功能报PASS。
5. 最小diff是设计草案，不可直接apply，没有编译、仿真或新增观察输出。正式源码/接口一字未动。
6. 三个新目录之外无写入；无Git写操作，无其他窗口通信/复核，无共享表修改。

## 给总控

文件：软件目录 contract.py / prepare.py / seal.py / README.md；TB目录 PROPOSED_OBSERVER_WIRING.diff；证据目录 FIELD_MATRIX.md、本说明及 RUN01–03 原始输入/双流/收据、SOURCE_BINDINGS.json、INPUT_IDENTITY.json，最终封存见 SEAL01。
当前可交付的是准备分支，不是原真链或真实数学全部完成。需 M1/M2 确认只读观察口、应用关联和 reset-edge 格式，随后核定新精确树/实际工具/一次额度；不得复用已消费7ms轮次。
请总控统一串行发布及最终签收，本窗口未提交/推送。原R05=6ms FAIL；既有成功捕获为R06 7ms后继另含observer增量。

## 总控两项文档返修（SEAL02）

仅修等级为“L0 静态／软件 schema 自检（非 L1）”及 README 的唯一新运行 ID 示例；checker、runner、接线建议均未改。
新增实际命令为上述 prepare.py 入口参数 RUN04；exit0，6.531秒，85子检查（1合成格式阳性、84指定拒收），timeout=false，源前后SHA一致。两流、逐例退出码和源码快照见 RUN04。截至本次总子检查数334；前述249仅指旧三轮。
RUN01–03 和 SEAL01 保持原字节。本次新增 SEAL02，封存命令和校验结果见其中 SEAL_RECEIPT.json；未执行Git写入、HDL编译、ModelSim/Gowin或板卡操作。

## 最终可复现封存（SEAL03，覆盖前文最终包入口）

SEAL03 为最终可复现包；SEAL02 仅保留为第一次文档返修历史，其 stdin 封存脚本未保存，不作为最终可复现入口。SEAL01/02 不删不改。
仅修 seal.py 支持纯字母数字 seal ID／归档代次、拒覆盖，排除所有 SEAL* 子目录；收齐三个授权目录中的源码、文档及 RUN01–04 原件（含 .gitignore 忽略的双流）。按排序、固定 ZIP 时间/属性和 ZIP_STORED 保存，精确输入相同时可重现 ZIP 字节；不含旧ZIP递归嵌套。

```powershell
& 'C:/Users/songdongkuan/miniconda3/python.exe' -B -X utf8 code/software/m3_r05_functional_integration_20261015/real_trace_successor_20261016/seal.py SEAL03 R03
```

实际 argv、脚本SHA、成员数、CRC/逐成员长度/SHA核验退出码及最终ZIP SHA见 SEAL03/SEAL_RECEIPT.json，完整成员清单见同目录 MANIFEST.json。重现时须另选未存在的 SEAL 字母数字目录，保留归档代次 R03 和相同载荷原字节；不复用 SEAL03。
本次不重跑85例，checker／prepare／observer建议不改；等级仍为L0静态／软件schema自检，真实采集PENDING，board_release_allowed=false，无Git写、EDA或板卡操作。
