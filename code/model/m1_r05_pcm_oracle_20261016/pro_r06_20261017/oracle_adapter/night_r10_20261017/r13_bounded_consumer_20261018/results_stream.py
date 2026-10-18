"""All audits are sidecars; only a bounded summary is serialized at the end."""
import hashlib
import json
import os
import shutil
from pathlib import Path
from identity_guard import require


class Budget:
    def __init__(self, root, *, output_cap=4 << 30, scratch_cap=4 << 30,
                 total_cap=56 << 30, reserve=8 << 30):
        self.root = Path(root).resolve()
        self.output_cap, self.scratch_cap, self.total_cap = output_cap, scratch_cap, total_cap
        self.reserve, self.written, self.scratch_reserved = reserve, 0, 0

    def check_disk(self, extra=0):
        # Every created file, part and SQLite sidefile in the frozen run root counts.
        total = sum(((p.stat().st_size + 4095) // 4096) * 4096
                    for p in self.root.rglob('*') if p.is_file())
        require(total + extra <= self.total_cap and shutil.disk_usage(self.root).free
                >= self.reserve + extra, 'DISK_BUDGET_EXCEEDED', status='RESOURCE_LIMIT')

    def reserve_output(self, size):
        require(self.written + size <= self.output_cap - (8 << 20),
                'OUTPUT_BUDGET_EXCEEDED', status='RESOURCE_LIMIT')
        self.check_disk(size + 4096)
        self.written += size

    def reserve_scratch(self, size):
        scratch = sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file()
                      and (p.name.startswith('lifecycle.sqlite') or p.name.startswith('etilqs_')))
        require(scratch + size <= self.scratch_cap, 'SCRATCH_BUDGET_EXCEEDED', status='RESOURCE_LIMIT')
        self.check_disk(size)


class Audit:
    def __init__(self, root, budget):
        self.root, self.budget = Path(root), budget
        self.channels = {}

    def append(self, channel, obj):
        require(channel in {'clock', 'action', 'comparison', 'epoch', 'request',
                            'accepted', 'configuration', 'fx', 'cancellation', 'result_accept'}, 'AUDIT_CHANNEL')
        raw = (json.dumps(obj, ensure_ascii=False, separators=(',', ':'),
                          allow_nan=False) + '\n').encode('utf-8')
        require(len(raw) <= 65536, 'AUDIT_LINE_LIMIT')
        if channel not in self.channels:
            file = (self.root / (channel + '.jsonl.part')).open('xb')
            self.channels[channel] = [file, hashlib.sha256(), 0, 0]
        item = self.channels[channel]
        self.budget.reserve_output(len(raw))
        item[0].write(raw)
        item[1].update(raw)
        item[2] += 1
        item[3] += len(raw)

    def seal(self, summary, identities_complete):
        require(identities_complete, 'FINAL_INPUT_IDENTITY_MISMATCH')
        descriptors = self.close()
        result = {**summary, 'sidecars': descriptors, 'schema': 'M1_R13_STREAM_RESULT_V1',
                  'real_verified': False, 'math_verified': False, 'board_release_allowed': False}
        raw = (json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
        require(len(raw) <= 1 << 20, 'RESULT_SUMMARY_LIMIT')
        self.budget.reserve_output(len(raw))
        path = self.root / 'RESULT.json.part'
        with path.open('xb') as file:
            file.write(raw)
            file.flush()
            os.fsync(file.fileno())
        path.rename(self.root / 'RESULT.json')
        return result

    def close(self):
        result = {}
        for name, item in self.channels.items():
            if not item[0].closed:
                item[0].flush()
                os.fsync(item[0].fileno())
                item[0].close()
            result[name] = dict(path=name + '.jsonl.part', rows=item[2], bytes=item[3],
                                sha256=item[1].hexdigest())
        return result


class AppendSink:
    def __init__(self, audit, channel, decorate=lambda obj: obj):
        self.audit, self.channel, self.decorate = audit, channel, decorate
        self.count = 0

    def append(self, obj):
        self.audit.append(self.channel, self.decorate(obj))
        self.count += 1

    def __len__(self):
        return self.count
