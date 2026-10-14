"""Software-only unit tests for the N32-B public result ledger."""
import unittest

from b_n32_check import N, OutputLedger


class OutputLedgerTests(unittest.TestCase):
    @staticmethod
    def ledger(*, clipped=True):
        ledger = OutputLedger()
        ledger.reset()
        ledger.request(0x12345678)
        value = 300_000 if clipped else 1
        for slot in range(N):
            ledger.lane(slot, value)
        pcm = (1 << 23) - 1 if clipped else N
        return ledger, pcm

    def observe(self, ledger, pcm, **changes):
        fields = dict(valid=1, ready=1, publish=1,
                      result_id=0x12345678, left=pcm, right=pcm,
                      late=0, clipped=int(pcm == (1 << 23) - 1),
                      first=True, published_row=True)
        fields.update(changes)
        ledger.result(**fields)

    def test_good_exact_clipped_publish(self):
        ledger, pcm = self.ledger()
        self.observe(ledger, pcm)
        self.assertEqual(ledger.publishes, 1)
        self.assertEqual(ledger.clipped_results, 1)

    def test_wrong_id_mutant_rejected(self):
        ledger, pcm = self.ledger()
        with self.assertRaisesRegex(ValueError, "^RESULT_ID_LEDGER$"):
            self.observe(ledger, pcm, result_id=0x12345679)

    def test_wrong_pcm_mutant_rejected(self):
        ledger, pcm = self.ledger()
        with self.assertRaisesRegex(ValueError, "^RESULT_PCM_LEDGER$"):
            self.observe(ledger, pcm, left=pcm - 1)

    def test_wrong_clipped_mutant_rejected(self):
        ledger, pcm = self.ledger()
        with self.assertRaisesRegex(ValueError, "^RESULT_CLIPPED_LEDGER$"):
            self.observe(ledger, pcm, clipped=0)

    def test_hold_payload_must_be_stable(self):
        ledger, pcm = self.ledger(clipped=False)
        self.observe(ledger, pcm, ready=0, publish=0, published_row=False)
        with self.assertRaisesRegex(ValueError, "^RESULT_HOLD_STABILITY$"):
            self.observe(ledger, pcm, ready=0, publish=0,
                         late=1, first=False, published_row=False)

    def test_reset_discards_old_transaction(self):
        ledger, pcm = self.ledger(clipped=False)
        ledger.reset()
        with self.assertRaisesRegex(ValueError, "^RESULT_WITHOUT_LIVE_REQUEST$"):
            self.observe(ledger, pcm)


if __name__ == "__main__":
    unittest.main()
