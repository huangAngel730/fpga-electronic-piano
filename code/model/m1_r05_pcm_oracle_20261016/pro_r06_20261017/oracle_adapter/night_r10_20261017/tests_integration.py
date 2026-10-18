"""New C9 math integration cases; no previously signed test group is called."""
import copy
from pathlib import Path
import tempfile
import unittest

from fixture_cases import make_fixture, write_fixture
from run_math import evaluate


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='m1_r10_')
        self.root=Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def case(self, **kwargs):
        return make_fixture(self.root,**kwargs)

    def result(self, fixture):
        write_fixture(self.root,fixture)
        return evaluate(self.root/'job.json')

    def mutate(self, key, value):
        f=self.case()
        row=next(r for r in f['rows'] if r['result_valid'])
        row[key]=value(row[key]) if callable(value) else value
        result=self.result(f)
        self.assertEqual(result['status'],'FAIL',result)
        self.assertEqual(result['first_difference']['field'],key)

    def test_piano_matches_signed_reference(self):
        f=self.case()
        r=self.result(f)
        self.assertEqual(r['status'],'SOFTWARE_MATCH',r)
        self.assertEqual(r['counts']['result_accepts'],2)
        self.assertFalse(r['real_verified'])
        self.assertEqual(r['comparisons'][0]['left'],f['expected_samples'][0]['left'])

    def test_triangle_pre_tick_address(self):
        f=self.case(timbre=1,samples=4)
        r=self.result(f)
        self.assertEqual(r['status'],'SOFTWARE_MATCH',r)
        self.assertEqual([s['left'] for s in r['comparisons']], [s['left'] for s in f['expected_samples']])

    def test_four_notes_and_fifth_steal(self):
        f=self.case(notes=(55,60,64,67,72),samples=4)
        r=self.result(f)
        self.assertEqual(r['status'],'SOFTWARE_MATCH',r)
        self.assertEqual(r['counts']['apply_kind_1'],5)
        self.assertEqual(r['counts']['apply_kind_2'],5)

    def test_retrigger_keeps_phase(self):
        f=self.case(notes=(60,60),samples=3)
        r=self.result(f)
        self.assertEqual(r['status'],'SOFTWARE_MATCH',r)
        self.assertEqual(r['comparisons'][0]['snapshot']['lanes'][0]['generation'],2)

    def test_long_note_on_backpressure(self):
        f=self.case(backpressure=5)
        r=self.result(f)
        self.assertEqual(r['status'],'SOFTWARE_MATCH',r)
        stages=[x for x in r['actions'] if x['kind'] in (1,2)]
        self.assertEqual(stages[1]['cycle']-stages[0]['cycle'],7)
        self.assertEqual(stages[0]['router_seq'],stages[1]['router_seq'])
        self.assertEqual(stages[0]['plan_seq'],201)

    def test_cancelled_effect_changes_later_history(self):
        f=self.case(delay=True,cancel_first=True,samples=3)
        r=self.result(f)
        self.assertEqual(r['status'],'SOFTWARE_MATCH',r)
        self.assertEqual(r['counts']['effect_accepts'],3)
        self.assertEqual(r['counts']['result_accepts'],2)
        self.assertEqual(r['comparisons'][0]['left'],f['expected_samples'][1]['left'])
        inp=f['expected_samples'][1]['mixed_left']
        without_previous_history=inp*16384>>15
        self.assertNotEqual(r['comparisons'][0]['left'],without_previous_history)

    def test_clip_and_clear_samples(self):
        f=self.case(notes=(60,60,60,60),samples=4)
        r=self.result(f)
        self.assertEqual(r['status'],'SOFTWARE_MATCH',r)
        self.assertEqual(r['counts']['result_accepts'],4)
        # Retriggering one note is one slot; use distinct voices below for true mix clipping.
        f=self.case(notes=(60,61,62,63),timbre=1,samples=256,delay=True,fx_gains=(32767,32767,32767))
        r=self.result(f)
        self.assertEqual(r['status'],'SOFTWARE_MATCH',r)
        flags=[x['upstream_clip'] or any(x['effect_clip']) for x in f['expected_samples']]
        self.assertTrue(any(flags),'fixture must exercise actual arithmetic saturation')
        self.assertTrue(any(not x for x in flags))

    def test_result_pcm_one_lsb_rejected(self):
        self.mutate('result_left',lambda x:x+1)

    def test_result_right_pcm_one_lsb_rejected(self):
        self.mutate('result_right',lambda x:x-1)

    def test_result_clip_rejected(self):
        self.mutate('result_clip_mask',lambda x:x^2)

    def test_effect_clip_separate(self):
        self.mutate('effect_clip_mask',lambda x:x^1)

    def test_feedback_clip_separate(self):
        self.mutate('feedback_clip_mask',lambda x:x^1)

    def test_effect_input_is_compared_not_trusted(self):
        f=self.case()
        row=next(r for r in f['rows'] if r['effect_input_valid'])
        row['effect_input_left']+=1
        r=self.result(f)
        self.assertEqual(r['status'],'FAIL',r)
        self.assertEqual(r['first_difference']['field'],'effect_input_left')

    def test_wrong_result_id(self):
        f=self.case()
        next(r for r in f['rows'] if r['result_valid'])['result_id']=99
        r=self.result(f)
        self.assertEqual(r['status'],'CONTRACT_REJECTED',r)
        self.assertEqual(r['error']['code'],'RESULT_WITHOUT_ACCEPTED_EFFECT')

    def test_generation_drift(self):
        f=self.case()
        next(r for r in f['rows'] if r['occupied_mask'])['slot_generations']+=1
        r=self.result(f)
        self.assertEqual(r['status'],'FAIL',r)
        self.assertEqual(r['first_difference']['layer'],'lane_identity')

    def test_partial_advance(self):
        f=self.case()
        next(r for r in f['rows'] if r['advance_mask'])['advance_mask']=7
        r=self.result(f)
        self.assertEqual(r['status'],'UNSUPPORTED_PROFILE',r)

    def test_missing_advance(self):
        f=self.case()
        next(r for r in f['rows'] if r['advance_mask'])['advance_mask']=0
        r=self.result(f)
        self.assertEqual(r['status'],'CONTRACT_REJECTED',r)
        self.assertEqual(r['error']['code'],'EFFECT_ACCEPT_WITHOUT_LIVE_SNAPSHOT')

    def test_unknown_advance(self):
        f=self.case()
        next(r for r in f['rows'] if r['advance_mask'])['advance_mask']='xxxx'
        r=self.result(f)
        self.assertEqual(r['status'],'PENDING_INPUT',r)

    def test_noteon_cannot_be_allocation_plus_one(self):
        f=self.case()
        source=next(r for r in f['rows'] if r['apply_kind']==2)
        allocation=next(r for r in f['rows'] if r['apply_kind']==1)
        dest=f['rows'][allocation['cycle']+1]
        for key in ('apply_valid','apply_kind','apply_mask','apply_data','router_apply_seq','router_apply_seq_valid','note_on_mask'):
            dest[key],source[key]=source[key],0
        r=self.result(f)
        self.assertEqual(r['status'],'CONTRACT_REJECTED',r)
        self.assertEqual(r['error']['code'],'NOTE_ON_CONSUME_TIMING_OR_GENERATION')

    def test_router_seq_cannot_replace_plan_seq(self):
        f=self.case()
        next(r for r in f['rows'] if r['apply_kind']==1)['router_apply_seq']=201
        r=self.result(f)
        self.assertEqual(r['status'],'PENDING_INPUT',r)
        self.assertEqual(r['error']['code'],'MISSING_TRUSTED_APPLY_CAUSE')


if __name__=='__main__':
    unittest.main()
