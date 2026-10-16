# M1-B：视觉接入前后的音频帧合同比较

实现是纯 Python 的最小帧比较模型，仅占本目录与同名 `code/docs/test/` 新目录。它不采集数据、不调用 HDL/EDA/设备，也不修改 M3 的显示、observer 或 CDC 工具。

- `visual_audio_guard.py`：严格输入校验、完整窗口、逐帧零容差比较，拒收退出 2。
- `test_visual_audio_guard.py`：新建独占证据目录，运行有界定向 unittest；每个 CLI 子进程保留 argv/cwd、原始 stdout/stderr、退出码与 SHA。每例最多 10 s、软件套件总预算 90 s。
- 完整格式、样本相位及实际验证边界见 `code/docs/test/m1_visual_audio_guard_20261016/M1_B_软件比较合同与待采集字段.md`。

CLI：

```text
python -X utf8 -B code/model/m1_visual_audio_guard_20261016/visual_audio_guard.py --before BEFORE.json --after AFTER.json --contract COMPARE_CONTRACT.json --basis code/docs/test/m1_r05_pcm_oracle_20261016/REFERENCE_CONTRACT.json --output NEW_RESULT.json
```

`--contract` 必须是执行前冻结的独立期望窗口与身份，不能从两份来件共同截短后的窗口生成。`--basis` 按实际文件字节核 SHA；输出使用独占创建，已有输出拒收且不覆盖。相等只输出 `FRAME_CONTRACT_EQUAL`，不输出视觉接入 PASS。当前合成测试的实际状态是 `PENDING_REAL_CAPTURE`。
