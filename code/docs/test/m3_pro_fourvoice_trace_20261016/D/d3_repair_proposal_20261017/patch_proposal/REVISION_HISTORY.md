# 静态提案修订留痕

- R01：初稿加入`min(q+833,f)`，误把monitor/B2的固定服务边界带入D3下一真实帧合同。总控指出这是未经授权的口径扩张。该稿未应用、未执行；保留REPAIR_R01_SUPERSEDED.patch.txt（SHA256 f5ee284d59dffa81be2a7686ae7e4878e8bcf78338855b1f5ddb1dd0e60274f8）及同名REVIEW/SCHEMA历史，全部作废，不用于实现或病例预期。
- R02（当前）：删除统一q+833规则与service_budget字段。只使用独立下一真实帧f：RETURN/CANCEL/未消费RESET<f，CONSUME=f。同时保留全局帧义务独立于事务终态、RESET同拍不能抹帧、合法早END和原trace行序。只读自审发现早END文字未提原`consumed>0/resets>0`门槛，已补明，不扩大为全取消无消费也可通过；代码原门槛保持。
- 当前有效文件仅REVIEW.md、SCHEMA_PROPOSAL.json、REPAIR.patch.txt；R01_SUPERSEDED只作失败设计历史。所有版本功能执行0、没有语法/CLI/运行验证；静态推演不是实际PASS。D3原件SHA3217f97e…18e07不变。
