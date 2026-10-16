# D/D2 10月17日限定结果

DONE_D_D2_FIXTURE；真实Pro对照仍PENDING。L1独立Python夹具，board_release_allowed=false。本窗口仅写D自有目录，未改coordinator/ingest、正式RTL或共享状态，未提交/推送；由夜间总控统一发布。

正例38000拍、44次请求/提交、16组手算PCM24边界、42个完整立体声帧（含两段启动零值）、88个完整半帧。40笔请求串行完整，最大请求到串行末位1673拍=41.825μs，仅为夹具数字结果。各epoch间隔833拍14次、834拍7次，连续三个间隔和2500；PA策略高有效、稳定指示8拍后开，均非Pro实测。

12个串行/期限/epoch/PA坏例均实际CLI exit1并符合首差异。首轮错位坏例已被拒收，但预期诊断写错导致整体exit1；修正后只续跑11个未完成组。所有首失败和源码原件保留。源码漂移门禁已补，三个历史轮前后源码一致。

复位审计明确：epoch0 ID21已采样串行未完、ID22已提交未采样，均在19001拍被复位取消；epoch1 ID21串行尾、ID22下帧采样因END未知。旧正例RESULT保持原样，修正见round_3/cases/RESET_DISPOSITION_AUDIT.json；新增helper已定向验证，没有以最终checker重复原13组。

C只读身份crosswalk保留76个lane ID（71消费、5取消），映射18组已有诊断串行请求，5个新映射坏例拒收。映射按epoch内消费帧序号，原C/D拍号分开；诊断PCM与音符无数学关系，不签C→PCM算法、共同执行时间轴或真实Pro请求身份。

消耗3/4轮，真实功能用时6.641000秒；round exits=1/0/0，均无超时。Python预检另0.656000秒。Icarus/ModelSim/Gowin/STA/硬件均0；D3仍由总控管理。剩余额度不自动消费。

当前仓库HEAD b6f289110a0b7341f1f9234c945bcb8d31d95aff；M1旧R05五目录已发布，Pro source/ROM/top/trace仍缺。输入更新不触发旧专项重跑。未验项包括真实Pro数学/期限/PA、同版物理时序、Bank与模拟/板测。M2/M1真人交接由总控提供，待用户转发。

入口：NIGHT_RUN_RECEIPT.json、FIXTURE_CONTRACT.md、各round的LAUNCH/CONSUMED/RUN_RECEIPT、round_3身份表。封包以LATEST_RECEIPT.json为准；含原捕获本体、失败原件、每轮源码、输入快照、SHA清单和CRC验证。
