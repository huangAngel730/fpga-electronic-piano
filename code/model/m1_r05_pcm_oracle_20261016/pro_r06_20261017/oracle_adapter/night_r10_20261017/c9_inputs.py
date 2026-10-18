"""Read M3's existing mechanical index and original files without projection."""
from pathlib import Path
import hashlib
import json
import re
import zipfile

from c9_math import MathIssue, PROFILE, integer, known, reject


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
MAX_FILE_BYTES = 512 * 1024 * 1024
ROLES = ('mechanical_index','public_rows','raw_capture','independent_plan',
         'frame_plan','reset_edges','provenance')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _pairs(items):
    value = {}
    for k,v in items:
        if k in value:
            reject('DUPLICATE_JSON_KEY',k)
        value[k] = v
    return value


def _nonint(value):
    reject('NONINTEGER_JSON_NUMBER',value)


def loads(raw, where):
    try:
        return json.loads(raw.decode('utf-8'),object_pairs_hook=_pairs,
                          parse_float=_nonint,parse_constant=_nonint)
    except (UnicodeError,json.JSONDecodeError) as error:
        raise MathIssue('INVALID_JSON',where) from error


def read_json(path):
    if path.stat().st_size > MAX_FILE_BYTES:
        reject('INPUT_SIZE_LIMIT',str(path))
    return loads(path.read_bytes(),str(path))


def object_fields(obj,required,where,optional=()):
    if type(obj) is not dict or set(obj)-set(required)-set(optional) or set(required)-set(obj):
        reject('OBJECT_FIELD_SET',where)


def verify_bindings(repo=REPO):
    bindings = read_json(HERE/'SOURCE_BINDINGS.json')
    for row in bindings['files']:
        path = repo/row['path']
        if not path.is_file() or path.stat().st_size!=row['bytes'] or digest(path.read_bytes())!=row['sha256']:
            reject('FROZEN_BINDING_DRIFT',row['path'])
    closure = repo/bindings['c9_source_closure_path']
    with zipfile.ZipFile(closure) as z:
        manifest = loads(z.read('MANIFEST.json'),'c9 source manifest')
        if (manifest['source_units'],manifest['ROMs'],manifest['headers'])!=(72,9,2):
            reject('C9_SOURCE_COUNTS')
        for name,desc in manifest['payloads'].items():
            raw = z.read(name)
            if len(raw)!=desc['bytes'] or digest(raw)!=desc['sha256']:
                reject('C9_SOURCE_MEMBER_DRIFT',name)
    return bindings


def artifact(desc, base, role, missing):
    if desc is None:
        missing.append(role)
        return None
    object_fields(desc,('path','bytes','sha256'),role,('source_path',))
    if type(desc['path']) is not str or not desc['path']:
        reject('ARTIFACT_PATH',role)
    rel = Path(desc['path'])
    if rel.is_absolute() or rel.drive or '..' in rel.parts or ':' in desc['path']:
        reject('ARTIFACT_PATH_ESCAPE',role)
    path = (base/rel).resolve()
    if not path.is_relative_to(base.resolve()):
        reject('ARTIFACT_PATH_ESCAPE',role)
    integer(desc['bytes'],0,MAX_FILE_BYTES,role+'.bytes')
    if type(desc['sha256']) is not str or re.fullmatch('[0-9a-f]{64}',desc['sha256']) is None:
        reject('ARTIFACT_SHA256',role)
    if not path.is_file():
        missing.append(role+':original file missing')
        return None
    raw = path.read_bytes()
    if len(raw)!=desc['bytes'] or digest(raw)!=desc['sha256']:
        reject('ARTIFACT_BYTES_MISMATCH',role)
    return raw


def schema_match(value, rules):
    for rule in rules['anyOf']:
        t = rule['type']
        if t=='null' and value is None:
            return True
        if t=='integer' and type(value) is int and rule.get('minimum',value)<=value<=rule.get('maximum',value):
            if 'enum' not in rule or value in rule['enum']:
                return True
        if t=='string' and type(value) is str and len(value)<=rule.get('maxLength',len(value)):
            if 'pattern' not in rule or re.fullmatch(rule['pattern'],value):
                if 'enum' not in rule or value in rule['enum']:
                    return True
    return False


def validate_index(index,schema):
    if type(index) is not dict or index.get('schema')!='M3_R7C_C9_MECHANICAL_INDEX_V1':
        reject('MECHANICAL_INDEX_SCHEMA',status='UNSUPPORTED_PROFILE')
    rows = index.get('rows')
    if type(rows) is not list or not rows or type(index.get('row_count')) is not int or index['row_count']!=len(rows):
        reject('INDEX_ROW_COUNT')
    required = set(schema['required'])
    if len(required)!=74:
        reject('C9_EXPECTED_74_FIELDS')
    last_cycle = -1
    for n,record in enumerate(rows,1):
        if type(record) is not dict:
            reject('INDEX_RECORD_OBJECT',str(n))
        fields = record.get('fields')
        if type(fields) is not dict or set(fields)!=required:
            reject('C9_FIELDS_NOT_EXACT_74',str(n))
        for key,value in fields.items():
            if not schema_match(value,schema['properties'][key]):
                reject('C9_FIELD_TYPE_OR_RANGE',f'{n}:{key}')
        if type(fields['cycle']) is not int or type(fields['epoch']) is not int:
            reject('CLOCK_ID_INTEGER_PROFILE_REQUIRED',str(n),'UNSUPPORTED_PROFILE')
        cycle = known(fields,'cycle',64)
        if cycle != last_cycle+1:
            reject('PUBLIC_POSEDGE_COVERAGE_GAP',str(n),'UNSUPPORTED_PROFILE')
        last_cycle = cycle
        source=record.get('source')
        if type(source) is not dict or source.get('line')!=n or source.get('cycle')!=cycle or source.get('epoch')!=known(fields,'epoch',32) or source.get('sampling_phase')!='POSEDGE_PRE_NBA':
            reject('INDEX_SOURCE_TIME',str(n))
        if type(record.get('apply')) is not dict:
            reject('INDEX_APPLY_OBJECT',str(n))
        if fields['apply_event_seq'] is not None or record['apply'].get('independent_apply_event_seq') is not None:
            reject('UNVERIFIED_PLAN_SEQUENCE_IN_INDEX',str(n))
        if record.get('apply',{}).get('apply_kind')!=fields['apply_kind']:
            reject('INDEX_DERIVED_APPLY_DRIFT',str(n))
    return rows


def validate_plan(plan):
    if type(plan) is not dict or type(plan.get('events')) is not list or plan.get('independent_of_trace') is not True:
        reject('INDEPENDENT_PLAN_REQUIRED',status='PENDING_INPUT')
    seen=set()
    for event in plan['events']:
        if type(event) is not dict or not {'event_seq','expected_event_hex','arrival_window'}<=event.keys():
            reject('PLAN_EVENT_SHAPE')
        epoch=integer(event.get('epoch',0),0,(1<<32)-1,'plan.epoch')
        seq=integer(event['event_seq'],0,(1<<64)-1,'plan.event_seq')
        if (epoch,seq) in seen:
            reject('DUPLICATE_PLAN_EVENT')
        seen.add((epoch,seq))
        if type(event['expected_event_hex']) is not str or re.fullmatch('(?:0x)?[0-9a-fA-F]{1,16}',event['expected_event_hex']) is None:
            reject('PLAN_EVENT_HEX')
        validate_window(event['arrival_window'])
    configs=plan.get('config_events',[])
    if type(configs) is not list:
        reject('PLAN_CONFIG_ARRAY')
    for event in configs:
        if type(event) is not dict or not {'payload','arrival_window'}<=event.keys():
            reject('PLAN_CONFIG_OBJECT')
        integer(event.get('epoch',0),0,(1<<32)-1,'config.epoch')
        integer(event['payload'],0,(1<<62)-1,'config.payload')
        validate_window(event['arrival_window'])


def validate_window(window):
    object_fields(window,('min_cycle','max_cycle'),'arrival_window')
    lo=integer(window['min_cycle'],0,(1<<64)-1,'window.min')
    integer(window['max_cycle'],lo,(1<<64)-1,'window.max')


def verify_original_rows(index, rows, raw, raw_capture, reset_raw, job):
    lines=raw.splitlines(keepends=True)
    if len(lines)!=len(rows):
        reject('PUBLIC_INDEX_ROW_COUNT')
    trace=index.get('trace_input',{})
    if type(trace) is not dict:
        reject('INDEX_TRACE_DESCRIPTOR')
    descriptor=job['artifacts']['public_rows']
    if trace.get('sha256')!=digest(raw) or trace.get('bytes')!=len(raw) or trace.get('path')!=descriptor.get('source_path',descriptor['path']):
        reject('INDEX_PUBLIC_TRACE_IDENTITY')
    origins=set()
    for n,(record,line) in enumerate(zip(rows,lines),1):
        original=loads(line,f'public:{n}')
        if type(original) is not dict:
            reject('PUBLIC_ROW_OBJECT',str(n))
        if original.get('schema') not in ('M3_R7C_C9_PUBLIC_ROW_V1','M3_R7A_C9_PUBLIC_ROW_V1'):
            reject('PUBLIC_ROW_SCHEMA',str(n),'UNSUPPORTED_PROFILE')
        origins.add(original.get('origin'))
        if original.get('capture_id')!=job['capture_id'] or original.get('fields')!=record['fields']:
            reject('INDEX_PUBLIC_FIELD_MISMATCH',str(n))
        if original['schema']=='M3_R7C_C9_PUBLIC_ROW_V1' and original.get('plan_association') is not None:
            reject('UNVERIFIED_PUBLIC_PLAN_ASSOCIATION',str(n))
        if record['source'].get('raw_line_sha256')!=digest(line):
            reject('PUBLIC_LINE_SHA',str(n))
        source=original.get('source',{})
        if type(source) is not dict:
            reject('PUBLIC_SOURCE_OBJECT',str(n))
        for key in ('line','cycle','epoch','sampling_phase'):
            if source.get(key)!=record['source'].get(key):
                reject('PUBLIC_INDEX_SOURCE_MISMATCH',f'{n}:{key}')
        rawsha=source.get('raw_capture_sha256',source.get('raw_sha256'))
        if record['source'].get('raw_capture_sha256')!=rawsha or record['source'].get('trace_path')!=trace.get('path'):
            reject('INDEX_RAW_SOURCE_MISMATCH',str(n))
        if raw_capture is not None and rawsha!=digest(raw_capture):
            reject('RAW_CAPTURE_SHA',str(n))
        if original['schema']=='M3_R7A_C9_PUBLIC_ROW_V1':
            evidence=record.get('upstream_evidence')
            if type(evidence) is not dict or any(evidence.get(k)!=original.get(k) for k in
                ('schema','origin','source','raw_ports','missing_reasons','events','semantics')):
                reject('UPSTREAM_EVIDENCE_DRIFT',str(n))
            if reset_raw is not None and source.get('reset_edges_sha256')!=digest(reset_raw):
                reject('RESET_EDGE_SOURCE_SHA',str(n))
    if len(origins)!=1:
        reject('MIXED_PUBLIC_ORIGINS')
    index_origins={'SYNTHETIC_C9_FIXTURE' if x=='SYNTHETIC_SCHEMA_FIXTURE' else x for x in origins}
    if index.get('origin') not in index_origins:
        reject('INDEX_ORIGIN_MISMATCH')
    expected='HDL_PUBLIC_CAPTURE_UNVERIFIED' if job['mode']=='REAL' else ('SYNTHETIC_C9_FIXTURE','SYNTHETIC_SCHEMA_FIXTURE')
    if not all(o in expected if isinstance(expected,tuple) else o==expected for o in origins):
        reject('JOB_ORIGIN_MISMATCH')


def verify_frames_and_resets(rows,frame_plan,reset):
    if type(frame_plan) is not dict or type(reset) is not dict:
        reject('FRAME_OR_RESET_OBJECT')
    if frame_plan.get('independent_of_trace') is not True:
        reject('FRAME_PLAN_NOT_INDEPENDENT')
    if known(rows[0]['fields'],'rst_n')!=0:
        reject('INITIAL_RESET_NOT_OBSERVED',status='PENDING_INPUT')
    expected=set()
    for ep in frame_plan.get('epochs',[]):
        if type(ep) is not dict or type(ep.get('frame_cycles')) is not list:
            reject('FRAME_EPOCH_SHAPE')
        epoch=integer(ep['epoch'],0,(1<<32)-1,'frame.epoch')
        for cycle in ep['frame_cycles']:
            key=(epoch,integer(cycle,0,(1<<64)-1,'frame.cycle'))
            if key in expected:
                reject('DUPLICATE_FRAME_PLAN_CYCLE')
            expected.add(key)
    actual={(known(r['fields'],'epoch',32),known(r['fields'],'cycle',64)) for r in rows if known(r['fields'],'frame_tick')}
    if expected!=actual:
        reject('FRAME_PLAN_COVERAGE_MISMATCH')
    finish=frame_plan.get('finish')
    if type(finish) is not dict:
        reject('FINISH_CONTRACT_MISSING',status='PENDING_INPUT')
    end=[r['fields'] for r in rows if known(r['fields'],'finish')]
    if len(end)!=1 or (end[0]['epoch'],end[0]['cycle'])!=(finish.get('epoch'),finish.get('cycle')) or end[0] is not rows[-1]['fields']:
        reject('FINISH_MUST_BE_UNIQUE_FINAL_ROW')
    # The supported reset projection is deliberately narrow and explicit. It
    # references raw asynchronous edges but never fabricates them from trace.
    if reset.get('sampling_phase')!='POSEDGE_PRE_NBA' or reset.get('independent_of_trace') is not True:
        reject('RESET_PROFILE_MISSING',status='PENDING_INPUT')
    if reset.get('profile')!='ASSERT_OBSERVED_LOW_BEFORE_RELEASE_V1':
        reject('RESET_PROFILE_UNSUPPORTED',status='UNSUPPORTED_PROFILE')
    ranges=reset.get('low_ranges')
    if type(ranges) is not list or not ranges or type(reset.get('raw_edges')) is not list or not reset['raw_edges']:
        reject('RESET_ORIGINAL_EDGES_REQUIRED',status='PENDING_INPUT')
    low=set()
    previous_end=-1
    for x in ranges:
        if type(x) is not dict:
            reject('RESET_RANGE_OBJECT')
        lo=integer(x['first_cycle'],0,(1<<64)-1,'reset.first')
        hi=integer(x['last_cycle'],lo,(1<<64)-1,'reset.last')
        epoch=integer(x['epoch'],0,(1<<32)-1,'reset.epoch')
        if lo<=previous_end:
            reject('RESET_RANGES_OVERLAP_OR_REORDER')
        previous_end=hi
        if hi-lo>len(rows):
            reject('RESET_RANGE_EXCEEDS_TRACE')
        low.update((epoch,c) for c in range(lo,hi+1))
    actual_low={(r['fields']['epoch'],r['fields']['cycle']) for r in rows if known(r['fields'],'rst_n')==0}
    if low!=actual_low:
        reject('RESET_ROWS_AND_ORIGINAL_PLAN_DIFFER')
    # Each raw assertion/release pair carries real time and its independently
    # recorded first affected/sample-release cycle, including subcycle times.
    if len(reset['raw_edges'])!=2*len(ranges):
        reject('RESET_RAW_EDGE_COUNT')
    last_time=-1
    for i,x in enumerate(ranges):
        a,b=reset['raw_edges'][2*i:2*i+2]
        for edge,value in ((a,0),(b,1)):
            if type(edge) is not dict:
                reject('RESET_EDGE_OBJECT')
            integer(edge['time_ps'],last_time+1,(1<<64)-1,'reset.time_ps')
            last_time=edge['time_ps']
            if edge.get('value')!=value:
                reject('RESET_EDGE_POLARITY')
            if edge.get('epoch')!=x['epoch']:
                reject('RESET_EDGE_EPOCH')
            integer(edge['first_sampled_cycle'],0,(1<<64)-1,'reset.first_sampled_cycle')
        if a.get('first_sampled_cycle')!=x['first_cycle'] or b.get('first_sampled_cycle')!=x['last_cycle']+1:
            reject('RESET_EDGE_SAMPLE_LINK')
    return finish


def load_job(path,repo=REPO):
    bindings=verify_bindings(repo)
    job=read_json(path)
    object_fields(job,('schema','mode','profile','capture_id','artifacts'),'job')
    if job['schema']!='M1_C9_MATH_JOB_V1' or job['profile']!=PROFILE:
        reject('MATH_JOB_PROFILE',status='UNSUPPORTED_PROFILE')
    if job['mode'] not in ('REAL','SYNTHETIC') or type(job['capture_id']) is not str or not job['capture_id']:
        reject('MATH_JOB_IDENTITY')
    object_fields(job['artifacts'],ROLES,'artifacts')
    missing=[]
    raw={role:artifact(job['artifacts'][role],path.parent,role,missing) for role in ROLES}
    docs={role:loads(data,role) for role,data in raw.items() if data is not None and role not in ('public_rows','raw_capture')}
    schema=read_json(repo/bindings['c9_row_schema_path'])
    rows=validate_index(docs['mechanical_index'],schema) if 'mechanical_index' in docs else None
    if 'independent_plan' in docs:
        validate_plan(docs['independent_plan'])
    if rows is not None:
        if docs['mechanical_index'].get('capture_id')!=job['capture_id']:
            reject('INDEX_CAPTURE_ID')
        if raw['public_rows'] is not None:
            verify_original_rows(docs['mechanical_index'],rows,raw['public_rows'],raw['raw_capture'],raw['reset_edges'],job)
        if 'frame_plan' in docs and 'reset_edges' in docs:
            verify_frames_and_resets(rows,docs['frame_plan'],docs['reset_edges'])
        if 'independent_plan' in docs:
            epochs={known(r['fields'],'epoch',32) for r in rows}
            planned=docs['independent_plan']['events']+docs['independent_plan'].get('config_events',[])
            if any(e.get('epoch',0) not in epochs for e in planned):
                reject('PLAN_EPOCH_NOT_IN_CAPTURE')
    if missing:
        return job,docs,rows,dict(status='PENDING_INPUT',missing=missing)
    provenance=docs['provenance']
    if type(provenance) is not dict:
        reject('PROVENANCE_OBJECT')
    if provenance.get('capture_id')!=job['capture_id']:
        reject('PROVENANCE_CAPTURE_ID')
    if job['mode']=='REAL':
        if digest(raw['provenance']) not in bindings['admitted_real_provenance_sha256']:
            return job,docs,rows,dict(status='PENDING_REAL_ADMISSION',
                missing=['M2 exact source/capture/tool/finish admission for provenance '+digest(raw['provenance'])])
    elif provenance.get('origin')!='SYNTHETIC_FIXTURE_NOT_RTL':
        reject('SYNTHETIC_PROVENANCE_MARKER')
    return job,docs,rows,None
