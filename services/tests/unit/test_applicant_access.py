"""Unit tests for applicant API dict vs ORM field resolution."""

from unittest import TestCase
from services.ai_analysis_graphs.applicant_access import (
    resolve_applicant_id,
    resolve_resume_text,
)


class ResolveApplicantIdTest(TestCase):
    def test_dict_prefers_applicant_id(self):
        self.assertEqual(
            resolve_applicant_id(
                {'applicant_id': 'uuid-1', 'resume_text': 'x'}
            ),
            'uuid-1',
        )

    def test_dict_falls_back_to_id(self):
        self.assertEqual(
            resolve_applicant_id({'id': 'uuid-2', 'resume_text': 'x'}),
            'uuid-2',
        )

    def test_model_uses_pk(self):
        class DummyApplicant:
            pk = 'pk-1'
            id = 'id-ignored'

        self.assertEqual(resolve_applicant_id(DummyApplicant()), 'pk-1')

    def test_model_falls_back_to_id(self):
        class DummyApplicant:
            id = 'id-1'

        self.assertEqual(resolve_applicant_id(DummyApplicant()), 'id-1')


class ResolveResumeTextTest(TestCase):
    def test_prefers_state_resume(self):
        self.assertEqual(
            resolve_resume_text({'resume_text': 'from-dict'}, '  from-state  '),
            'from-state',
        )

    def test_dict_resume_text(self):
        self.assertEqual(
            resolve_resume_text({'resume_text': ' body '}, None),
            'body',
        )

    def test_dict_resume_parsed_text(self):
        self.assertEqual(
            resolve_resume_text({'resume_parsed_text': 'parsed'}, None),
            'parsed',
        )

    def test_model_attributes(self):
        class DummyApplicant:
            resume_parsed_text = 'p'
            resume_text = None

        self.assertEqual(resolve_resume_text(DummyApplicant(), None), 'p')
