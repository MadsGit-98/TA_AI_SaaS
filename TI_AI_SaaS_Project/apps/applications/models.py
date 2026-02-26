import uuid
from django.db import models, IntegrityError
import secrets
import string


def generate_reference_number():
    """
    Generate a new application reference number in the format "XC-XXXXXX".
    
    The suffix consists of six characters drawn from uppercase letters A–Z and digits 0–9.
    
    Returns:
        reference_number (str): Reference string formatted as "XC-XXXXXX".
    """
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(secrets.choice(chars) for _ in range(6))
    return f'XC-{random_part}'


class Applicant(models.Model):
    """
    Represents a job applicant's submission including contact info and resume.

    Per specification: No status workflow - applications are always "submitted"
    """

    STATUS_SUBMITTED = 'submitted'
    STATUS_CHOICES = [
        (STATUS_SUBMITTED, 'submitted'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_number = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        db_index=True
    )
    access_token = models.UUIDField(
        unique=True,
        editable=False,
        db_index=True,
        help_text="Secure token for accessing application success page"
    )
    job_listing = models.ForeignKey(
        'jobs.JobListing',
        on_delete=models.CASCADE,
        related_name='applicants'
    )
    first_name = models.CharField(max_length=200)
    last_name = models.CharField(max_length=200)
    email = models.EmailField(max_length=255, db_index=True)
    phone = models.CharField(max_length=50, db_index=True)
    resume_file = models.FileField(
        upload_to='applications/resumes/',
        max_length=500
    )
    resume_file_hash = models.CharField(max_length=64, db_index=True)
    resume_parsed_text = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SUBMITTED,
        editable=False
    )
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['job_listing', 'resume_file_hash'],
                name='unique_resume_per_job'
            ),
            models.UniqueConstraint(
                fields=['job_listing', 'email'],
                name='unique_email_per_job'
            ),
            models.UniqueConstraint(
                fields=['job_listing', 'phone'],
                name='unique_phone_per_job'
            ),
        ]
        indexes = [
            models.Index(fields=['job_listing', 'submitted_at']),
        ]
    
    def save(self, *args, **kwargs):
        """
        Ensure the instance has a unique reference_number and an access_token before saving, retrying if the reference_number collides.
        
        Generates a reference_number and an access_token when they are not set, then attempts to save the model. If a save fails due to a uniqueness conflict on reference_number, the method clears the reference_number and retries up to five times with a newly generated value. If an IntegrityError occurs for other fields (for example email, phone, or resume constraints), that error is re-raised immediately. If all retry attempts are exhausted due to repeated reference_number collisions, an IntegrityError is raised indicating the failure and chained to the last database error.
        Raises:
        	IntegrityError: If saving fails for non-reference_number uniqueness violations, or if a unique reference_number cannot be generated after the allowed retries.
        """
        max_attempts = 5
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                # Generate reference_number if not set
                if not self.reference_number:
                    self.reference_number = generate_reference_number()
                
                # Generate access_token if not set
                if not self.access_token:
                    self.access_token = uuid.uuid4()
                
                # Save the model
                super().save(*args, **kwargs)
                return  # Success - exit the method
                
            except IntegrityError as e:
                # Check if this is specifically a reference_number uniqueness error
                error_message = str(e).lower()
                if 'reference_number' in error_message:
                    # Store the error for potential re-raise
                    last_error = e
                    # Clear reference_number to force regeneration on next attempt
                    self.reference_number = None
                    # Continue to next retry attempt
                    continue
                else:
                    # Not a reference_number error (e.g., email, phone, resume constraints)
                    # Re-raise immediately without retry
                    raise
        
        # All retry attempts exhausted - re-raise the last IntegrityError
        if last_error:
            raise IntegrityError(
                f"Failed to generate unique reference_number after {max_attempts} attempts"
            ) from last_error

    def __str__(self):
        """
        Produce a human-readable representation of the applicant combining full name and the related job listing title.
        
        Returns:
            str: A string in the format "<first_name> <last_name> - <job listing title>".
        """
        return f"{self.first_name} {self.last_name} - {self.job_listing.title}"


class ApplicationAnswer(models.Model):
    """
    Stores an applicant's answer to a specific screening question.
    
    References ScreeningQuestion from jobs app to avoid duplication.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant = models.ForeignKey(
        'Applicant',
        on_delete=models.CASCADE,
        related_name='answers'
    )
    question = models.ForeignKey(
        'jobs.ScreeningQuestion',
        on_delete=models.PROTECT,
        related_name='answers'
    )
    answer_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['applicant', 'question'],
                name='unique_answer_per_question'
            ),
        ]
        indexes = [
            models.Index(fields=['applicant', 'question']),
        ]
    
    def __str__(self):
        """
        Human-readable representation of an application answer combining the applicant and question id.
        
        Returns:
            str: A string in the format "<applicant> - Answer to Question <question_id>" where <applicant> is the applicant's string representation and <question_id> is the associated question's id.
        """
        return f"{self.applicant} - Answer to Question {self.question.id}"
