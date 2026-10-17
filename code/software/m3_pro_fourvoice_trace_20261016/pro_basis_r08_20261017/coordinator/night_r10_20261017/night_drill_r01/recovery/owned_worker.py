"""Owned LOCAL_SYNTHETIC recovery worker. No I/O occurs on import."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       allow_nan=False, separators=(',', ':')) + '\n').encode('utf-8')


def identity(file):
    digest, count = hashlib.sha256(), 0
    with Path(file).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
            count += len(block)
    return {'bytes': count, 'sha256': digest.hexdigest()}


def save(file, value):
    with Path(file).open('xb') as stream:
        stream.write(encoded(value))
        stream.flush()
        os.fsync(stream.fileno())


def load(file):
    with Path(file).open('rb') as stream:
        raw = stream.read(1024 * 1024 + 1)
    require(len(raw) <= 1024 * 1024, 'STATE_METADATA_BOUND')
    return json.loads(raw)


def run(mode, directory, token, seed_sha):
    directory = Path(directory).resolve()
    seed_path = directory / 'SEED.json'
    require(identity(seed_path)['sha256'] == seed_sha, 'SEED_SHA')
    seed = load(seed_path)
    require(seed['token'] == token and seed['origin'] == 'LOCAL_SYNTHETIC', 'WORKER_OWNER')
    state = directory / 'state'
    checkpoint_path = state / 'CHECKPOINT.json'
    if mode == 'prepare':
        state.mkdir(exist_ok=False)
        generation = state / 'generation_0001'
        generation.mkdir()
        key = seed['dedup_key']
        documents = {
            'IDENTITY.json': seed['identity'],
            'DEDUP.json': {'keys': [key], 'receipt_count': 1, 'advance_count': 1},
            'OUTBOX.json': {'items': [{'key': key, 'target_commit': seed['result_commit'],
                                      'state': 'PENDING_REMOTE_VERIFICATION', 'attempts': 1,
                                      'last_error': 'LOCAL_SYNTHETIC_UNKNOWN_RESPONSE'}]},
            'CONSUMPTION.json': seed['consumption'],
        }
        for name, value in documents.items():
            save(generation / name, value)
        checkpoint = {'schema': 'M3_OWNED_WORKER_CHECKPOINT_V1', 'token': token,
                      'origin': 'LOCAL_SYNTHETIC', 'generation': 'generation_0001',
                      'owner_pid': os.getpid(), 'worker_source': identity(__file__),
                      'seed_sha256': seed_sha, 'original_START': seed['identity']['original_START'],
                      'goal': seed['identity']['goal'],
                      'files': {name: identity(generation / name) for name in documents}}
        # Exclusive, fsynced pointer is the commit marker. Recovery never uses
        # uncommitted generation files if preparation was interrupted earlier.
        temporary = state / 'CHECKPOINT.prepared.json'
        save(temporary, checkpoint)
        os.replace(temporary, checkpoint_path)
        print(json.dumps({'checkpoint_committed': True, 'pid': os.getpid(),
                          'token': token}), flush=True)
        until = time.monotonic() + 20
        while time.monotonic() < until:
            time.sleep(0.05)
        raise TimeoutError('OWNER_DID_NOT_INTERRUPT_WITHIN_20S')
    require(mode == 'resume', 'WORKER_MODE')
    checkpoint = load(checkpoint_path)
    require(checkpoint['token'] == token and checkpoint['seed_sha256'] == seed_sha,
            'CHECKPOINT_IDENTITY')
    require(checkpoint['worker_source'] == identity(__file__), 'WORKER_SOURCE_CHANGED')
    require(checkpoint['generation'] == 'generation_0001', 'CHECKPOINT_GENERATION')
    generation = state / checkpoint['generation']
    documents = {}
    require(set(checkpoint['files']) == {'IDENTITY.json', 'DEDUP.json',
                                       'OUTBOX.json', 'CONSUMPTION.json'}, 'STATE_SET')
    for name, expected in checkpoint['files'].items():
        require(identity(generation / name) == expected, 'STATE_SHA:' + name)
        documents[name] = load(generation / name)
    require(documents['IDENTITY.json'] == seed['identity'], 'IDENTITY_RESET')
    require(documents['CONSUMPTION.json'] == seed['consumption'], 'CONSUMPTION_RESET')
    require(checkpoint['original_START'] == seed['identity']['original_START']
            and checkpoint['goal'] == seed['identity']['goal'], 'START_OR_GOAL_RESET')
    dedup = documents['DEDUP.json']
    require(dedup == {'keys': [seed['dedup_key']], 'receipt_count': 1, 'advance_count': 1},
            'DUPLICATE_RECEIVE_OR_ADVANCE')
    item = documents['OUTBOX.json']['items']
    require(item == [{'key': seed['dedup_key'], 'target_commit': seed['result_commit'],
                      'state': 'PENDING_REMOTE_VERIFICATION', 'attempts': 1,
                      'last_error': 'LOCAL_SYNTHETIC_UNKNOWN_RESPONSE'}], 'OUTBOX_RESET')
    report = {'schema': 'M3_OWNED_WORKER_RESUME_V1', 'origin': 'LOCAL_SYNTHETIC',
              'status': 'RESUMED_PERSISTED_STATE_NO_REPLAY', 'pid': os.getpid(),
              'interrupted_pid': checkpoint['owner_pid'], 'token': token,
              'identity': seed['identity'], 'consumption': seed['consumption'],
              'dedup': dedup, 'outbox': documents['OUTBOX.json'],
              'checkpoint': identity(checkpoint_path),
              'network_recheck': 'REQUIRED_BY_COORDINATOR_AFTER_RETURN',
              'App_restart_verified': False, 'machine_restart_verified': False}
    save(directory / 'RESUME_REPORT.json', report)
    print(json.dumps({'status': report['status'], 'pid': os.getpid()}), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('prepare', 'resume'))
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--token', required=True)
    parser.add_argument('--seed-sha', required=True)
    args = parser.parse_args()
    run(args.mode, args.directory, args.token, args.seed_sha)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
