# T058 夜间观察桥＋波形联合验收

执行日期：2026-10-08（Asia/Shanghai）。M3自审；待M2复核，未替M2签收或取号。
任务来源 cb6e08c；冻结功能 a17803c / 4739e39 / dd689ec 全部10项 SHA 开始/结束核对一致。
业务 RTL、公共包、CDC源、旧 TB/runner/证据、原 L/ROM、顶层/约束及共享状态均未修改。
新增目录仅 night_blackbox_20261007 与本报告子目录。

## 实际结果

Icarus14.0(devel s20260301-474-g5591c2dde-dirty)，真实 RTL。
每例 compile0、run0，独立 Python checker 对正向 exit0：

| 输入 | 采集/送达样本 | 完整扫描帧 | 逐像素比较 | 完整窗/发布 | Python扫描行 |
|---|---:|---:|---:|---:|---:|
| 封存A normal | 5849/5849 | 12 | 5,040,001 | 2/2 | 6300 |
| 封存A diagnostic | 41/41 | 1 | 420,001 | 0/0 | 525 |
| synthetic压力 | 10500/10343 | 14 | 5,880,001 | 4/3 | 7350 |

正向合计 **11,340,003** 次像素比较；Python独立计算 **14,175** 行实际输出hash。
每例最后多采1个下一帧起始像素，不把它算完整扫描帧。
封存A的SHA及每两个输入样本间隔均核对，未改变源帧周期凑PASS。
压力队列峰值32；公开满队列丢显示155包，另2个观测在分支复位未完成时不入队，
公开source_reset_done已捕获。桥目的包逐项核源payload、入队身份、顺序、无重复/跨branch。

pixel停钟→恢复出现gap，gap清部分窗、旧完整窗保持；显示复位及音频复位后重新得到
连续2048包快照。显示复位不归零音频观察seq，音频复位回FIRST_SEQ，u32近回绕覆盖。
恢复最后trace_valid=1；final gap0是音频复位后的计数，不冒称过程无gap。
frame_summaries封存每帧快照首尾seq/512列minmax SHA；gap时不拼接，发布只在帧边界，
逐像素比较含所有消隐、固定区域与2拍mask/RGB。最后一帧也包含真实轨迹。

两wrapper反例各 compile0/run完整0：交换左右→checker1 PIXEL_REFERENCE；
错seq→checker1 STATE_REFERENCE。每反例14完整扫描帧，不以编译错误冒充语义拒收。
空、截断、错计数、错像素capture分别被非零拒收。
正式本轮277.937秒，最长单仿真68.406秒，未超600/1800秒上限。

## 命令与交付

```powershell
python -B -X utf8 code/tb/input/pcm_waveform_candidate/night_blackbox_20261007/run.py --output code/output/m3_night_wave_NEW
```

本机实际输出 `code/output/m3_night_wave_20261008_002446`。
原编译/运行/检查命令、退出码、耗时、向量和源/产物SHA在evidence/original_receipt.json。
最终 checker 又以交付源码复查全部5个capture，日志与摘要在final_checks.json；
逐帧摘要的增加不重写原receipt。原capture以gzip+base64轻量封存，可解码重算raw SHA；
全量原capture/向量也提供独立转发ZIP。delivery_manifest.json列新增文件SHA。
原stdout/stderr及receipt同时以.gz.b64保存逐字节原件，raw_log_manifest核raw/carrier SHA；
可读JSON视图按仓库.gitattributes统一LF。被忽略的原.log只在ZIP，不列为Git缺失文件。

首两轮新TB/oracle存在启动X复位记录及把reset未完成的O误判为满队列标志错误，
分别保留旧output失败收据；仅修正新增测试台和公开捕获口径，不改冻结源，不计业务BUG。

仓库 `check_repo.ps1`：9/9 PASS、exit0，131.750秒。raw stdout/stderr与gate_receipt封存。
其子链历史正弦/三角ROM相对路径readmemh ERROR仍实际出现，虽然脚本总PASS；
gate_child_context和三个原子日志如实保留。不修其他模块、不外推全音色通过。

## 未测边界

本轮L2＋限定L3独立参考比较：不代表实体HDMI、物理CDC/MTBF、音频隔离、综合/PnR/STA。
未更换L、未重跑Gowin、未安装、未烧录、未接FPGA。整机CDC/STA/音频门禁仍归M2。
waveform_enable固定启用，背靠背valid的极限吞吐本轮未另外新增；原独立专项结论不重复扩张。
共享登记与复核收口由M2完成，本次不写任务看板/当前状态。

推送前fetch发现M2已发布5254567/6231470复核：原独立reference.py存在END+1及合法
定向PCM错输入误收，待最小返修。本夜间新增联合checker严格核精确END与A输入身份，
但不等于修复旧入口。本轮按用户冻结/只新增要求未改旧reference/runner；旧入口漏洞与
M2提出的后续返修仍保留，不能用本轮PASS关闭T058完整签收。
