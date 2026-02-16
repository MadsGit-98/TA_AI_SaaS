from rest_framework import serializers
from .models import JobListing, ScreeningQuestion, CommonScreeningQuestion


class DateValidationMixin:
    """
    Mixin to provide date validation for serializers that have start_date and expiration_date fields.
    """
    def validate_dates(self, data):
        """
        Ensure `expiration_date` is chronologically after `start_date`, using instance values for missing fields during partial updates.
        
        Parameters:
            data (dict): Incoming serializer data; may omit `start_date` or `expiration_date` for partial updates.
        
        Returns:
            dict: The (possibly augmented) input data.
        
        Raises:
            rest_framework.serializers.ValidationError: If both dates are present and `expiration_date` is not after `start_date`.
        """
        start_date = data.get('start_date')
        expiration_date = data.get('expiration_date')

        # For partial updates (PATCH), get missing values from the existing instance
        if not start_date and self.instance:
            start_date = getattr(self.instance, 'start_date', None)

        if not expiration_date and self.instance:
            expiration_date = getattr(self.instance, 'expiration_date', None)

        if start_date and expiration_date and start_date > expiration_date:
            raise serializers.ValidationError("Expiration date must be after start date.")

        return data


class ScreeningQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScreeningQuestion
        exclude = ('job_listing',)  # Exclude job_listing from serialization since it's set by the view

    def validate(self, data):
        """
        Validate that `choices` are present only for choice-based questions.
        
        This method determines the effective `question_type` and `choices` from the incoming `data`
        or from the existing instance (for partial updates), then enforces that:
        - `choices` must be provided when `question_type` is `'CHOICE'` or `'MULTIPLE_CHOICE'`.
        - `choices` must not be provided when `question_type` is any other value.
        
        Returns:
            dict: The (possibly unchanged) validated data.
        
        Raises:
            serializers.ValidationError: If `choices` are missing for choice-based questions or if
            `choices` are provided for non-choice question types.
        """
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
    
    class Meta:
        model = JobListing
        fields = '__all__'
        read_only_fields = ('id', 'application_link', 'created_at', 'updated_at', 'created_by', 'modification_date')


class JobListingCreateSerializer(DateValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = JobListing
        fields = [
            'id', 'title', 'description', 'required_skills', 'required_experience',
            'job_level', 'start_date', 'expiration_date', 'status'
        ]
        read_only_fields = ('id', 'application_link', 'created_at', 'updated_at', 'modification_date')

    def validate(self, data):
        # Call the parent validate method if it exists
        """
        Validate the serializer input and enforce chronological consistency between start_date and expiration_date.
        
        Parameters:
            data (dict): Partial or full validated data from earlier serializer validation steps.
        
        Returns:
            dict: The validated data (potentially augmented with instance values for partial updates).
        
        Raises:
            serializers.ValidationError: If expiration_date is not after start_date.
        """
        data = super().validate(data)
        # Apply date validation
        return self.validate_dates(data)


class JobListingUpdateSerializer(DateValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = JobListing
        fields = [
            'title', 'description', 'required_skills', 'required_experience',
            'job_level', 'start_date', 'expiration_date', 'status'
        ]

    def validate(self, data):
        # Call the parent validate method if it exists
        """
        Validate the serializer input and enforce chronological consistency between start_date and expiration_date.
        
        Parameters:
            data (dict): Partial or full validated data from earlier serializer validation steps.
        
        Returns:
            dict: The validated data (potentially augmented with instance values for partial updates).
        
        Raises:
            serializers.ValidationError: If expiration_date is not after start_date.
        """
        data = super().validate(data)
        # Apply date validation
        return self.validate_dates(data)