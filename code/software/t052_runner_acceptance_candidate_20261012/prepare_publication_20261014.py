"""Publish existing T052 evidence without invoking the acceptance tools."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'code/output/m3_t052_host_capture_delivery_20261014_01'
DEST = Path(__file__).parent / 'PUBLICATION_20261014_R01'


def main():
    packet = SOURCE / 'T052_HOST_CAPTURE_EVIDENCE.zip'
    expected = '6b759a38e6e917a19d0932fe779f4f04bfcd3463ecec10b37a2520a688be1929'
    assert hashlib.sha256(packet.read_bytes()).hexdigest() == expected
    DEST.mkdir(exist_ok=False)
    shutil.copyfile(packet, DEST / packet.name)
    shutil.copyfile(SOURCE / 'SUMMARY.json', DEST / 'CAPTURE_SUMMARY.json')
    run = ROOT / 'code/output/m3_t052_host_capture_20261014_01'
    for name in ('receipt.json', 'actual_run_receipt.json', 'environment_precheck.json'):
        shutil.copyfile(run / name, DEST / name)
    for label in ('compile', 'run', 'check'):
        for stream in ('stdout', 'stderr'):
            shutil.copyfile(run / f'{label}.{stream}.bin', DEST / f'{label}.{stream}.txt')
    capture = DEST / 'captures'
    capture.mkdir()
    for path in sorted((run / 'work').glob('*_actual.jsonl')):
        shutil.copyfile(path, capture / path.name)
    assert len(list(capture.iterdir())) == 4
    text = '''T052 第4项：真实128沿采集交付（2026-10-14）

结果：CAPTURE_AND_CHECKER_PASS_PENDING_M2；T052保持PARTIAL。
机器：LAPTOP-KSS1MRR7。全新config/输出/消费标记，正式批准的沙箱外执行。
compile、VVP、checker各一次，全部退出0；分别0.078s、0.016s、0.594s。
分项上限90s，外层上限300s。checker=RTL_CONTROL_WINDOW_PASS。
7项输入、1014项工具身份前后SHA一致。checker原件未放宽，音频数学NOT_RERUN。
ledger：accepted=6、published=3、cancelled=3、open=0；reset_edges=4。
冻结DUT、ROM、128行计划和正式工程未改。observer修复reason前导空格，隔离测试同步收紧。
实现窗口按用户要求自审，未向审核员/预审员发送消息；最终复核归M2。

Config SHA256：d7140f0c4c3e294d4fc3de0edaf1aeae7dad874434616533ba3a53b7ec154433
完整原件包：T052_HOST_CAPTURE_EVIDENCE.zip
包SHA256：6b759a38e6e917a19d0932fe779f4f04bfcd3463ecec10b37a2520a688be1929
包内包含本次父子收据、实际命令/显式环境、原日志、四capture、源/工具前后SHA、消费标记、源码及控制器diff，并保留此前失败与compile-only诊断封存。
包外JSON、captures和日志txt为方便阅读的副本。原始字节身份以ZIP内文件及其SHA索引为准；Git依据仓库.gitattributes统一文本LF，不能把换行规范化后的Git文本SHA当成原运行字节SHA。
旧失败及compile-only诊断.vvp均未运行。当前仅为RTL仿真/控制窗口通过，未综合、PnR、STA或上板，不能回填旧4207条capture完整性。

发布边界：本目录是M3提供给M2的冻结证据入口。历史包内“未提交/未推送”属于封存当时状态；发布是否完成以实际Git提交及远端SHA核验为准。共享任务看板和当前状态由M2签收后登记。

给M2：请复核本次精确Git提交的observer/runner后继及ZIP实际证据，决定是否签收第4项；签收前T052保持PARTIAL。另请核定第5项T060的独立新执行许可，旧A/B许可已消费，不能复用。原准备0b5f453含177输入/621工具声明；请先决定是否compile-only诊断，再绑定最终工具/config、机器、次数与预算，随后核定A/B补采。T052和N32许可均不转用于T060。
待用户转发，尚未送达。
'''
    (DEST / 'M2_HANDOFF.txt').write_text(text, encoding='utf-8', newline='\n')
    index = {}
    for path in sorted(DEST.rglob('*')):
        if path.is_file():
            data = path.read_bytes()
            index[path.relative_to(DEST).as_posix()] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    (DEST / 'FILE_IDENTITIES.json').write_text(json.dumps(index, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(DEST)


if __name__ == '__main__':
    main()
