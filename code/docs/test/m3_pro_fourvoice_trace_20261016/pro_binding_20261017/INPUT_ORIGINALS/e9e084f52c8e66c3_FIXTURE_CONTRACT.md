# D数字出口独立夹具合同

范围：`D_PT8211_FIXTURE_V1`，`ISOLATED_PYTHON_FIXTURE_NOT_PRO_DUT`。这是一份输入驱动的Python模型及独立pin decoder，无RTL执行。输入以各轮`INPUT_PLAN.json`为准，黄金是16组显式手算边界，不能代替M1算法签字。

- 夹具sys_clk假设40MHz。32位NCO步进659706977，每128次翻转产生一立体声帧；闭式独立日历从active_start推导frame_tick，逐沿检查833/834与连续三个间隔和2500。
- 每帧64个BCLK上升沿、每半帧32位，前16位零、末16位有效，MSB先发；WS低右/高左。DIN与WS仅在BCLK下降沿更新，上升沿采样；BCLK半周期6/7拍、完整周期13/14拍。
- PCM24为有符号24位。先在增长位中加128，再算术右移8位并饱和到[-32768,32767]；半LSB向正无穷舍入。左右非同值、负数及正负满幅均入手算表。
- TICK记当拍状态更新前的信号；frame_tick选择已有pending，否则hold；request在frame_tick后一拍；夹具commit在frame_tick后32拍，提交到下一真实frame_tick前必须完成。第一次输出为启动零值，不能当作已验证某个非零请求。
- epoch0复位拍1..6，epoch1复位19001..19004；所有外部数字输出在复位中为零。旧pending/request不进入新epoch。
- PA_EN高有效、clock_stable连续8拍后开，仅是本夹具候选数字策略。clock_stable不是Pro实际PLL/PCM稳定原件，8拍不是实物功放等待时间；未签电气极性或稳定音频。
- 每笔记录epoch/id、request/commit/sample/串行末位；已知复位取消和END观察尾分开。仅完整立体声结果计算request到串行末位，不以完整半帧补签另一半。

字段集合由check_fixture.py的FIELDS固定，拒绝多字段、缺字段、重复JSON键、非整数和x。header含schema/origin/clock_hz；END必须严格等于38000拍和最后epoch。拒收结果为CLI exit1与first_difference，正例exit0。

round_3的C_IDENTITY_LINK是独立身份表：C每epoch内被消费帧按序映射D已验证的请求ID1..N，一个帧保留多个lane身份；取消lane无D目标。C与D原拍号分别保留，PCM仍取D手算向量，未验证C音符求和、真实Pro身份映射或共同因果延迟。

复现命令保存在每轮LAUNCH/CASE_RECEIPT中。原轮目录为不可覆盖的消费记录；回放应使用封包内该轮sources及新输出目录，不能原地重写旧round。当前已成功组不在本夜重复执行。
