from rest_framework import serializers
from pathlib import Path
from apps.applications.models import Applicant, ApplicationAnswer
from apps.jobs.models import ScreeningQuestion, JobListing
from apps.applications.utils.file_validation import validate_resume_file
from apps.applications.utils.email_validation import validate_email
from apps.applications.utils.phone_validation import validate_phone
from services.resume_parsing_service import ResumeParserService, ConfidentialInfoFilter


class ScreeningQuestionSerializer(serializers.ModelSerializer):
    """Serializer for ScreeningQuestion model (read-only)."""
    
    class Meta:
        model = ScreeningQuestion
        fields = ['id', 'question_text', 'question_type', 'required', 'order', 'choices']
        read_only_fields = fields


class ApplicationAnswerSerializer(serializers.ModelSerializer):
    """Serializer for ApplicationAnswer model."""

    question_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = ApplicationAnswer
        fields = ['id', 'question_id', 'answer_text', 'created_at']
        read_only_fields = ['id', 'created_at']

    def to_internal_value(self, data):
        """Parse and validate nested serializer data."""
        # Initialize question instance attribute
        self._question_instance = None
        return super().to_internal_value(data)

    def validate_question_id(self, value):
        """Validate that the question exists."""
        try:
            question = ScreeningQuestion.objects.get(id=value)
            # Store the question instance for use in validate_answer_text
            self._question_instance = question
            return question
        except ScreeningQuestion.DoesNotExist:
            raise serializers.ValidationError("Question not found.")

    def validate_answer_text(self, value):
        """Validate answer length based on question type."""
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Answer cannot be empty.")
        if len(value) > 5000:
            raise serializers.ValidationError("Answer cannot exceed 5000 characters.")

        # Get the question object from instance attribute (set by validate_question_id)
        question = getattr(self, '_question_instance', None)
        
        # Fallback: try to get question from initial_data
        if not question and hasattr(self, 'initial_data') and isinstance(self.initial_data, dict):
            question_id = self.initial_data.get('question_id')
            if question_id and hasattr(question_id, 'id'):
                question = question_id

        # Short answer types that don't require minimum length (only need to be non-empty)
        # These match the QUESTION_TYPE_CHOICES in ScreeningQuestion model
        short_answer_types = ['YES_NO', 'CHOICE', 'MULTIPLE_CHOICE', 'FILE_UPLOAD']
        
        if question and question.question_type in short_answer_types:
            # Short answer types only need to be non-empty (already checked above)
            pass
        else:
            # TEXT type requires minimum 10 characters (temporarily lowered for testing)
            if len(value) < 10:
                raise serializers.ValidationError("Answer must be at least 10 characters.")

        return value


class ApplicantSerializer(serializers.ModelSerializer):
    """Serializer for Applicant model with file upload and validation."""

    job_listing_id = serializers.UUIDField(write_only=True)
    screening_answers = ApplicationAnswerSerializer(many=True, write_only=True, required=False, default=list)
    resume = serializers.FileField(write_only=True)
    country_code = serializers.CharField(write_only=True, required=False, default='US')

    class Meta:
        model = Applicant
        fields = [
            'id', 'job_listing_id', 'first_name', 'last_name', 'email',
            'phone', 'country_code', 'resume', 'screening_answers',
            'submitted_at', 'status'
        ]
        read_only_fields = ['id', 'submitted_at', 'status']

    def to_internal_value(self, data):
        """Parse JSON strings for screening_answers field (from multipart forms)."""
        if 'screening_answers' in data and isinstance(data['screening_answers'], str):
            try:
                import json
                data = data.copy()
                data['screening_answers'] = json.loads(data['screening_answers'])
            except (json.JSONDecodeError, ValueError) as e:
                raise serializers.ValidationError({
                    'screening_answers': f'Invalid JSON format: {str(e)}'
                })
        
        # Manually validate nested screening_answers serializer
        validated_screening_answers = []
        if 'screening_answers' in data and isinstance(data['screening_answers'], list):
            data = data.copy()
            answer_serializer = ApplicationAnswerSerializer(many=True, data=data['screening_answers'])
            if answer_serializer.is_valid():
                validated_screening_answers = answer_serializer.validated_data
            else:
                raise serializers.ValidationError({
                    'screening_answers': answer_serializer.errors
                })
        
        # Call parent to_internal_value to validate other fields
        result = super().to_internal_value(data)
        
        # Manually add the validated screening answers to the result
        # This is needed because DRF doesn't automatically handle nested serializers
        # for write-only fields that aren't on the model
        if hasattr(result, '_dict'):
            result._dict['screening_answers'] = validated_screening_answers
        elif isinstance(result, dict):
            result['screening_answers'] = validated_screening_answers
        
        return result
    
    def validate_job_listing_id(self, value):
        """Validate that the job listing exists and is active."""
        try:
            job_listing = JobListing.objects.get(id=value)
            if job_listing.status != 'Active':
                raise serializers.ValidationError("This job is no longer accepting applications.")
            return job_listing
        except JobListing.DoesNotExist:
            raise serializers.ValidationError("Job listing not found.")
    
    def validate_email(self, value):
        """Validate email format and MX record."""
        return validate_email(value)
    
    def validate_phone(self, value):
        """Validate phone number format."""
        country_code = self.initial_data.get('country_code', 'US')
        return validate_phone(value, country_code)
    
    def validate_resume(self, value):
        """Validate resume file format and size."""
        validated_file = validate_resume_file(value)
        # Store the validated extension for use in create()
        self.validated_file_extension = Path(value.name).suffix.lower().lstrip('.')
        return validated_file

    def validate(self, attrs):
        """Validate cross-field dependencies (screening answers vs required questions)."""
        job_listing = attrs.get('job_listing_id')
        screening_answers = attrs.get('screening_answers')

        if job_listing and screening_answers:
            # Get all required questions for this job
            required_questions = ScreeningQuestion.objects.filter(
                job_listing=job_listing,
                required=True
            ).values_list('id', flat=True)

            # Get answered question IDs
            answered_question_ids = {
                answer['question_id'].id if hasattr(answer['question_id'], 'id') else answer['question_id']
                for answer in screening_answers
            }

            # Check for missing required questions
            missing_questions = set(required_questions) - set(answered_question_ids)
            if missing_questions:
                raise serializers.ValidationError({
                    'screening_answers': f"Missing required answers for questions: {missing_questions}"
                })

        return attrs

    def create(self, validated_data):
        """Create applicant and answers."""
        # Get screening answers (may be empty list if no questions)
        screening_answers = validated_data.pop('screening_answers', [])
        job_listing = validated_data.pop('job_listing_id')
        resume_file = validated_data.pop('resume')
        # Remove country_code as it's write-only and not a model field
        validated_data.pop('country_code', None)

        # Calculate file hash for duplication detection
        file_content = resume_file.read()
        file_hash = ResumeParserService.calculate_file_hash(file_content)

        # Extract and redact resume text using pre-validated extension
        file_extension = self.validated_file_extension
        if file_extension == 'pdf':
            parsed_text = ResumeParserService.extract_text_from_pdf(file_content)
        elif file_extension == 'docx':
            parsed_text = ResumeParserService.extract_text_from_docx(file_content)
        else:
            # This should never happen due to validate_resume()
            raise serializers.ValidationError("Unsupported file format.")

        # Redact confidential information
        redacted_text = ConfidentialInfoFilter.redact(parsed_text)

        # Reset file pointer to the beginning before saving
        resume_file.seek(0)

        # Create applicant
        applicant = Applicant.objects.create(
            job_listing=job_listing,
            resume_file_hash=file_hash,
            resume_parsed_text=redacted_text,
            **validated_data
        )

        # Save the resume file after creating the object
        applicant.resume_file.save(resume_file.name, resume_file, save=True)

        # Create answers for each screening question response
        for answer_data in screening_answers:
            question = answer_data['question_id']
            answer_text = answer_data['answer_text']

            # Handle FILE_UPLOAD questions - store file path or placeholder
            if answer_data.get('file_upload'):
                # For file upload questions, store a reference to the uploaded file
                # The actual file is stored in FormData and should be handled separately
                answer_text = f"[File uploaded for question {question.id}]"

            ApplicationAnswer.objects.create(
                applicant=applicant,
                question=question,
                answer_text=answer_text
            )

        return applicant


class ApplicantCreateResponseSerializer(serializers.Serializer):
    """Serializer for applicant creation response."""

    id = serializers.UUIDField()
    status = serializers.CharField()
    submitted_at = serializers.DateTimeField()
    access_token = serializers.UUIDField()
    message = serializers.CharField()


class DuplicateCheckResponseSerializer(serializers.Serializer):
    """Serializer for duplication check response."""
    
    valid = serializers.BooleanField()
    checks = serializers.DictField()
    errors = serializers.ListField(child=serializers.DictField(), required=False)


class FileValidationRequestSerializer(serializers.Serializer):
    """Serializer for file validation request."""
    
    job_listing_id = serializers.UUIDField()
    resume = serializers.FileField()


class ContactValidationRequestSerializer(serializers.Serializer):
    """Serializer for contact validation request."""

    job_listing_id = serializers.UUIDField()
    email = serializers.EmailField()
    phone = serializers.CharField()


class ApplicationStatusSerializer(serializers.Serializer):
    """
    Lean serializer for application status endpoint.
    
    Returns only non-PII fields to prevent IDOR exposure.
    Per security requirements: only status and submitted_at are exposed.
    """

    id = serializers.UUIDField()
    status = serializers.CharField()
    submitted_at = serializers.DateTimeField()
