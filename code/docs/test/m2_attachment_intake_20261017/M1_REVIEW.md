# M2 内部只读辅助复核：M1 第17批 Pro 软件准备

本报告只供 M2 主集成窗口决定限定接入；不是审核员/预审员制度结论。已读当前仓库规范、协作入口、M1/M2任务卡、R06完整单与总览，附件的 TASK_RECEIVED/README/回执仅作为历史证据，没有据此运行附件脚本或恢复旧额度。

## 结论

此前未见本批精确版本已发布/签收。可选择性接入 **129 个新文件（模型5、证据124），限 L0 来源及合成软件准备**；本次静态阅读未发现阻止这一限定接入的具体代码问题。A0/A1/B0准备可保留为后续复用输入，不能写成当前R06的19字段真实语义/显式RTL出口、真实Pro PCM接入、全FRAME覆盖或基础整机通过。

ZIP `M1_Pro四声算法准备_20261016.zip`：7,384,923字节；SHA256 `54efcff568e7115334f6aa4c1bfb0554c5a0b0014b5c8b4a1a6627b63a6fc5a0`。204文件，CRC全部通过，路径安全；203条成员manifest的大小/SHA全部匹配（manifest自身不自引用）。去掉repo前缀，129是新pro_successor文件，71个既有只读依赖逐字节等于已发布树；2个旧任务/总览快照与现行不同，不覆盖；另2个外包说明/manifest不当生产源码。

## 原件和最终版本

- A0原收据为73文件/32 R06归档成员、七冻结依赖与三ROM核同，最初外层stdout/stderr未独立落盘的限制有明确登记；后续FINAL_STATIC_R01原stdout记录独立核验PASS。其历史Pro/PG484冲突说明不覆盖现在已发布R06-C1事实。
- A1原stderr实际14个新方法PASS；五场景各256、共1280行均为合成。复用父模型，未新增DDS/ADSR/混音/效果数学。四独奏效果后相加4476与合奏黄金4479的见证只限软件。非零clip正例未覆盖，不能把错clip false→true拒收升级为真实削波覆盖。
- B0最终生产源码SHA256 `7213e9fdce5fcab4dd5828b282613def88e8f5d7566986e3af6b89ae9c899267`。首轮30 PASS对应旧源码`497e8a7d…16894de`。原四CLI实际exit0/1/2/3，分别合成接受/1LSB差异/先身份拒收/伪装REAL仍待验，均为修前过程原件，不移签最终源码。
- 修前缺失另一端输入时跳过可用日历核验的缺陷已有最小修复；最终同一生产源码上32方法PASS及后来新增1方法单独PASS，测试文件版本不同。不得说最终33方法单次全跑。
- 已独立核6份executions收据SHA以及对应12原始双流bytes/SHA；读取关键1LSB、错source先于PCM和伪装REAL报告及最终测试stderr。未执行任何包内Python、HDL、EDA、硬件或Git写操作。

## 信任与当前接入限制

`capture_compare.py:219–320`只接受settled四lane同沿tick、独立event/config/effect/cancel日历；每calendar action严格不同cycle；不实现生产前端、同沿仲裁、FRAME计划或deadline。`389–423`的期望由独立日历及冻结Reference重建，DUT wave/env/phase只允许实际diagnostics，不反填黄金。身份在PCM比较前全部校验。

`29`空`APPROVED_PRO_MAP_SHA256`及`528–531`无条件四个missing项使当前REAL数学即使相等也始终PENDING。异步RESET_EDGES、rawdriver/fulltrace/observer同源链、执行工具/argv/双流/退出/消费、连续性认证没有被这个profile实现。`REAL_CAPTURE_PCM_PASS`当前不可达，保留board_release_allowed=false。SHA只证明收到的文件字节，自报capture_id/producer不能单独证明真实来源。

因此当前R06-C1独立FRAME公式、完整窗口直到真实finish（包括idle和合法取消）、F与实际A分离、TX pending/held身份旁带等仍由M2/M3后继包实施。将来真实接入需要另交受信source/ROM/端口复位合同及同次原始日历/PCM；不能仅把allowlist加一个自报SHA、删除四个missing或把旧合成改名REAL。

## 发布换行处理

129新增中22成员含CRLF（日志与SESSION收据），5个生产/测试模型Python都为LF，原件SHA不变。根gitattributes统一LF会改变实际分散发布的10份SESSION JSON字节；12份CRLF双流只在ZIP提供；完整raw/LF SHA映射在`EVIDENCE_AUDIT.json.crlf_new`。原始日志/收据以主窗口另封存的新129载荷ZIP为准（主窗口告知SHA `96c535fbdfc08d929f987ab59a7c9d007335aa194d4a714db4ba4cafdc214e11`，此处仅登记其告知值，本助手未重新核该新ZIP）。不要声称Git分散129件与附件全部原字节相同。

本助手输出仅在`code/output/m2_attachment_intake_20261017/m1_review/`。ZIP_AUDIT.json、EVIDENCE_AUDIT.json保存本次纯文件检查。没有对主分支、既有候选、共享状态或附件生产内容做修改；最后接入/发布由M2主窗口执行。

当前最终封装：129原载荷全部在原件ZIP；Git分散89件（模型5、文档/证据84），40原始.bin均仅ZIP。22个CRLF原件具体为10份SESSION JSON（分散遵根LF）和12份.bin（仅ZIP），不能宣称Git分散129件或22件分散归一。
