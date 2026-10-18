"""R13 actual streaming consumer candidate. Only worker_group may admit it."""
import importlib.util
from pathlib import Path
import sys
from identity_guard import require
from stream_io import LogicalStream, small_json
from history_join import joined
from lifecycle_store import Store
from results_stream import Audit, Budget
from clocked_math_stream import make_engine


def frozen_module(root, desc, name, tick, held):
    # All executable dependencies here are bounded small source files. The same
    # verified buffer is compiled; no source reread after its identity check.
    from identity_guard import LockedInput
    require(desc['bytes'] <= 1 << 20, 'SOURCE_SIZE_LIMIT', desc['path'])
    stream = LockedInput(root, desc, 'source:' + name, tick)
    held.append(stream)
    source = b''.join(stream.chunks())
    path = Path(root) / desc['path']
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    module.__file__ = str(path)
    require(name not in sys.modules, 'MODULE_IDENTITY_COLLISION', name)
    sys.modules[name] = module
    exec(compile(source, str(path), 'exec'), module.__dict__)
    return module


def evaluate(job, root, output, bindings, tick, group_budget=None):
    require(job.get('schema') == 'M1_R13_STREAM_JOB_V1', 'STREAM_JOB_SCHEMA')
    require(job.get('profile') == 'C9_PIANO_TRIANGLE_NOTES_DELAY_CLOCKED_V1', 'MATH_JOB_PROFILE')
    require(job.get('mode') == 'SYNTHETIC', 'M2_EXACT_PROVENANCE_REQUIRED',
            status='PENDING_REAL_ADMISSION')
    require(job.get('missing_roles') == [], 'MISSING_ORIGINAL_ROLES', status='PENDING_INPUT')
    require(job.get('origin') == 'SYNTHETIC_SCHEMA_FIXTURE', 'JOB_ORIGIN_MISMATCH')
    output = Path(output)
    require(not output.exists(), 'OUTPUT_ALREADY_EXISTS')
    output.mkdir(parents=True)
    budget, held, streams = group_budget or Budget(output), [], {}
    audit, engine, store = Audit(output, budget), None, None
    try:
        metadata = {}
        for role in ('independent_plan', 'frame_plan', 'reset_edges', 'provenance', 'end'):
            require(role in job['artifacts'], 'MISSING_ORIGINAL_ROLES', role, 'PENDING_INPUT')
            metadata[role], stream = small_json(root, job['artifacts'][role], role, tick)
            held.append(stream)
        require(metadata['provenance'].get('origin') == 'SYNTHETIC_FIXTURE_NOT_RTL'
                and metadata['provenance'].get('capture_id') == job['capture_id'], 'PROVENANCE_CAPTURE_ID')
        geometry = job['geometry']
        require(type(geometry['row_count']) is int and 0 < geometry['row_count'] <= 1130662,
                'ROW_COUNT_LIMIT')
        require(job['finish_contract_frozen'] is True, 'FINISH_CONTRACT_MISSING', status='PENDING_INPUT')
        require(metadata['end']['cycle'] == metadata['frame_plan']['finish']['cycle']
                and metadata['end']['sampling_phase'] == 'POSEDGE_PRE_NBA', 'END_FINISH_MISMATCH')
        from independent_plan import ClockContract, validate_independent_plan
        plan = validate_independent_plan(metadata['independent_plan'])
        clock = ClockContract(metadata['frame_plan'], metadata['reset_edges'], geometry)
        legacy = frozen_module(root, bindings['entry_dependencies']['legacy_math'], '_r13_signed_math', tick, held)
        helper = frozen_module(root, bindings['entry_dependencies']['m3_stream'], '_r13_frozen_m3_stream', tick, held)
        dependencies = helper.dependencies()
        store = Store(output / 'lifecycle.sqlite', budget)
        engine = make_engine(legacy, plan, store, audit)
        caps = {'raw_capture': (4631191552, 4096), 'public_rows': (6946787328, 6144),
                'line_index': (578898944, 512),
                'row_index': (9262383104, 8192), 'fx_history': (2772992, 2048),
                'advance_history': (1384448, 1024), 'input_apply_history': (262144, 2048)}
        for role, (max_bytes, max_line) in caps.items():
            require(role in job['artifacts'], 'MISSING_ORIGINAL_ROLES', role, 'PENDING_INPUT')
            streams[role] = LogicalStream(root, job['artifacts'][role], role,
                max_bytes=max_bytes, max_line=max_line, max_rows=1130662, tick=tick)
        for row in joined(streams, job['capture_id'], helper, dependencies, geometry):
            tick()
            require(row['source']['reset_edges_sha256'] == job['artifacts']['reset_edges']['sha256'],
                    'RESET_EDGE_SOURCE_SHA')
            clock.row(row['fields'])
            engine.row(row['fields'])
        clock.complete()
        result = engine.finish()
        require(engine.counts['result_accepts'] > 0, 'NO_ACCEPTED_MATH_SAMPLES', status='PENDING_INPUT')
        for stream in streams.values():
            stream.final_verify()
        for stream in held:
            stream.verify()
        store.close()
        store = None
        tick()
        return audit.seal({**result, 'status': 'SOFTWARE_MATCH_STREAM_COMPLETE',
            'capture_id': job['capture_id'], 'level': 'L1_SOFTWARE_ONLY',
            'hash_bytes_by_role': {role: sum(x.hash_bytes for x in stream.inputs)
                                   for role, stream in streams.items()}}, True)
    except BaseException as error:
        # Fail on the first error. Never drain inputs after a mathematical error
        # merely to manufacture EOF or a complete-result marker.
        partial = dict(status=getattr(error, 'status', 'CONTRACT_REJECTED'),
            code=getattr(error, 'code', type(error).__name__), detail=str(error),
            first_difference=getattr(engine, 'first_difference', None),
            terminal_match=False, real_verified=False, math_verified=False)
        audit.close()
        from stream_io import canonical
        failure = canonical(partial) + b'\n'
        require(len(failure) <= 1 << 20, 'FAILURE_RECEIPT_LIMIT')
        (output / 'FAILURE.json').write_bytes(failure)
        return partial
    finally:
        if store is not None:
            store.close()
        for stream in streams.values():
            stream.close()
        for stream in held:
            stream.close()
