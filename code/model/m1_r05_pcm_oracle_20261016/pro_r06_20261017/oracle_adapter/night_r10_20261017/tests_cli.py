"""Exercise the actual CLI function in-process, without child-process fixtures."""
from contextlib import redirect_stdout,redirect_stderr
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from fixture_cases import make_fixture,write_fixture,json_data
from run_math import main


class CLITests(unittest.TestCase):
    def test_cli_success_failure_pending_and_rejected_exit_codes(self):
        with tempfile.TemporaryDirectory(prefix='r10_cli_') as d:
            root=Path(d)
            f=make_fixture(root,samples=1)
            for mode,expected in [('valid',0),('mismatch',1),('pending',3),('unsupported',2)]:
                local=root/mode
                job=write_fixture(local,f)
                if mode=='mismatch':
                    row=next(r for r in f['rows'] if r['result_valid'])
                    row['result_right']+=1
                    write_fixture(local,f)
                    row['result_right']-=1
                if mode in ('pending','unsupported'):
                    data=json.loads(job.read_bytes())
                    if mode=='pending':
                        data['artifacts']['raw_capture']=None
                    else:
                        data['profile']='OTHER_PROFILE'
                    job.write_bytes(json_data(data))
                out=local/'MATH_RESULT.json'
                with patch.object(sys,'argv',['run_math.py','--job',str(job),'--output',str(out)]),redirect_stdout(io.StringIO()):
                    self.assertEqual(main(),expected,mode)
                result=json.loads(out.read_bytes())
                self.assertFalse(result['board_release_allowed'])
                self.assertFalse(result['real_verified'])


if __name__=='__main__':
    unittest.main()
