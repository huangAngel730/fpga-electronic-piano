"""Conservative session timeout bounds for complete-frame-only transcripts."""
import unittest

from session_audit import audit_transcript
from session_fixtures import RECORDS_A, RECORDS_B, attempt, begin, build_success, frame, response


class SessionTimeProfileTests(unittest.TestCase):
    def test_status_does_not_refresh_active_session(self):
        self.reject_unobserved_timeout(False)

    def test_early_nack_does_not_refresh_active_session(self):
        self.reject_unobserved_timeout(True)

    def reject_unobserved_timeout(self, nack):
        trace = build_success()
        old = (101, RECORDS_A)
        req = begin(202, RECORDS_B, 2)
        trace['attempts'].append(attempt(req, response(req, bank=old, active=True)))
        for index in range(11):
            req = frame(2, 2, 100 + index, payload=RECORDS_B[:1]) if nack else frame(5, 2, 100 + index)
            trace['attempts'].append(attempt(req, response(req, error=6 if nack else 0, bank=old, active=True), 500000))
        req = frame(4, 2, 200)
        trace['attempts'].append(attempt(req, response(req, bank=old)))
        with self.assertRaisesRegex(ValueError, 'SESSION_TIMEOUT_PROFILE_UNSUPPORTED'):
            audit_transcript(trace)

    def test_begin_data_refresh_allow_bounded_recovery(self):
        trace = build_success()
        old = (101, RECORDS_A)
        req = begin(202, RECORDS_B, 2)
        trace['attempts'].append(attempt(req, response(req, bank=old, active=True)))
        for index in range(6):
            req = frame(5, 2, 100 + index)
            trace['attempts'].append(attempt(req, response(req, bank=old, active=True), 500000))
        req = frame(2, 2, 1, payload=RECORDS_B[:7])
        trace['attempts'].append(attempt(req, response(req, bank=old, active=True, received=7), 1000))
        for index in range(6):
            req = frame(5, 2, 200 + index)
            trace['attempts'].append(attempt(req, response(req, bank=old, active=True, received=7), 500000))
        req = frame(4, 2, 250)
        trace['attempts'].append(attempt(req, response(req, bank=old)))
        report = audit_transcript(trace)
        self.assertEqual(report['commits'], 1)
        self.assertEqual(report['aborts'], 1)


if __name__ == '__main__':
    unittest.main()
