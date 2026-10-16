# E3首失败与有依据的不同尝试

前三轮都已消费，原输入、执行源、原双流和返回码保留在ROUND_01..03。未启动任何VVP，不把编译崩溃算反例通过。

1. ROUND_01：44条真实文件记录/独立MIDI oracle生成成功，编译驱动exit3221225477(0xC0000005)，stdout/stderr均空，未生成可验证RTL结果。最初怀疑执行路径长度；后测最长213字符，未超260，不能将路径写成已确认原因。
2. ROUND_02：只改短相对路径编译并复用首轮输入；来源与工具字节未变，仍同返回码，路径假设不获支持。
3. ROUND_03：参照已签OSS运行器隔离PATH/IVERILOG_ROOT/TEMP，不安装或替换工具，不改RTL，仍同返回码。环境隔离尚未解除阻断。

随后读取同工具E1成功记录RESULT.md，明确记载正常require_escalated审批通过后才执行成功。下一轮申请正常本机工具执行权限，仍用原工具/输入/代码、独占新输出和剩余额度；该申请不等于已批准，也不绕过自动审批。若审批拒绝则保持BLOCKED/保本地封包，不换工具规避。

执行前自身只读子智能体发现checker诊断顺序会先报ACK/NACK身份而非指定错误码，已在ROUND_01前修正为身份字段→错误码→ACK/NACK类型；没有为此消费功能轮。旧T057 NACK8会话合同差异继续保留。

ROUND_04：正常require_escalated审批通过，同一编译工具/输入/源在0.078秒编译exit0，证明前述沙盒执行阻断已解除。整体exit0/122.188秒，92场景82应答，6次44条公开RAM快照、全部44条UART READ核同；冻结严格checker对干净段106帧/3次重放PASS；真实CRC旁路变体运行exit0，新checker按[COMMIT,NACK9]期望实际[COMMIT,ACK0]拒收exit1。该轮仅旧接收器，不能签NACK8修复。

总控随后要求在授权新后继目录修NACK8。旧16013字节接收器保持SHA不变；新score_transfer_e3_successor在v1语义COMMIT错误4/5/6/8清active/cache，ERROR_WAIT次拍响应，success ACK缓存重放优先分支不改。ROUND_05拟在同一真实文件上新增相关生命周期、旧RAM保持和fresh BEGIN恢复；使用剩余第5轮，不恢复前三轮或改历史结果。

ROUND_05：新后继完整影响范围PASS，整体exit0/204.390秒；127场景、112应答、11次完整44条RAM快照及干净段44条UART READ核同。14个实际NACK包括帧CRC、丢包、帧/50ms参数会话超时、整曲CRC和新增COMMIT生命周期；旧已提交曲谱保留。NACK8后原cached DATA及下一DATA均NACK5；语义4/5/6均清会话；新BEGIN恢复发布与COMMIT重放核同。CRC旁路行为变体仍仿真exit0、checker指定首差异exit1。严格checker只签干净106帧/3重放段，不把包含NACK的全轨迹写成严格PASS。

自审发现新checker无条件输出NACK8已验标记，--clean-only或旧inputs也会误标；该缺口未影响ROUND_05的实际完整新增覆盖，但需要修对外出口。最小修复新增commit_fix_coverage，仅完整必要用例/active0才TESTED。ROUND_06只验证该helper的5个控制及原ROUND_05证据绑定，exit0/0.563秒，干净段/旧plan/缺cached拒收/active错误四项均NOT_EXERCISED，未重复RTL或串行组。最终checker仅此覆盖标签分支经过定向验证，未全量重跑原组。

最终6/6轮已用；整体轮exit1/1/1/0/0/0。全保首失败，不续开目录获得额度。自身只读子智能体复查最后增量及实际证据未发现具体阻断。没有ModelSim/Gowin、综合/STA、设备或Git写入。
