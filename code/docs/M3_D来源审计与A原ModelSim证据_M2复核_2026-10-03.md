# M3 D来源审计与A原ModelSim证据：M2复核（2026-10-03）

## 结论

- **D 26c6ab5 来源审计器就绪签收**：M2实际原公开入口37/37 PASS（7正向/30负向），所有输入运行前后不变。等级L0来源检查/L1审计器自检；没有最终工程审计、综合、PnR、STA或实物通过结论。
- **A d57467d 原M3仿真交付证据复核通过**：附件原21项文件SHA、evidence日志SHA、源文件身份、ROM值和4组编译/运行/反例日志核对，M2独立Python重算原capture覆盖与FCW完全匹配。
- A的RTL仿真由M3 ModelSim2020.4执行。本轮没有再运行RTL，原V0163关于M2独立RTL运行未完成的事实不改写；本次解决的是原仿真交付的证据复核，不把证据重算称作新M2 ModelSim通过。
- C状态按最新V0166：M1修正版已到M2，M2对原始修正版非零延迟核心已验；整包仍待两测试文件及说明最小补齐。M3本机是否已收到附件未确认，C继续等待M2提供补齐后的正式交接包/SHA，而非笼统重做核心验收。

## D源码范围及独立自检

提交26c6ab5aa98995d3854484955b9721f77a4da28a只新增runner、test_audit.py和README。
该提交已在当前develop历史中，附件旧M2_HANDOFF里“尚未推送”的说明被用户新通知明确替代，不安排重复推送。

```powershell
python -X utf8 code/tb/board/m3_integration_provenance/test_audit.py --output code/output/M3_A_evidence_D_review_20261003/D37_independent
```

实际exit0；全部37组真实调用公共审计CLI，正向7组exit0、负向30组exit1、expected/actual error一致，输入哈希前后不变。
正向覆盖生产合成夹具、D/E仓库根迁移、禁用缺源、显式隔离、批准生产快照、精确basename例外。
负向覆盖旧parser、未批准output候选、缺ROM、重复source/module、CST/SDC变化、严格CRLF、缺manifest/角色/来源/约束、哈希引用未固定、非法XML/重复JSON键、动态依赖、仅仿真ROM、加密源和旧报告覆盖保护。

源码检查：批准manifest与实测SHA分离，精确GPRJ路径一致、所有启用源和约束必须逐一列入；不按basename回退。Hash-ref要求元数据本身独立固定SHA。scope区分production/isolated，允许的生产stage逐文件批准，不自动将output候选改成production。
ROM/include解析为保守字面及参数检查，无法静态确定/加密HDL/VHDL拒收，不能替代厂商elaboration。CLI只exclusive-create新报告，不修改被审GPRJ/RTL/ROM。
这些边界如实保留，不能因37夹具通过就宣称最新47输入音画工程已审计。

当前没有最终批准manifest，故**本轮仅签收工具就绪，不运行或声称最终整合来源审计通过**。

## A原证据包身份

附件 `M3_A_original_ModelSim_d57467d_20261003_174922.zip` SHA：
`a87d88a7d1b31cea3ded95cb32b0fb52e6a0a51b7ce4f64e46be182e84073738`，与通知一致。
解包只到忽略output，逐项校验package_manifest21文件SHA及evidence记录日志SHA全部一致。
原capture SHA `c78ace3e34539949b5a553ea498059c913001725719f9f744899a153b423874a`。
所有非ROM source_SHA与本机待审源码字节相同。三ROM本机当前CRLF、M3附件LF，原始SHA分别保留；对50/1024/1024个十六进制字和标准LF文本逐项核对一致，没用静默规范化把raw digest写成相同。
首次身份检查仅检查一个换行转换方向而提前停止，未修改输入；补充双向LF/CRLF身份检查后通过，这不属于重跑A或改变ROM。

## M2独立原capture重算

读取M3原始positive/capture，不修改其字节，使用匹配SHA的已入库scoreboard与M1模型独立重算：

| 覆盖项 | 原capture重算 |
|---|---:|
|公共FIFO输入/接受事件|1270/1270|
|离散事件|235|
|请求/快照/计算|878/875/874|
|成功消费|858|
|身份/Program编号|256/128|
|非零控制声部结果|2899|
|1041/1042拍节奏请求|576|
|取消|8|
|结果背压/满FIFO同拍pop-push|46/151|
|控制读取反压/同拍write-through|4/1|

全部统计与原evidence逐键完全一致。原正向日志恰有一次PASS、Errors0；正向和三mutant编译日志Errors0。
原held_valid_lfo运行日志有明确LFO推进断言；live_base/corrupt_tag的原scoreboard日志分别检出FCW不符/错误请求标签。
对收到的**正向capture副本**另做三个数据反例：FCW改1LSB、request id改变、去END；均被当前记分板拒收。该反例是Python证据解析器检查，不冒称新RTL变异仿真。
两个scoreboard原mutant没有随包附其raw capture，故本轮仅核对原行为日志及hash，不声称重新从mutant capture计算了原负例。

本轮签收A原ModelSim交付证据，沿原源版本的L2/L3边界。A基于当时候选四槽控制和TB身份夹具，不能当作实际银行/PCM接入V0164或音画STA V0165已通过。
原V0163本机Icarus超时/旧ModelSim语法不支持的失败记录继续保留，不删除、不用capture重算替代那次工具执行结果。

## C、D、主线下一步

V0166原M1修正版f45744f7非零延迟60104周期/12968输出验证已经完成；原555场景测试仍228错。
M3 C不再重做B框架/重复该核心采集；等待M1应用显式reset_before生成器/TB与清理矛盾零延迟说明，精确SHA到件后做一次验收收口。
D工具无需重复开发；只有M2给出新最终GPRJ、批准来源manifest及选定角色后才做对应版本审计。
当前直接阻塞是V0165的parser长Setup路径、控制短Hold及Recovery，属于M3输入与M2控制复位职责；D/A签收不解除这些时序失败。

本轮只提交复核文档及共享状态，不改正式RTL、模型、GPRJ/CST/SDC或可视化。不派额外重复任务。

反馈待用户转发，尚未送达。

登记：D来源审计器就绪V0167；A原证据收口V0168补V0163，不改写旧运行历史；复核功能提交4f344da。

本轮发布门禁实际九项全PASS（142Python/T007/T019），仅文档状态更新。D原三文件、A源模型和收到的capture/ROM均未修改。
