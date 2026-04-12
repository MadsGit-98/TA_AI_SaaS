"""
AI Service API Serializers

Request/response serializers for the AI service REST API.
Field names align with AnalysisResultDTO and AnalysisState from
services.ai_analysis_graphs.types to ensure consistent data shapes.
"""

from rest_framework import serializers

from services.ai_analysis_graphs.types import AnalysisResultDTO


class _AnalysisResultDTOSerializer(serializers.Serializer):
    """
    Validates a single result dict against the AnalysisResultDTO shape.
    Ensures incoming webhook payloads match the expected schema from
    services.ai_analysis_graphs.types.AnalysisResultDTO.
    """
    applicant_id = serializers.CharField()
    job_listing_id = serializers.CharField()
    education_score = serializers.IntegerField(required=False, default=0)
    skills_score = serializers.IntegerField(required=False, default=0)
    experience_score = serializers.IntegerField(required=False, default=0)
    supplemental_score = serializers.IntegerField(required=False, default=0)
    overall_score = serializers.IntegerField()
    category = serializers.CharField()
    education_justification = serializers.CharField(required=False, default='', allow_blank=True)
    skills_justification = serializers.CharField(required=False, default='', allow_blank=True)
    experience_justification = serializers.CharField(required=False, default='', allow_blank=True)
    supplemental_justification = serializers.CharField(required=False, default='', allow_blank=True)
    overall_justification = serializers.CharField(required=False, default='', allow_blank=True)
    status = serializers.ChoiceField(choices=['Analyzed', 'Unprocessed'])
    error_message = serializers.CharField(required=False, default='', allow_blank=True)


class WebhookCompletedPayloadSerializer(serializers.Serializer):
    """Webhook event: analysis completed."""
    event = serializers.CharField(default='completed')
    analysis_run_id = serializers.UUIDField()
    job_id = serializers.UUIDField()
    results = _AnalysisResultDTOSerializer(many=True)
    applicants_processed = serializers.IntegerField()
    applicants_total = serializers.IntegerField()
    progress_percentage = serializers.IntegerField(default=100)
    timestamp = serializers.DateTimeField()


class ApplicantSerializer(serializers.Serializer):
    """Single applicant in an analysis request."""
    applicant_id = serializers.UUIDField()
    resume_text = serializers.CharField(min_length=1, trim_whitespace=False)
    name = serializers.CharField(min_length=1, max_length=200)
    email = serializers.EmailField(required=False, allow_blank=True)


class InitiateAnalysisRequestSerializer(serializers.Serializer):
    """Request body for POST /api/v1/analysis/initiate/"""
    job_id = serializers.UUIDField()
    job_title = serializers.CharField(min_length=1, max_length=200)
    job_skills = serializers.ListField(
        child=serializers.CharField(min_length=1),
        min_length=1,
    )
    job_experience_level = serializers.ChoiceField(choices=['entry', 'mid', 'senior', 'lead'])
    applicants = ApplicantSerializer(many=True, min_length=1, max_length=100)


class InitiateAnalysisResponseSerializer(serializers.Serializer):
    """Response body for successful analysis initiation."""
    analysis_run_id = serializers.UUIDField()
    job_id = serializers.UUIDField()
    status = serializers.CharField()
    applicants_total = serializers.IntegerField()
    estimated_completion = serializers.DateTimeField(required=False)


class DuplicateAnalysisResponseSerializer(serializers.Serializer):
    """Response when analysis is already running."""
    error = serializers.CharField(default='duplicate_analysis')
    message = serializers.CharField()
    existing_analysis_run_id = serializers.UUIDField(allow_null=True)
    existing_status = serializers.CharField()


class RerunAnalysisRequestSerializer(serializers.Serializer):
    """Request body for POST /api/v1/analysis/{job_id}/rerun/"""
    confirm = serializers.BooleanField(required=True)


class RerunAnalysisResponseSerializer(serializers.Serializer):
    """Response body for successful rerun."""
    analysis_run_id = serializers.UUIDField()
    job_id = serializers.UUIDField()
    status = serializers.CharField()
    previous_results_deleted = serializers.IntegerField()
    applicants_total = serializers.IntegerField()
    estimated_completion = serializers.DateTimeField(required=False)


class AnalysisStatusResponseSerializer(serializers.Serializer):
    """Response body for GET /api/v1/analysis/{job_id}/status/"""
    analysis_run_id = serializers.UUIDField()
    job_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=[
        'queued', 'processing', 'completed', 'cancelled', 'failed', 'partially_complete'
    ])
    applicants_processed = serializers.IntegerField()
    applicants_total = serializers.IntegerField()
    progress_percentage = serializers.IntegerField()
    category_distribution = serializers.DictField(required=False)
    estimated_completion = serializers.DateTimeField(required=False)
    started_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(required=False)
    cancelled_at = serializers.DateTimeField(required=False)


class CancelAnalysisRequestSerializer(serializers.Serializer):
    """Request body for POST /api/v1/analysis/{job_id}/cancel/"""
    reason = serializers.CharField(required=False, allow_blank=True, default='User requested cancellation')


class CancelAnalysisResponseSerializer(serializers.Serializer):
    """Response body for successful cancellation."""
    analysis_run_id = serializers.UUIDField()
    job_id = serializers.UUIDField()
    status = serializers.CharField(default='cancelling')
    message = serializers.CharField()
    applicants_processed = serializers.IntegerField()
    applicants_total = serializers.IntegerField()


class HealthDependencySerializer(serializers.Serializer):
    """Single dependency in health check response."""
    status = serializers.ChoiceField(choices=['ok', 'error', 'unknown'])
    message = serializers.CharField()
    response_time_ms = serializers.IntegerField(allow_null=True)


class HealthResponseSerializer(serializers.Serializer):
    """Response body for GET /health"""
    service = serializers.CharField(default='ai-analysis-service')
    status = serializers.ChoiceField(choices=['healthy', 'degraded', 'unhealthy'])
    version = serializers.CharField(default='1.0.0')
    dependencies = serializers.DictField(child=HealthDependencySerializer())
    last_checked = serializers.DateTimeField()
    error_details = serializers.CharField(required=False, allow_blank=True)


class ReadyResponseSerializer(serializers.Serializer):
    """Response body for GET /ready"""
    ready = serializers.BooleanField()
    checks = serializers.DictField(child=serializers.BooleanField())
    reason = serializers.CharField(required=False, allow_blank=True)


# Webhook serializers (AI service → Django)

class WebhookProgressPayloadSerializer(serializers.Serializer):
    """Webhook event: progress update."""
    event = serializers.CharField(default='progress')
    analysis_run_id = serializers.UUIDField()
    job_id = serializers.UUIDField()
    applicants_processed = serializers.IntegerField()
    applicants_total = serializers.IntegerField()
    progress_percentage = serializers.IntegerField()
    category_distribution = serializers.DictField(required=False)
    timestamp = serializers.DateTimeField()


class WebhookCancelledPayloadSerializer(serializers.Serializer):
    """Webhook event: analysis cancelled."""
    event = serializers.CharField(default='cancelled')
    analysis_run_id = serializers.UUIDField()
    job_id = serializers.UUIDField()
    applicants_processed = serializers.IntegerField()
    applicants_total = serializers.IntegerField()
    progress_percentage = serializers.IntegerField()
    timestamp = serializers.DateTimeField()


class WebhookFailedPayloadSerializer(serializers.Serializer):
    """Webhook event: analysis failed."""
    event = serializers.CharField(default='failed')
    analysis_run_id = serializers.UUIDField()
    job_id = serializers.UUIDField()
    error_message = serializers.CharField()
    applicants_processed = serializers.IntegerField()
    applicants_total = serializers.IntegerField()
    progress_percentage = serializers.IntegerField()
    timestamp = serializers.DateTimeField()
