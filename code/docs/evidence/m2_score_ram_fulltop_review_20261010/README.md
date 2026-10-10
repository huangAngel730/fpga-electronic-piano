# 精确 RAM 全顶层功能证据

`EVIDENCE.zip.b64` 解码为 633,405 字节 ZIP，272 个成员，SHA256 `840eb96bb0dbe8494e10af94167e8090e3b46490b7065a10e87fe7c9bb90560b`；MANIFEST.json 列各成员原始 SHA。所有真实执行输入与编译副本在 source_objects 按 SHA 去重存储，qualification_summary 的 source_index 保存各运行原路径与对象身份；不包含工具可执行文件，保留实际版本日志和二进制 SHA。完整 v2 准备工程、ROM、constraints、收据、四组有效运行日志/capture/向量均保留。

02 为精确新工程正例，compile/sim/check=0，13场景/12回复/3事件，音频1962509和像素1226567比较一致，总868.283秒。01回复负例、03音频负例、05独立参考视频负例为三项实际可编译行为拒收；04共享显示参考初试无效，保留日志和中断观察，不算有效负例或通过。source/index 原始 SHA 不回填。

software_synthetic 为明确标注的解析器/资源层级损坏自测，只有软件L1；本包功能实际L2/限定对照L3，没有综合/PnR/STA/实屏或设备证据。最终仓库门禁另以 FINAL_PUBLICATION_GATE 载体封存，不能用本包自身或历史门禁替代发布门禁。
