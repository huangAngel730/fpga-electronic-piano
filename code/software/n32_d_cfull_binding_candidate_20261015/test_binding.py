"""Static binding tests; never execute archive members or HDL/EDA."""
from __future__ import annotations
import hashlib
import copy
import contextlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import sys
import unittest
import uuid
import warnings
import zipfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import binding_check as binding

ROOT=HERE.parents[2]
ABCD=ROOT/'code/output/n32_publication_20261014_r01/transfer/M3_N32_ABCD_20261014_COMPLETE.zip'
CFULL=ROOT/'code/output/n32_c_full_publication_20261014_r01/transfer/M3_N32_C_FULL_20261014.zip'
RECEIPT=Path('E:/FPGA/GAOYUNFPGA/Callback3/chat6/M2_REVIEW_RECEIPT.json')
OUT=Path(os.environ.get('N32_BINDING_TEST_OUTPUT',ROOT/'code/output'/('n32_d_cfull_binding_tests_'+uuid.uuid4().hex))).resolve()
OUT.mkdir(parents=True,exist_ok=True)


def archive_bytes(entries,compression=zipfile.ZIP_STORED):
    stream=io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',UserWarning)
        with zipfile.ZipFile(stream,'w',compression=compression) as archive:
            for name,raw in entries:archive.writestr(name,raw)
    return stream.getvalue()


class RetainedCases(unittest.TestCase):
    def setUp(self):
        self.directory=OUT/(self._testMethodName+'_'+uuid.uuid4().hex[:8])
        self.directory.mkdir()

    def zip_reject(self,raw,limits=None):
        (self.directory/'input.zip').write_bytes(raw)
        with self.assertRaises((ValueError,OSError,zipfile.BadZipFile)) as caught:
            binding.inspect_zip_bytes(raw,'independent_fixture',limits=limits)
        (self.directory/'rejection.txt').write_text(type(caught.exception).__name__+': '+str(caught.exception)+'\n',encoding='utf-8')

    def json_reject(self,raw):
        (self.directory/'input.json').write_bytes(raw)
        with self.assertRaises((ValueError,UnicodeError)) as caught:binding.load_strict_json(raw,'independent_fixture')
        (self.directory/'rejection.txt').write_text(type(caught.exception).__name__+': '+str(caught.exception)+'\n',encoding='utf-8')


class ZipSafetyTests(RetainedCases):
    def test_regular_stored_zip(self):
        raw=archive_bytes([('folder/a.txt',b'original bytes')])
        checked=binding.inspect_zip_bytes(raw,'literal_positive')
        self.assertEqual(set(checked.names),{'folder/a.txt'})
        self.assertEqual(checked.read('folder/a.txt'),b'original bytes')

    def test_regular_deflated_zip(self):
        raw=archive_bytes([('a.txt',b'abcdef'*100)],zipfile.ZIP_DEFLATED)
        checked=binding.inspect_zip_bytes(raw,'literal_positive')
        self.assertEqual(checked.read('a.txt'),b'abcdef'*100)

    def test_duplicate_member(self):self.zip_reject(archive_bytes([('x',b'a'),('x',b'b')]))
    def test_case_collision(self):self.zip_reject(archive_bytes([('A.txt',b'a'),('a.txt',b'b')]))
    def test_absolute_member(self):self.zip_reject(archive_bytes([('/x',b'a')]))
    def test_parent_escape(self):self.zip_reject(archive_bytes([('../x',b'a')]))
    def test_embedded_parent_escape(self):self.zip_reject(archive_bytes([('a/../x',b'a')]))
    def test_backslash_member(self):
        # Windows ZipInfo normalizes a backslash passed to writestr. Alter the
        # already-built raw local+central filenames with an equal-length name.
        normal=archive_bytes([('a/x',b'a')])
        unsafe=b'a'+bytes([92])+b'x'
        self.assertEqual(normal.count(b'a/x'),2)
        raw=normal.replace(b'a/x',unsafe)
        self.assertEqual(raw.count(unsafe),2)
        self.assertNotIn(b'a/x',raw)
        (self.directory/'fixture_construction.json').write_text(json.dumps(dict(
            local_and_central_replacements=2,unsafe_filename_hex=unsafe.hex(),
            method='Equal-length raw filename mutation, not ZipInfo name normalization'))+'\n',encoding='utf-8')
        self.zip_reject(raw)
    def test_drive_member(self):self.zip_reject(archive_bytes([('C:/x',b'a')]))
    def test_ads_member(self):self.zip_reject(archive_bytes([('x:stream',b'a')]))

    def test_symlink_member(self):
        info=zipfile.ZipInfo('link');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
        self.zip_reject(archive_bytes([(info,b'target')]))

    def test_encrypted_flag(self):
        raw=bytearray(archive_bytes([('x',b'a')]))
        local=raw.index(b'PK\x03\x04');central=raw.index(b'PK\x01\x02')
        for offset in (local+6,central+8):
            struct.pack_into('<H',raw,offset,struct.unpack_from('<H',raw,offset)[0]|1)
        self.zip_reject(bytes(raw))

    def test_bad_crc(self):
        raw=bytearray(archive_bytes([('payload',b'UNIQUE_PAYLOAD_12345')]))
        position=raw.index(b'UNIQUE_PAYLOAD_12345');raw[position]^=1
        self.zip_reject(bytes(raw))

    def test_truncated_zip(self):self.zip_reject(archive_bytes([('x',b'a')])[:-10])
    def test_invalid_magic(self):self.zip_reject(b'not a zip\n')

    def test_unsupported_bzip2_compression_rejected(self):
        self.zip_reject(archive_bytes([('a',b'BZIP2 unsupported input')],zipfile.ZIP_BZIP2))

    def test_member_count_limit(self):
        self.zip_reject(archive_bytes([('a',b'1'),('b',b'2')]),binding.ZipLimits(max_members=1))

    def test_single_member_size_limit(self):
        self.zip_reject(archive_bytes([('a',b'12')]),binding.ZipLimits(max_member_bytes=1))

    def test_total_uncompressed_size_limit(self):
        self.zip_reject(archive_bytes([('a',b'12'),('b',b'34')]),binding.ZipLimits(max_total_bytes=3))

    def test_ratio_limit(self):
        self.zip_reject(archive_bytes([('a',b'x'*4096)],zipfile.ZIP_DEFLATED),binding.ZipLimits(max_ratio=2))

    def test_archive_bytes_limit(self):
        self.zip_reject(archive_bytes([('a',b'1')]),binding.ZipLimits(max_archive_bytes=10))


class JsonSafetyTests(RetainedCases):
    def test_literal_json(self):self.assertEqual(binding.load_strict_json(b'{"x":[1,false,null]}','literal'),{'x':[1,False,None]})
    def test_duplicate_key(self):self.json_reject(b'{"x":1,"x":2}')
    def test_nested_duplicate_key(self):self.json_reject(b'{"a":{"x":1,"x":2}}')
    def test_nan(self):self.json_reject(b'{"x":NaN}')
    def test_infinity(self):self.json_reject(b'{"x":Infinity}')
    def test_negative_infinity(self):self.json_reject(b'{"x":-Infinity}')
    def test_truncated_json(self):self.json_reject(b'{"x":')
    def test_invalid_utf8(self):self.json_reject(b'{"x":"\xff"}')


class IdentityManifestTests(RetainedCases):
    def assert_rejected(self,call):
        with self.assertRaises(ValueError) as caught:call()
        (self.directory/'rejection.txt').write_text(str(caught.exception)+'\n',encoding='utf-8')

    def manifest_archive(self,files,entries=(('a',b'A'),)):
        return archive_bytes(list(entries)+[('MANIFEST.json',json.dumps({'files':files}).encode())])

    def test_literal_identity(self):
        binding.validate_identity(b'A',{'bytes':1,'sha256':hashlib.sha256(b'A').hexdigest()},'literal')

    def test_boolean_byte_count_is_not_integer(self):
        self.assert_rejected(lambda:binding.validate_identity(b'A',{'bytes':True,'sha256':hashlib.sha256(b'A').hexdigest()},'bool'))

    def test_malformed_sha(self):
        self.assert_rejected(lambda:binding.validate_identity(b'A',{'bytes':1,'sha256':'not-sha'},'badsha'))

    def test_uppercase_sha_rejected(self):
        self.assert_rejected(lambda:binding.validate_identity(b'A',{'bytes':1,'sha256':'A'*64},'uppercase'))

    def test_wrong_byte_length(self):
        self.assert_rejected(lambda:binding.validate_identity(b'A',{'bytes':2,'sha256':hashlib.sha256(b'A').hexdigest()},'length'))

    def test_wrong_sha_bytes(self):
        self.assert_rejected(lambda:binding.validate_identity(b'A',{'bytes':1,'sha256':'0'*64},'sha'))

    def test_extra_identity_field_rejected(self):
        self.assert_rejected(lambda:binding.validate_manifest_records({'a':{'bytes':1,'sha256':hashlib.sha256(b'A').hexdigest(),'extra':0}}))

    def test_manifest_literal_exact_set(self):
        raw=self.manifest_archive({'a':{'bytes':1,'sha256':hashlib.sha256(b'A').hexdigest()}})
        checked=binding.inspect_zip_bytes(raw,'manifest_positive')
        self.assertIsInstance(checked.verify_manifest(),dict)

    def test_manifest_missing_member_rejected(self):
        raw=self.manifest_archive({'a':{'bytes':1,'sha256':hashlib.sha256(b'A').hexdigest()},'missing':{'bytes':1,'sha256':'0'*64}})
        self.assert_rejected(lambda:binding.inspect_zip_bytes(raw,'missing').verify_manifest())

    def test_manifest_unlisted_extra_member_rejected(self):
        raw=self.manifest_archive({'a':{'bytes':1,'sha256':hashlib.sha256(b'A').hexdigest()}},(('a',b'A'),('extra',b'X')))
        self.assert_rejected(lambda:binding.inspect_zip_bytes(raw,'extra').verify_manifest())

    def test_manifest_member_tamper_rejected(self):
        raw=self.manifest_archive({'a':{'bytes':1,'sha256':hashlib.sha256(b'A').hexdigest()}},(('a',b'B'),))
        self.assert_rejected(lambda:binding.inspect_zip_bytes(raw,'tampered').verify_manifest())


class ActualAnchoredBundleTests(RetainedCases):
    def test_real_four_layer_bundle_static_only(self):
        before={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in (ABCD,CFULL,RECEIPT)}
        self.assertEqual(before[str(ABCD)],'ba9e4f42d9aa5bb60c6d5122ae271fc58b3b9e7d27cca4caa48fd9740d85aa36')
        self.assertEqual(before[str(CFULL)],'eac6e9371a96e91447a75d869d7e7a6dc76252fd89d6c8b621953a396a42c726')
        self.assertEqual(before[str(RECEIPT)],'e0447a093fc6d2cc593d9012f8ac2be0585aeed33cee447bc02ffbe84d795fbe')
        result=binding.verify_bundle(ABCD,CFULL,RECEIPT)
        (self.directory/'actual_report.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        after={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in (ABCD,CFULL,RECEIPT)}
        self.assertEqual(before,after)
        expected=json.loads((HERE/'EXPECTED_IDENTITIES.json').read_text(encoding='utf-8'))
        self.assertEqual(result['status'],'STATIC_BINDING_ONLY')
        self.assertEqual(result['shared_count'],25)
        self.assertEqual(result['d_project_roles'],expected['counts'])
        self.assertIs(result['top_difference']['resource_top_simulated'],False)
        self.assertEqual(result['top_difference']['c_simulation_top'],'tb_c_n32_r1_v6')
        self.assertEqual(result['cfull']['counts'],expected['limits'])
        for key in ('actual_EDA_calls','RTL_calls','device_calls'):
            self.assertIs(type(result[key]),int);self.assertEqual(result[key],0)
        self.assertEqual(result['resources'],'UNKNOWN')
        self.assertEqual(result['STA'],'NOT_RUN');self.assertIs(result['T061_complete'],False)
        self.assertIs(result['historical_d_evidence']['automatically_rebound_to_C_FULL'],False)

    def test_outer_layer_sha_swapped_rejected(self):
        with self.assertRaises(ValueError) as caught:binding.verify_bundle(CFULL,ABCD,RECEIPT)
        (self.directory/'rejection.txt').write_text(str(caught.exception)+'\n',encoding='utf-8')


class OutputBoundaryTests(RetainedCases):
    def test_task_output_prefix_accepted_without_io(self):
        target=self.directory/'prepared'
        self.assertEqual(binding.task_output_path(target),target.absolute())
        self.assertFalse(target.exists())

    def test_other_task_prefix_rejected(self):
        target=ROOT/'code/output'/'another_task_output'
        with self.assertRaisesRegex(ValueError,'OUTPUT_BOUNDARY'):
            binding.task_output_path(target)

    def test_source_directory_output_rejected(self):
        with self.assertRaisesRegex(ValueError,'OUTPUT_BOUNDARY'):
            binding.task_output_path(HERE/'new_output')
        self.assertFalse((HERE/'new_output').exists())

    def test_parent_component_output_rejected(self):
        with self.assertRaisesRegex(ValueError,'OUTPUT_BOUNDARY'):
            binding.task_output_path(self.directory/'..'/'escape')

    def test_cli_existing_output_does_not_overwrite(self):
        before=set(self.directory.iterdir())
        stdout,stderr=io.StringIO(),io.StringIO()
        with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
            code=binding.main(['prepare','--abcd',str(ABCD),'--cfull',str(CFULL),
                               '--receipt',str(RECEIPT),'--output',str(self.directory)])
        self.assertNotEqual(code,0)
        self.assertEqual(set(self.directory.iterdir()),before)
        self.assertIn('OUTPUT_EXISTS',stdout.getvalue()+stderr.getvalue())
        (self.directory/'stdout.log').write_text(stdout.getvalue(),encoding='utf-8')
        (self.directory/'stderr.log').write_text(stderr.getvalue(),encoding='utf-8')

    def test_reused_wrong_m2_receipt_rejected(self):
        wrong=self.directory/'wrong_receipt.json';wrong.write_bytes(b'{"schema":1,"reviewer":"M2"}\n')
        with self.assertRaises(ValueError) as caught:binding.verify_bundle(ABCD,CFULL,wrong)
        (self.directory/'rejection.txt').write_text(str(caught.exception)+'\n',encoding='utf-8')


class SemanticContractTests(RetainedCases):
    """Reach semantic checks directly; do not stop every mutation at outer SHA."""
    @classmethod
    def setUpClass(cls):
        cls.outer_a=zipfile.ZipFile(ABCD);cls.outer_c=zipfile.ZipFile(CFULL)
        cls.d=zipfile.ZipFile(io.BytesIO(cls.outer_a.read('D/snapshot.zip')))
        cls.c=zipfile.ZipFile(io.BytesIO(cls.outer_c.read('C_FULL/snapshot.zip')))
        cls.project=json.loads(cls.d.read('project/manifest.json'))
        cls.expected=json.loads((HERE/'EXPECTED_IDENTITIES.json').read_text(encoding='utf-8'))
        cls.cf_manifest=json.loads(cls.outer_c.read('C_FULL/MANIFEST.json'))
        cls.original_plan=json.loads(cls.c.read('reused/original_plan.json'))
        cls.original_receipt=json.loads(cls.c.read('reused/original_receipt.json'))
        cls.current_plan=json.loads(cls.c.read('prepared/plan.json'))
        cls.current_receipt=json.loads(cls.c.read('execution/receipt.json'))
        cls.report=json.loads(cls.c.read('execution/report.json'))
        cls.mutations=json.loads(cls.c.read('execution/mutation_report.json'))

    @classmethod
    def tearDownClass(cls):
        for archive in (cls.d,cls.c,cls.outer_a,cls.outer_c):archive.close()

    def rejection(self,call,description):
        with self.assertRaises(ValueError) as caught:call()
        (self.directory/'mutation_and_diagnostic.json').write_text(json.dumps(dict(
            mutation=description,error=str(caught.exception),code=getattr(caught.exception,'code',None),
            source='READ_ONLY_SIGNED_BASELINE_DICT_PLUS_ONE_MUTATION',EDA_calls=0,RTL_calls=0),indent=2)+'\n',encoding='utf-8')

    def shared(self,d_records=None,c_inputs=None,original_inputs=None,d_read=None,c_read=None,original_read=None):
        return binding.validate_shared_inputs(
            self.project['files'] if d_records is None else d_records,
            self.current_plan['inputs'] if c_inputs is None else c_inputs,
            self.original_plan['inputs'] if original_inputs is None else original_inputs,
            d_read or (lambda path:self.d.read('project/'+path)),
            c_read or (lambda path:self.c.read('prepared/snapshot/'+path)),
            original_read or (lambda path:self.c.read('history/n32cfp01/snapshot/'+path)))

    def cf(self,**changed):
        values=dict(manifest=self.cf_manifest,original_plan=self.original_plan,
                    original_receipt=self.original_receipt,current_plan=self.current_plan,
                    current_receipt=self.current_receipt,report=self.report,mutations=self.mutations)
        values.update(changed)
        return binding.validate_cfull_contract(values['manifest'],values['original_plan'],values['original_receipt'],
            values['current_plan'],values['current_receipt'],values['report'],values['mutations'],self.expected)

    def test_actual_project_45_roles_fixed(self):
        binding.validate_project_contract(self.project,self.expected)
        from collections import Counter
        self.assertEqual(dict(Counter(row['role'] for row in self.project['files'])),
                         {'source':18,'top':1,'include':2,'rom':5,'evidence':16,'gprj':1,'sdc':1,'tcl':1})

    def test_actual_shared_25_origin_mappings(self):
        rows=self.shared();self.assertEqual(len(rows),25)
        (self.directory/'actual_shared_25.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')

    def test_project_missing_file(self):
        changed=copy.deepcopy(self.project);changed['files'].pop()
        self.rejection(lambda:binding.validate_project_contract(changed,self.expected),'Remove one of 45 project records')

    def test_project_extra_file(self):
        changed=copy.deepcopy(self.project);changed['files'].append(dict(path='sources/extra.sv',role='source',bytes=1,sha256='0'*64))
        self.rejection(lambda:binding.validate_project_contract(changed,self.expected),'Add a 46th unapproved source')

    def test_project_wrapper_is_not_resource_top(self):
        changed=copy.deepcopy(self.project);changed['project']['top_source']='sources/b_n32_r1_wrapper.sv'
        changed['project']['source_order'][-1]='sources/b_n32_r1_wrapper.sv'
        self.rejection(lambda:binding.validate_project_contract(changed,self.expected),'Substitute simulation wrapper for D resource top')

    def test_project_boolean_tool_calls_not_integer(self):
        changed=copy.deepcopy(self.project);changed['execution']['tool_calls']=False
        self.rejection(lambda:binding.validate_project_contract(changed,self.expected),'Boolean false is not integer zero tool calls')

    def test_project_resources_not_silently_upgraded(self):
        changed=copy.deepcopy(self.project);changed['execution']['resources']='PASS'
        self.rejection(lambda:binding.validate_project_contract(changed,self.expected),'Forge resource acceptance')

    def test_project_changed_clock(self):
        changed=copy.deepcopy(self.project);changed['clock']['period_ns']=20
        self.rejection(lambda:binding.validate_project_contract(changed,self.expected),'Change frozen 25ns clock')

    def test_wrong_origin_snapshot_mapping(self):
        rows=copy.deepcopy(self.project['files'])
        row=next(row for row in rows if row['role']=='source');row['origin_snapshot']='code/rtl/other/source.sv'
        self.rejection(lambda:self.shared(d_records=rows),'Wrong original source mapping')

    def test_changed_d_source_actual_bytes(self):
        target=next(row['path'] for row in self.project['files'] if row['role']=='source')
        def reader(path):
            raw=self.d.read('project/'+path)
            return raw+b'// changed\n' if path==target else raw
        self.rejection(lambda:self.shared(d_read=reader),'Change D source bytes without changing pinned identities')

    def test_changed_c_rom_actual_bytes(self):
        target=next(row['origin_snapshot'] for row in self.project['files'] if row['role']=='rom')
        def reader(path):
            raw=self.c.read('prepared/snapshot/'+path)
            return raw+b'0000\n' if path==target else raw
        self.rejection(lambda:self.shared(c_read=reader),'Change C ROM bytes')

    def test_original_plan_source_identity_changed(self):
        rows=copy.deepcopy(self.original_plan['inputs'])
        target=next(row['origin_snapshot'] for row in self.project['files'] if row['role']=='source')
        next(row for row in rows if row['snapshot']==target)['sha256']='0'*64
        self.rejection(lambda:self.shared(original_inputs=rows),'Wrong source identity in original FULL plan')

    def test_actual_continuous_and_reuse_contract(self):self.cf()

    def test_segmented_c_cannot_be_claimed_full(self):
        changed=copy.deepcopy(self.report);changed['single_continuous_full_C_run']=False
        changed['profile']='TWO_SEPARATELY_QUALIFIED_SEGMENTS_NOT_ONE_CONTINUOUS_RUN'
        self.rejection(lambda:self.cf(report=changed),'Replace continuous FULL claim by segmented profile')

    def test_capture_composition_forbidden(self):
        changed=copy.deepcopy(self.report);changed['capture_composition']=True
        self.rejection(lambda:self.cf(report=changed),'Compose capture instead of one continuous run')

    def test_capture_sha_wrong(self):
        changed=copy.deepcopy(self.report);changed['capture_sha256']='0'*64
        self.rejection(lambda:self.cf(report=changed),'Wrong continuous capture identity')

    def test_original_simulation_nonzero_forbidden(self):
        changed=copy.deepcopy(self.original_receipt)
        next(step for step in changed['steps'] if step['name']=='simulate')['exit_code']=1
        self.rejection(lambda:self.cf(original_receipt=changed),'Original simulation must actually exit zero')

    def test_original_failure_history_must_remain_partial(self):
        changed=copy.deepcopy(self.original_receipt);changed['status']='PASS';changed['exit_code']=0
        self.rejection(lambda:self.cf(original_receipt=changed),'Do not rewrite original mutations failure as success')

    def test_reuse_capture_identity_wrong(self):
        changed=copy.deepcopy(self.current_plan);changed['reused_simulation']['capture']['sha256']='0'*64
        self.rejection(lambda:self.cf(current_plan=changed),'Reuse a different capture')

    def test_reuse_original_receipt_identity_wrong(self):
        changed=copy.deepcopy(self.current_plan);changed['reused_simulation']['receipt']['sha256']='0'*64
        self.rejection(lambda:self.cf(current_plan=changed),'Reuse a different original failure receipt')

    def test_reuse_not_new_simulation(self):
        changed=copy.deepcopy(self.current_receipt);changed['execution_mode']='NEW_RTL_SIMULATION'
        self.rejection(lambda:self.cf(current_receipt=changed),'Do not label software-only reuse as a new simulation')

    def test_publication_counter_forgery(self):
        changed=copy.deepcopy(self.report);changed['publications']=4941
        self.rejection(lambda:self.cf(report=changed),'Wrong signed publication count')

    def test_mutation_nonzero_contract(self):
        changed=copy.deepcopy(self.mutations);changed['mutations'][0]['exit_code']=0
        self.rejection(lambda:self.cf(mutations=changed),'Mutation acceptance must not be hidden')


if __name__=='__main__':unittest.main(verbosity=2)
