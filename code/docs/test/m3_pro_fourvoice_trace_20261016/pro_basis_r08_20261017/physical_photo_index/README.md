# R8-19 实物原图索引

状态 PREPARED_NOT_RUN；本项六例只进入总控 H 组合组，不能单独运行。代码入口为同名 software 目录 `m3r08_19.py --request REQUEST.json --output NEW_OUTPUT_DIR`，输入格式见 INPUT_SCHEMA.json。

每份原件由 path/bytes/SHA 绑定；声明值逐项关联 evidence_id、从 1 开始的页号及区域说明。PNG/JPEG/WebP 仅检查文件格式起始特征，不等于验证画面内容；本工具没有 OCR、原图真实性或板卡型号签收能力。照片与测量必须指向同一 board_id。

`REAL_INPUT_GAPS.json` 如实记录尚无实物原图与同板测量。它不是运行请求。参考文档和合成夹具不能满足真实原图项；即使结构齐全，REAL_CANDIDATE 仍待人工确认完整料号/version、核心板/Dock、Bank与会话。

机器输出 physical_photo_index.json 保留文件身份、逐项链接和缺件；real_pass、physical_identity_signed、board_release_allowed 均为 false。未执行软件、综合、时序或上板验证。退出码遵循 ACCEPT=0/PENDING_UNKNOWN=3/REJECT=2。
