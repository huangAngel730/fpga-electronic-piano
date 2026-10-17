# 给M2的精确返修准入请求（尚未获准）

请仅对D3漏FRAME＋超期CANCEL/END和相邻RESET/同cycle边界确认以下绑定，不扩大至其余已核组。

1. 采用夜间2的唯一后继路径提案：`code/software/m3_pro_fourvoice_trace_20261016/D/d3_deadline_successor_20261017/ingest.py`及同目录`run_deadline_delta.py`；输出`code/docs/test/m3_pro_fourvoice_trace_20261016/D/d3_deadline_successor_20261017/ROUND_01/`。夜间5缺件表中的另一目录名只是独立初步建议，总控不采用；以上后继尚未创建。
2. 原D3源SHA `3217f97e57daec534306a213c64566fa111e3116f15a15967ca881847c218e07`只读。唯一有效补丁文本SHA `e89443c8a852288c27f04a5cdecb2bfa4e8722123845a4bc3c974b1dd887815a`；SCHEMA_PROPOSAL.json SHA `9e7b9bf118721f3050b5f0a306d466a49727e00f50479e68d447bd0391709ee1`。三个R01_SUPERSEDED文件为已撤回历史。
3. 独立定向输入规格CASES.json SHA `8bf7e0918fa5ceccab1d187c625a1cd3a4f97d282207c8e48ab56235eabb3bcb`，16项，5合法/11拒收，全部未运行。此文件是输入设计包装，不能直接交给旧V1 CLI；请确认按显式profile和原顺序展开、将计划内reset截窗和窗外下一帧哨兵固定为V2 epochs，保留同cycle偏序，不能从被检trace反推。实际五角色source/rom/contract/calendar/trace与manifest必须在执行前生成并封存大小/SHA；合成source/ROM只能标SYNTHETIC_FIXTURE。
4. 先批准上述隔离写集与V2合同，使M3能落地当前补丁、定向runner及输入适配；之后以实际生成的源码/runner/manifest SHA、精确argv/cwd再绑定执行。建议仅一组16项定向Python CLI，总墙钟≤90秒、单例≤5秒，独占ROUND_01，首个非预期结果即停；如需返工后续轮另核实际变化，不恢复旧六轮。此处是申请上限，目前新执行额度仍为0。
5. 使用Python `C:/Users/songdongkuan/miniconda3/python.exe`，既有3.12.4/EXE SHA `4e5a83fcdcd12bcb9ae4dc98c5405effe35dc5ac10d89982c6a6a3646493f88a`在执行前现场再核。只读decoder SHA `da91462e8421719e09ffab60d7bbe38d4ee05ac1793ea70e1f09c7a69ccda0cb`。不新增仿真/EDA/设备许可。

截止语义：RETURN/CANCEL/未消费RESET<f，CONSUME=f；f是独立下一真实帧。834间隔的年龄833仍可合法取消/复位，不能套monitor的接受+833。全局FRAME义务独立于事务状态；END/RESET只按预先冻结输入关闭窗口。允许事务已闭合后的合法早END；默认同拍旧FRAME/CONSUME在RESET前履行，例外需M2显式冻结。

M2核的是本次具体增量，不重跑旧C/D/E1–E4。D3合成软件返修无需等Pro商业许可/板卡；真实Pro同源/数学/物理/实物准入另行保持PENDING。待用户转发，尚未送达。
