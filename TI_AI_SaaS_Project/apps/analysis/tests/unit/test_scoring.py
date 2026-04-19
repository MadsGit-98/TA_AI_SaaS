"""Unit tests for ``apps.analysis.scoring``."""

from django.test import TestCase

from apps.analysis.scoring import validate_score


class ValidateScoreFiniteTest(TestCase):
    """``validate_score`` rejects NaN and infinities with clear errors."""

    def test_nan_raises_value_error_including_metric_name(self):
        with self.assertRaises(ValueError) as ctx:
            validate_score(float('nan'), 'skills')
        msg = str(ctx.exception)
        self.assertIn('skills', msg)
        self.assertIn('finite', msg.lower())

    def test_positive_infinity_raises(self):
        with self.assertRaises(ValueError) as ctx:
            validate_score(float('inf'), 'experience')
        self.assertIn('experience', str(ctx.exception))

    def test_negative_infinity_raises(self):
        with self.assertRaises(ValueError) as ctx:
            validate_score(float('-inf'), 'education')
        self.assertIn('education', str(ctx.exception))
