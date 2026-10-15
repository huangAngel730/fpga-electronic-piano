# M3 N32 延迟重放：仓库输出目录门禁修正

原提交 `56e3cd6` 把五份原始结果追踪到了 `code/output/m3_n32_delay_replay_20261015_r04/`，使 `check_repo.ps1` 的 `Forbidden tracked files` 失败。M2 只将同一五份文件**按字节复制**到本目录并从 Git 索引移除旧路径，未改结果、SHA、收据或 M3 原始提交；本地旧输出保留，Git 历史可按原提交取回。原 `transfer/TRANSFER_RECEIPT.json` 的 `path` 是生成时的历史位置，交付请用本目录的同名 ZIP，并按收据原 SHA `d3a5ec86aa96ce573a2466a2e702dba25d8a1bb2a09c9911479d4976bbd7dff5` 独立核对。此处仅修发布位置，不复核 N32 功能或扩大其签收等级。
