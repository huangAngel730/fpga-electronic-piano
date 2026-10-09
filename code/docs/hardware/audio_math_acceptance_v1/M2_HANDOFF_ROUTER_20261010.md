# 给M2：T060四声部路由参考层新交付

待用户转发，尚未送达。提交/推送结果以本轮最终通知中的实际Git号为准；本文件形成时未宣称已推送。

M2，M3已按A2复核剩余范围补齐当前冻结4voice事件路由参考层：仅用原R/E/K/J和只读ROM，
独立导出分配/LRU、generation、source/channel CC64延迟释放、N/Q及准确off边沿；
包络release_done驱动回收，不再拿观测N/Q/STATE off喂expected。
两个off准确推导为epoch1 cycle1023197 lane1和cycle1254337 lane3，与原记录一致。
正常capture的14N/2488Q/2487tick/9964STATE及完整DDS→包络→ROM→增益→混音→PCM精确匹配。

新增16自检（含独立非零包络4800tick回收）＋既有44项，原56指定反例，新增6定点错误和2个
可执行Python行为变异；实际数字、原日志/退出码、源/输入/产物SHA和门禁见新receipt/manifest。
不称新的RTL仿真或生产修改；真capture没有回收完成，只有模型合成回收证据。
M2先前确认的observer计数分类/generated TB身份已写新收据，不重复申请、不改旧证据。

完整runner保留exit3、A1/A2/T060 complete=false，状态ROUTER_AUDIO_MATCH_AWAITING_M2_CLOSURE。
请复核路由独立性和当前冻结数学的有限收口；5个END计数/2条fixture标记仍未独立可推导，
新frame与MATH重叠未在原轨迹覆盖，模型显式拒收。未重复音频RTL/Gowin、旧夜间或设备动作。
本次仅A三处，未改M1/生产/ROM/工程/公共接口/共享登记，T061与32音状态未扩签。

请转发 `ROUTER_CLOSURE_20261010.md`、`ROUTER_EVIDENCE_MANIFEST_20261010.json`、
`ROUTER_EVIDENCE_20261010.json.gz.b64` 以及输出目录生成的 `M3_T060_ROUTER_20261010.zip`。
ZIP含本次源、复现文档、原日志/收据、6完整错误输入和两执行变异；原56输入按SHA沿用双方原封存包，
ZIP不重复搬运全部历史包。没有新增安装、烧录或接线许可。
