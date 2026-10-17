# D3最小可逆修法提案（仅静态，待M2）

基线c7e0144ac33acfde9b449183933ef7a21aa9325c。原D3 `code/software/m3_pro_fourvoice_trace_20261016/D/ingest/ingest.py` SHA256 `3217f97e57daec534306a213c64566fa111e3116f15a15967ca881847c218e07`保持只读；本目录REPAIR.patch.txt只展示未来后继的文本差异，没有应用、import、CLI或测试。当前D3仍PARTIAL/REWORK_REQUIRED，静态提案不等于返修通过。

## 漏洞与最小变化

原109–124行只在收到FRAME后设置due_cycle；164–168行CANCEL只看due_cycle，130–132行END只看终态；103行RESET使用<834兜底。漏FRAME2510后req8在2512被取消，已835拍，仍可进入END2513。旧R02 late_cancel明确带FRAME2510，故其五项增量不覆盖漏帧路径；原件与已签其他组保留，不复跑。

1. **输入版本升级而非悄悄补默认值**：新manifest/contract/calendar采用V2，五种artifact角色不变，calendar本体新增独立timebase与epochs。请求的cycle/epoch、输入停止/复位时刻及全帧列表必须在读trace前冻结并按manifest SHA绑定；没有V2计划就拒收，禁止从trace间隔、观察到的FRAME或最后记录推导“期望帧”。833/834间隔检查仅是计划自洽检查，不证明48kHz物理频率或计划来源独立性，后者仍由M2核输入出处。
2. **同一真实截止帧、不同严格关系**：帧请求q的下一冻结帧为f；未返回的REQUESTED/ACCEPTED每条记录前必须cycle<f，RETURN/CANCEL或RESET清理未消费事务也必须严格早于f。已RETURNED结果可等待f，并在FRAME后同cycle CONSUME。833/834间隔精确由独立帧日历决定；不新增q+833上限，不把monitor/B2接受+833的另一合同套到D3。
3. **全局帧覆盖不依赖ledger存活**：每条普通记录、CANCEL、END、RESET前，若有应出现但周期已过去的冻结帧，先拒收；取消所有事务也不删除帧游标。FRAME逐项精确匹配(epoch/frame_id/cycle)，禁止只靠相邻trace间隔。RESET必须核完包括同拍的旧epoch到期帧，不作临时抑制豁免。END核完所有cycle<=END的应有帧；若全部事务和冻结请求已闭合，且原始`consumed>0/resets>0`等覆盖门禁仍满足，END早于下一帧可合法截断，不强迫等待最大规划窗末尾；因此早取消后END2513仍不能掩盖FRAME2510。全取消且consumed=0的窗口仍因原门槛拒收，本次不顺手放宽。
4. **同cycle保原顺序**：不排序、不补行、不改cycle。普通PA等可先于同cycle FRAME；FRAME必须先于依赖它的CONSUME。RETURN在到期拍无论排在FRAME前后都拒收；CANCEL/RESET同理不能靠排在FRAME前逃逸。END必须在同cycle应有FRAME及CONSUME之后。默认同拍旧FRAME/CONSUME先发生，再RESET；若实际Pro另有优先级，需M2事先明确合同后另议，不从trace选择豁免。若旧FRAME/CONSUME已按该计划完成，再RESET不应重罚已CONSUMED事务。

## 必须绑定的输入与路径

**仅拟议，尚未获准创建/执行**：

- 软件后继：`code/software/m3_pro_fourvoice_trace_20261016/D/d3_deadline_successor_20261017/ingest.py`；定向runner拟放同目录`run_deadline_delta.py`，不可沿旧runner覆写ROUND_01/02。
- 文档/原件：`code/docs/test/m3_pro_fourvoice_trace_20261016/D/d3_deadline_successor_20261017/`，一轮独占输出由M2绑定。此提案目录只存说明、schema及补丁文本。
- 输入schema详见SCHEMA_PROPOSAL.json。epochs须列每次reset、stop kind/cycle、所有预期FRAME与下一FRAME哨兵；末epoch的stop_cycle是最大可观察终点，不强制END恰等于它。requests仍保留旧epoch/req_id/cycle/lane_mask。下一帧可能在观察窗外，但其时间必须预先可知，不能由漏帧trace臆造。

本修订保持M2原合同：RETURN/CANCEL/未消费RESET<f、CONSUME=f。在834间隔，q+833仍早于f，可以合法取消/复位；在833间隔，同一年龄已经到期，必须拒收。若以后另有固定service budget需求，应另列待决并获许可，不植入本次最小补丁。补丁不改变M1数学、音频频率或生产接口。初稿曾误加统一q+833边界，已按总控纠正撤回，原文保留为R01_SUPERSEDED，见REVISION_HISTORY.md。

## 静态推演锚（均未执行）

| 条件 | 预期首拒收/合法性 |
| --- | --- |
| 原反例：req1677、漏FRAME2510、CANCEL2512/END2513 | 在CANCEL之前全局游标发现FRAME2510已过去，MISSING_FROZEN_FRAME；不会进入CANCELED。 |
| 取消1713合法，但随后仍漏FRAME2510，END2513 | 仍拒MISSING_FROZEN_FRAME；取消不能关闭全局采样时基。 |
| 未返回事务在任意普通PA记录cycle2510 | TRANSACTION_FROZEN_DEADLINE；即使该行不是FRAME/CANCEL也检查。 |
| req1677，RETURN1712，CANCEL2509，FRAME2510，END2513（计划一致） | 取消在严格截止前，帧未漏；仅静态预期可达结构接受，仍需实测。 |
| 同req，在833间隔第833拍RESET2510，事务未消费 | FRAME未出现先拒MISSING_FROZEN_FRAME_AT_RESET；帧出现但未消费则拒RESET_AT_OR_AFTER_FROZEN_DEADLINE；未返回状态可能更早由统一事务检查拒收。 |
| 834间隔的第833拍CANCEL/RESET，返回/取消状态满足原合同 | 仍<f，允许；不得套统一q+833边界。 |
| RETURNED跨834间隔，正确下一FRAME/CONSUME同拍 | 允许消费年龄834，前提返回已严格早于该真实f。 |
| 同cycle PA→FRAME→CONSUME→END且计划完整 | 不重排行，按原序处理；反序END→FRAME拒收，FRAME→RETURN到期拍拒收。 |
| END落在下一帧之后但没有任何在途请求 | 仍由全局帧列表拒收；EOF没有END同样不能作为隐式截窗。 |
| 全部请求已观察且终态闭合、原至少一次消费/复位门槛满足，END在下一帧之前 | 允许合法截窗；只核到END拍的帧，不要求将未来帧补进trace。全取消且无消费仍按原门槛拒收。 |

补丁是完整的文本差异草案，未应用到任何实际软件文件、未做语法或运行验证。还需M2批准准确后继路径、V2输入原件/manifest SHA、同cycle观察顺序及一轮软件CLI时间/次数额度，之后只跑上述有针对性的增量与相邻合法对照，不重跑C/D/E1–E4。保留旧源码、失败和全部旧消费记录。board_release_allowed=false；本轮功能执行0，不提交/推送、不回传消息，由总控主动读取本地结果。
