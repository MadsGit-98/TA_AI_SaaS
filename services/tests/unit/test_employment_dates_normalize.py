"""Regression: LLM may return non-dict entries in employment_dates."""

from unittest import TestCase

from services.ai_analysis_graphs.worker import _normalize_employment_dates


class NormalizeEmploymentDatesTest(TestCase):
    def test_keeps_dict_entries(self):
        raw = [
            {'job_title': 'Dev', 'company': 'X', 'start': '2020-01', 'end': '2021-01'},
        ]
        self.assertEqual(_normalize_employment_dates(raw), raw)

    def test_skips_plain_strings(self):
        out = _normalize_employment_dates(['Senior Engineer at Acme 2020-2021'])
        self.assertEqual(out, [])

    def test_parses_embedded_json_object_string(self):
        line = '{"job_title": "A", "company": "B", "start": "2020-01", "end": "2021-01"}'
        out = _normalize_employment_dates([line])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['job_title'], 'A')

    def test_non_list_returns_empty(self):
        self.assertEqual(_normalize_employment_dates({'not': 'a list'}), [])
