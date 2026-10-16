# D 夜间限定交付 — PARTIAL / 两组已消费

任务为双滑块最小隔离候选，输入HEAD `8b64a352464932a28df565038cafc8d623dea5c9`。
新候选确实例化原60K live/score/renderer和event/control CDC；三个独占写集，无Git写入、无EDA、无实物。
显示copy不反压音频，source/channel/note身份由原live实例保留；flash历史FAIL明确未修/禁用。

## 实际过程（全部原件保留）

| 目录 | 实际步骤/退出 | 组消费 | 实际结论 |
|---|---|---:|---|
| 首个delivery_r01 | 两次平台CreateProcess前拒绝 | 0 | 历史L0，旧包SHA不变 |
| run_night_01 | Python1，CREATE_SUSPENDED AttributeError；0个工具创建 | 0 | 软件预检失败；原固定L2标签错误，真实L0 |
| run_night_02 | iverilog版本0，vvp版本3221225595/0xC000007B；编译/产物仿真0 | 1 | 自有runner漏oss/lib，继承PATH含其他架构目录；不指认唯一DLL |
| run_night_03 | 两版本0、编译0、正例VVP1（t=0参数断言） | 1 | 仅原失败SHA编译通过，正例失败、负例未跑 |

工具合计6次启动：iverilog版本2、vvp版本2、compile1、产物VVP1；negative0、checker外部工具0、EDA0、硬件0。
两组真实消费均有不可覆写TOOL_CREATE_RESERVED/TOOL_STARTED，按夜间最多2组已耗尽，不再运行。
无超时，每工具90秒、每组300秒更严限制；每步原命令/cwd/环境/双流/退出/耗时在各目录。
各before/after输入与工具表逐字一致，run_night_02记录172项工具文件，修闭包后run_night_03记录438项；
后者仅增加所需lib直属依赖绑定，EXE未换、旧视觉/公共源未改。
版本实际为 Icarus Verilog/runtime 14.0(devel) s20260301-474-g5591c2dde-dirty，原stdout/stderr内留全输出。

## 增量修复与未验证边界

1. 新runner从未导出的Python常量改Windows flag0x4；0启动预检标签不再假L2。
2. 新runner局部PATH改为同tool的bin;lib;System32;Windows，排除继承的其他MinGW，前后SHA加入lib直属文件。
   下一组版本0支持“局部依赖环境修正有效”，不证明特定DLL唯一根因。
3. 新wrapper参数占位H-1/H违反原renderer静态范围断言；**工具额度耗尽之后只静态修**H-2/H-1。
   原renderer这两个参数仅断言引用，实际底边绘制用SCREEN_HEIGHT-1。原件不改，不关断言、不放宽checker。

原执行RTL SHA `42e3b795b80183e629746d16ac61e1883ee4eb30dc5530b0c72ab34ccce2cbfa`，
TB SHA `1ed079f600ef8d762fb131b0987d050a3ac248d053c99d6f25ee9865e7e40932`；
修后RTL身份另列CURRENT_IDENTITIES.json。原运行字节逐组stage保存；不能拿当前修后源替代原编译源码。

**当前源码未验证；D未完成。**最大实际证据为失败旧SHA编译通过（限定L1），模块运行失败、L2未通过。
无上飘/多来源/模式/下落/音频夹具正例PASS，四指定负例也没有运行，不能从写好的TB推出任何通过数。
音频部分仅独立48k调度夹具设计，不是R05/synth/PCM/I2S真链；没有真实音画capture或138K实屏。
不恢复旧attempt或运行旧残留vvp；已消费2/2，任何追加执行需新明确额度，夜间不再请求/等待。

## 移交

总控保留本包PARTIAL；次晨M2决定后续新执行额度与正式接入边界。
先在全新目录验证静态修后候选与四反例，基础R05同版签收后才讨论正式视觉合入/实屏。
原L0包及本夜失败包均提供文件本体、SHA及原流，不把发布当M2已签收。
待用户转发，尚未送达；board_release_allowed=false。
