from rest_framework import serializers
from django.db.models import Exists, OuterRef
from .models import JobListing, ScreeningQuestion, CommonScreeningQuestion
from apps.analysis.models import AIAnalysisResult
from services.ai_analysis_service import get_analysis_progress


class DateValidationMixin:
    """
    Mixin to provide date validation for serializers that have start_date and expiration_date fields.
    """
    def validate(self, data):
        """
        Ensure expiration_date, if present, occurs after start_date, using instance values for missing fields during partial updates.
        
        Returns:
            data: The validated input mapping.
        
        Raises:
            serializers.ValidationError: If both dates are present and expiration_date is less than or equal to start_date.
        """
        start_date = data.get('start_date')
        expiration_date = data.get('expiration_date')

        # For partial updates (PATCH), get missing values from the existing instance
        if not start_date and self.instance:
            start_date = getattr(self.instance, 'start_date', None)

        if not expiration_date and self.instance:
            expiration_date = getattr(self.instance, 'expiration_date', None)

        if start_date and expiration_date and expiration_date <= start_date:
            raise serializers.ValidationError("Expiration date must be after start date.")

        return data


class ScreeningQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScreeningQuestion
        exclude = ('job_listing',)  # Exclude job_listing from serialization since it's set by the view

    def validate(self, data):
        question_type = data.get('question_type', getattr(self.instance, 'question_type', None))
        choices = data.get('choices', getattr(self.instance, 'choices', None))

        # Validate that choices are provided when question type requires them
        if question_type in ['CHOICE', 'MULTIPLE_CHOICE'] and not choices:
            raise serializers.ValidationError({"choices": "Choices are required for choice-based questions."})
        if question_type not in ['CHOICE', 'MULTIPLE_CHOICE'] and choices:
            raise serializers.ValidationError({"choices": "Choices should only be provided for choice-based questions."})

        return data


class CommonScreeningQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommonScreeningQuestion
        fields = '__all__'


class JobListingSerializer(serializers.ModelSerializer):
    screening_questions = ScreeningQuestionSerializer(many=True, read_only=True)
    analysis_complete = serializers.SerializerMethodField()
    analysis_in_progress = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    applicant_count = serializers.SerializerMethodField()

    class Meta:
        model = JobListing
        fields = '__all__'
        read_only_fields = ('id', 'application_link', 'created_at', 'updated_at', 'created_by', 'modification_date')

    def get_analysis_complete(self, obj):
        """
        Determine whether AI analysis for the given job listing is complete.
        
        Checks an `analysis_complete` queryset annotation on `obj` if present; otherwise queries for any AIAnalysisResult related to the job listing with status `ANALYZED`.
        
        Parameters:
            obj: JobListing instance to check for completed analysis.
        
        Returns:
            True if a completed analysis exists for the job listing, False otherwise.
        """
        # Check if the view annotated the queryset with analysis_complete
        if hasattr(obj, 'analysis_complete'):
            return obj.analysis_complete

        # Fallback: query the database (for backwards compatibility)
        return AIAnalysisResult.objects.filter(
            job_listing=obj,
            status=AIAnalysisResult.STATUS_ANALYZED
        ).exists()

    def _get_analysis_progress(self, obj):
        """
        Get analysis progress for the given JobListing, using a per-serializer-instance cache to avoid repeated lookups.
        
        Parameters:
            obj (JobListing): Job listing instance to query progress for.
        
        Returns:
            dict: Mapping with keys 'processed' and 'total' containing integer counts.
        """
        # Check if already cached on this serializer instance
        if not hasattr(self, '_progress_cache'):
            self._progress_cache = {}

        job_id = str(obj.id)

        # Return cached value if available
        if job_id in self._progress_cache:
            return self._progress_cache[job_id]

        # Fetch from Redis and cache
        progress = get_analysis_progress(job_id)
        self._progress_cache[job_id] = progress
        return progress

    def get_analysis_in_progress(self, obj):
        """
        Determine whether AI analysis for the given job listing is currently in progress.
        
        Returns:
            bool: True if analysis has been started and not yet completed, False otherwise.
        """
        progress = self._get_analysis_progress(obj)
        processed = progress.get('processed', 0)
        total = progress.get('total', 0)

        # Analysis is in progress if total > 0 and not all processed
        return total > 0 and processed < total

    def get_progress_percentage(self, obj):
        """
        Compute the analysis progress as an integer percentage between 0 and 100.
        
        Returns:
            int: Percentage of processed applicants out of total applicants; returns 0 when total is zero.
        """
        progress = self._get_analysis_progress(obj)
        processed = progress.get('processed', 0)
        total = progress.get('total', 0)

        if total > 0:
            return int((processed / total) * 100)
        return 0

    def get_applicant_count(self, obj):
        """
        Return the applicant count for the job listing.
        
        If the queryset includes an `applicant_count` annotation, that value is returned; otherwise returns the count of related applicants.
        
        Returns:
            int: Number of applicants for the job listing.
        """
        # Check if the view annotated the queryset with applicant_count
        if hasattr(obj, 'applicant_count'):
            return obj.applicant_count
        
        # Fallback: query the database (for backwards compatibility)
        return obj.applicants.count()


class JobListingCreateSerializer(DateValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = JobListing
        fields = [
            'id', 'title', 'description', 'required_skills', 'required_experience',
            'job_level', 'start_date', 'expiration_date', 'status'
        ]
        read_only_fields = ('id', 'application_link', 'created_at', 'updated_at', 'modification_date')

    def validate(self, data):
        # Call the parent validate method
        """
        Validate start_date and expiration_date and return the validated data.
        
        Performs date validation for serializers that include `start_date` and `expiration_date`. For partial updates, missing dates fall back to the instance's existing values. Raises serializers.ValidationError if both dates are present and `expiration_date` is not later than `start_date`.
        
        Returns:
            The validated data dictionary.
        """
        data = super().validate(data)
        return data


class JobListingUpdateSerializer(DateValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = JobListing
        fields = [
            'title', 'description', 'required_skills', 'required_experience',
            'job_level', 'start_date', 'expiration_date', 'status'
        ]

    def validate(self, data):
        # Call the parent validate method
        """
        Validate start_date and expiration_date and return the validated data.
        
        Performs date validation for serializers that include `start_date` and `expiration_date`. For partial updates, missing dates fall back to the instance's existing values. Raises serializers.ValidationError if both dates are present and `expiration_date` is not later than `start_date`.
        
        Returns:
            The validated data dictionary.
        """
        data = super().validate(data)
        return data