# chat8 RESUME_R02 来源核账

此目录只读核验夜间 A 生产者与 C 消费者的既有原件。它检查实际文件字节、工具与源码身份、三次 ModelSim 调用的六份功能流、创建／消费标记、253456 沿捕获，以及 C 命令和结果对 A 回执／捕获的精确绑定。

工具不会运行 ModelSim、Icarus、Gowin 或硬件，不判断 PCM 数学，也不修改 A/C 原件。输出最多是 L0 静态身份加软件核验结果；本轮没有执行 HDL lint／编译，因此不记 HDL L1。

从仓库根目录运行：

```powershell
python -B -X utf8 code/software/m3_r04_receipt_audit_20261015/chat8_provenance_20261016/provenance_audit.py `
  --a-root code/docs/test/m3_r05_functional_integration_20261015/night_20261016/RESUME_R02 `
  --c-root code/docs/test/m3_40mhz_pcm_i2s_latency_20261015/night_20261016/RESUME_R02 `
  --output code/docs/test/m3_r04_receipt_audit_20261015/chat8_provenance_20261016/PROVENANCE_RESULT.json
```

输出路径必须不存在。自报回执和 manifest 只能证明封包内部字节一致，不能独立认证历史进程确实发生；该限制会明确写入结果。

带原始双流和前后身份的固定运行入口为：

```powershell
python -B -X utf8 code/software/m3_r04_receipt_audit_20261015/chat8_provenance_20261016/run_provenance.py `
  --output code/docs/test/m3_r04_receipt_audit_20261015/chat8_provenance_20261016/RUN_01
```
