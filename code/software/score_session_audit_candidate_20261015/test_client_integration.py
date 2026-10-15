"""New checker interoperability with original Client, using software replies only."""
import hashlib
from pathlib import Path
import types
import unittest

from session_audit import audit_transcript
from session_fixtures import RECORDS_A, attempt, begin, document, frame, response


class OriginalClientIntegration(unittest.TestCase):
    def test_original_client_software_transcript(self):
        path = Path(__file__).resolve().parents[3] / 'code/software/score_transfer_v1/score_transfer.py'
        raw = path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), '8e2a065dcea4fef997da2b0fda7e16a314c65c436b654903ca388be407ddfc07')
        codec = types.ModuleType('frozen_client_task_local_test')
        codec.__file__ = str(path)
        exec(compile(raw, str(path), 'exec'), codec.__dict__)
        bank = 101, RECORDS_A
        requests = [begin(101, RECORDS_A, 7), frame(2, 7, 1, payload=RECORDS_A),
                    frame(3, 7, 2), frame(5, 7, 0), frame(6, 7, 0, 0), frame(6, 7, 1, 1)]
        replies = [response(requests[0], active=True),
                   response(requests[1], active=True, received=16),
                   response(requests[2], bank=bank, received=16),
                   response(requests[3], bank=bank, received=16),
                   response(requests[4], bank=bank, received=16, event=RECORDS_A[:8]),
                   response(requests[5], bank=bank, received=16, event=RECORDS_A[8:])]
        trace = document([bank])

        class SoftwareOnlyTransport:
            def __init__(self):
                self.index, self.pending, self.now = 0, bytearray(), 0.0

            def write(self, data):
                if self.index >= len(requests) or data != requests[self.index]:
                    raise ValueError('original client request differs from independent frame expectation')
                reply = replies[self.index]
                trace['attempts'].append(attempt(data, reply))
                self.pending.extend(reply)
                self.index += 1
                return len(data)

            def read(self, count):
                self.now += 0.001
                value = bytes(self.pending[:min(count, 3)])
                del self.pending[:len(value)]
                return value

        transport = SoftwareOnlyTransport()
        client = codec.Client(transport, clock=lambda: transport.now)
        self.assertEqual(client.upload(101, RECORDS_A, session=7), 2)
        self.assertEqual(transport.index, 6)
        report = audit_transcript(trace)
        self.assertEqual(report['commits'], 1)
        self.assertEqual(report['final_unique_reads'], 2)
        self.assertFalse(report['hardware_pass_claim'])


if __name__ == '__main__':
    unittest.main()
