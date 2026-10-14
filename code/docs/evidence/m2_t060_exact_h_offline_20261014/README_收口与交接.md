# T060原H离线验收收口

2026-10-14，依据用户明确要求「完成T060」。本次实际执行新的独立编译诊断和新的A/B补采，不沿用或恢复旧消费许可。业务RTL、ROM、数学模型、原捕获、旧失败、残留A.vvp及用户当前未提交修改全部保持。

## 实际结果

- 独立compile-only：30原输入、281原工具依赖绑定，一次实际编译退出0，全流程34.625秒，在90秒上限内；未运行旧残留vvp。新编译结果只作诊断，不用其成功代替音频验收。
- 新A/B配置：本机LAPTOP-J2NSUAK1，177原输入逐字节与封存相同，1399实际工具/运行时文件绑定；新config SHA `3cbceb9d04e4e55c16cc8094da502103cb710daa1388bd51bd9cb4a91bf977bb`，独立新approval及ONE_SHOT_ATTEMPT。旧机器/工具差异明示，不冒复用旧许可。
- A/B共16实际步骤，入口0、289.343秒、所有工具未超时；A capture230.875秒，在300秒分项限内，全流程在900秒内。source与tools执行前后SHA一致，自动重试0。
- A：24586完整记录、4914提交；恰4800个Release推进tick后自然Idle/release_done、真实路由退休和occupied清除，再同身份NoteOn，generation1→2且非零PCM恢复。CC64/deferred之后panic真实握手接受，清pedal/key/deferred并进入Release，不把panic误写成立即清occupied。
- B：1595完整记录，四指定取消点均命中且旧代不提交；后继ID2/4/6/8正常提交，既有相位推进不回滚，HOLD反压旧结果保持。复位后epoch2新ID1在1571拍正常提交；共5次有效提交。
- 独立原checker实际逐记录/字段、定点数学和源码日历比较通过。checker结果中的new_RTL_run=false表示checker自身不启动仿真；本批真实运行来自受控runner实际capture步骤，不将软件输出当捕获。
- 四份完整损坏capture保持格式与END，分别按MINCLOSURE_RETIRE_IDENTITY、MINCLOSURE_PANIC_RELEASE、MINCLOSURE_CANCEL_OLD_ID、MINCLOSURE_ADVANCE_NONROLLBACK_MATH非零拒收。

## 收口范围

机器输出 `T060_OFFLINE_CLOSURE.json` 的状态为 `T060_EXACT_H_OFFLINE_ACCEPTANCE_SCOPE_COMPLETE`，`t060_offline_acceptance_complete=true`。含原H/capture2已签DDS/envelope/ROM/gain/mix/PCM、路由/严格结构和两计数证据REUSED，以及本次原H A/B真实功能补采。旧4207/56反例/原capture2数学未重跑，旧PARTIAL/exit3收据不改。

原capture2的3诊断END（control_stalls/center_samples/checks）和2精确fixture flag仍只排除其独立期望，不排除字段/类型/原值、身份/时序或PCM数学；不适用于新输入。这个明确批准的排除边界不是未完成的功能缺口，旧退出码仍保留为历史事实。

不签任意输入/无限长期演奏、L/newRAM/N8/N32生产音频、实际晶振与采样率、整机STA或实物验收；T061/N32及上板阶段继续独立保持未完成。不得将T060这个离线范围的完成扩成所有音频工程通过。

## 文件与发布状态

证据ZIP为294个数据成员，5327546字节，SHA `8514ffdabfa460d31054bbb0ac46d91b70c85c0eefe6cfe24348af21267bd2ad`，准确清单见 `DELIVERY.json`。含原真实日志/退出/捕获、冻结源和依赖清单、config/approval/消费标记、四完整反例及独立检查结果；工具/vvp二进制留原ignored输出，身份已绑定。

当前仅本地封存，`repository_registered=false`、`git_published=false`。正确M2工作区的Git发布此前被权限审核拒绝，当前D盘checkout旧且有用户修改，本轮不stash/reset/覆盖，也不借旧门禁冒签新树。恢复正确发布权限后，导入本次执行与收口原件、核精确树门禁、最后fetch取号并普通推送；本地离线结果不因尚未发布而写成没有执行，也不冒已经进入develop。

## 可直接发M3／M1

T060原H离线范围已由M2实际完成新的编译诊断和A/B唯一补采。16步/289.343秒/入口0，A24586记录4914提交及4800Release tick真实退休/重分配、panic；B1595记录四取消点及epoch2恢复全部与独立原checker一致，四完整反例指定拒收。旧失败/marker/原capture/数学证据不改，原3END/2flag精确排除保持。不要再执行旧或新同版A/B，不重复旧数学/56反例；本次新许可已经消费。T052沿自身许可/回传另处理；M1继续双音色＋延迟链，M3继续优化N32，波形不动。此结论仅T060原H离线验收范围，不签N32、整机物理STA或上板。包已本地齐套，尚未Git登记推送，待用户转发，尚未送达。
