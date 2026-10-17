# 夜间任务2：D3静态修法提案已齐套

状态：DONE_STATIC_PROPOSAL / NO_ACTIONABLE_EXECUTION_PENDING_M2。当前有效材料为REVIEW.md、SCHEMA_PROPOSAL.json、REPAIR.patch.txt；仅补丁文本，未应用或执行。拟议软件/原件后继为D/d3_deadline_successor_20261017，尚待M2绑定写集、V2输入和当轮CLI预算。

核心修法：下一真实帧f来自读trace前冻结的独立帧日历，RETURN/CANCEL/未消费RESET严格<f，CONSUME=f；每条记录均检查期限与独立全局帧游标，取消不移除帧义务，END/RESET不能抹掉同拍/已到期FRAME。保留同cycle行序与合法早END；早END仍须满足原至少一次消费等覆盖门槛。833/834依独立f区分，不新增q+833规则。

原D3 SHA256 `3217f97e57daec534306a213c64566fa111e3116f15a15967ca881847c218e07`未变。原109–124、164–168、130–132、103行分别定位FRAME驱动due、CANCEL、END和RESET<834兜底漏洞。旧R02五项增量只读引用，late_cancel包含FRAME2510，未覆盖漏该帧后CANCEL2512/END2513。修订前误加固定833规则的初稿已撤回并保留R01_SUPERSEDED，见REVISION_HISTORY.md。

本轮实际等级L0_STATIC_ONLY，功能执行0，无被审CLI/import、语法/运行检查、RTL/EDA/硬件；表中结果均为静态预期，绝非PASS。只读子智能体复核本次差异，未发现其他具体旁路；其早END文字歧义已澄清。旧源码/原件、正式工程、M1模型、共享状态/index未修改，不提交或推送，不发送消息。D3仍PARTIAL/REWORK_REQUIRED、board_release_allowed=false；由总控读取本地材料，M2决定后续许可。
