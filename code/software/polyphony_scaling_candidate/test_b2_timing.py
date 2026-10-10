"""Small source-calendar tests, not synthetic evidence of executed RTL."""
import unittest

from b2_clock import backend_calendar, deadline_missed


class SourceCalendarTests(unittest.TestCase):
    def test_all_supported_backend_profiles(self):
        for n in (4, 8, 16, 32):
            for response in (1, 3, 7, 32, 64):
                with self.subTest(n=n, response=response):
                    c = backend_calendar(123, n, response)
                    self.assertEqual(c.advance, 131)
                    self.assertEqual(c.lanes, tuple(
                        123+15+response+i*(response+3) for i in range(n)))
                    self.assertEqual(c.backend_first, 123+14+n*(response+3))
                    self.assertEqual(c.backend_first, c.lanes[-1]+2)

    def test_wrapper_first_is_not_publish_handshake(self):
        for response in (1, 3):
            c = backend_calendar(70, 4, response)
            self.assertEqual(c.wrapper_first, c.lanes[-1]+4)
            self.assertEqual(c.wrapper_first, 70+28+4*response)
            # The deadline cannot change when a consumer holds ready low.
            expected = deadline_missed(c.wrapper_first, 0)
            self.assertEqual(expected, 0)
            self.assertEqual(deadline_missed(c.wrapper_first+900, 0), 1)

    def test_deadline_832_833_834(self):
        for accepted in (0, 97, 0xffffffff):
            self.assertEqual([deadline_missed(accepted+1+duration, accepted)
                              for duration in (832, 833, 834)], [0, 1, 1])

    def test_invalid_parameters_fail_closed(self):
        for accepted, n, response in ((True, 4, 1), (-1, 4, 1), (0, 5, 1),
                                      (0, 4, 0), (0, 4, 65), (0, 4, True)):
            with self.assertRaisesRegex(ValueError, 'CLOCK_PARAMETERS'):
                backend_calendar(accepted, n, response)


if __name__ == '__main__':
    unittest.main()
