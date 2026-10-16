# User authorization evidence and platform approval boundary

Read via Codex `read_thread` on 2026-10-16, source chat `01a14050-cd98-7c41-8004-5d3e25765167`, title 夜间任务1（夜间总控）, user message `01a140bb-f65f-7291-914b-cf694a39b81f` in active turn `01a140bb-b848-7bc2-bd01-12b017477407`.

Direct human instruction (excerpts):

> 你是夜间任务的总控 授权你总控对话 夜间任务2 夜间任务3 夜间任务4 你们四个一起联合做夜间任务
>
> 请读取 develop 上《M3_夜间八小时任务单_2026-10-15.md》，自行组织 A/B/C/D 不抢写的并行工作……只在已授权隔离范围内执行有界测试，受阻即封存并转其他包。
>
> 你可以调配他们 让他们用他们的子智能体协助他们完成任务
>
> 如果遇到问题 请尝试解决 解决方案超过3次没有成功就先跳过这个任务 稍微扩大尝试的余量（相比任务要求）
>
> Modelsim SE-64 2020.4软件版本已经得到M2的认可 可以使用 如果遇到无法仿真的情况 可以查看主对话2的内容 看看是如何解决的

This later direct user instruction follows an older completed read-only overlap query. The initial platform escalation was rejected because its review cited that older query and regarded the new authorization as untrusted assistant history. No escalated process was created. We subsequently inspected the human message above using the supported read-only chat tool, then re-request standard platform approval with this evidence. Rejection is never bypassed; if approval remains rejected, actual ModelSim capture stays blocked and only static/software work continues.

Initial RUN_01 was a restricted-environment preflight: vlib -help CreateProcess returned WinError 623, no process created, no functional commands, raw empty streams preserved. No old or new functional allowance was consumed. Initial failed source bodies are present for staged HDL; runner source was identified by SHA but not copied at that preflight (explicit limitation). Before later startup, snapshots are copied before tool probes.

Pre-execution self-audit fixed the new observation-only t=0 epoch handling (X-to-0 initialization is not an independent RESET record). Algorithms, ROM, original R05 and old validated/failure trees remain read-only.
