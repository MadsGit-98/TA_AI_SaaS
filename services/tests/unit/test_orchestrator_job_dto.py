"""Tests for job DTO wiring in run_analysis initial state."""

from unittest import TestCase

from services.ai_analysis_graphs.orchestrator import _job_dto_from_analysis_context


class JobDtoFromContextTest(TestCase):
    def test_maps_analysis_job_context_fields(self):
        ctx = {
            'id': '11111111-1111-1111-1111-111111111111',
            'title': 'Backend Engineer',
            'description': 'Build APIs',
            'required_skills': ['Python', 'Redis'],
            'required_experience': 3,
            'job_level': 'senior',
        }
        dto = _job_dto_from_analysis_context(ctx, '11111111-1111-1111-1111-111111111111')
        self.assertEqual(dto['title'], 'Backend Engineer')
        self.assertEqual(dto['description'], 'Build APIs')
        self.assertEqual(dto['required_skills'], ['Python', 'Redis'])
        self.assertEqual(dto['required_experience'], 3)
        self.assertEqual(dto['job_level'], 'senior')
        self.assertEqual(dto['id'], '11111111-1111-1111-1111-111111111111')

    def test_falls_back_job_id_when_id_missing(self):
        ctx = {'title': 'Only Title', 'required_skills': [], 'job_level': 'entry'}
        dto = _job_dto_from_analysis_context(ctx, 'fallback-id')
        self.assertEqual(dto['id'], 'fallback-id')
