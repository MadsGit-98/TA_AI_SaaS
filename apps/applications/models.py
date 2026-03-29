import uuid
from django.db import models, IntegrityError
from django.conf import settings
import secrets
import string


def generate_reference_number():
    """
    Generate a unique reference number for applications.
    Format: XC-XXXXXX (XC- followed by 6 alphanumeric characters)
    """
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(secrets.choice(chars) for _ in range(6))
    return f'XC-{random_part}'


class UploadBatch(models.Model):
    """
    Tracks a single bulk upload session for a job listing.
    
    Used to manage the two-phase commit process:
    1. Files uploaded to temporary storage
    2. Duplicate detection and user review
    3. Commit to permanent storage and Applicant creation
    """
    
    STATUS_PENDING = 'pending'
    STATUS_UPLOADING = 'uploading'
    STATUS_VALIDATING = 'validating'
    STATUS_REVIEW = 'awaiting_review'
    STATUS_COMMITTED = 'committed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_FAILED = 'failed'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_UPLOADING, 'Uploading'),
        (STATUS_VALIDATING, 'Validating'),
        (STATUS_REVIEW, 'Awaiting Review'),
        (STATUS_COMMITTED, 'Committed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_FAILED, 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_listing = models.ForeignKey(
        'jobs.JobListing',
        on_delete=models.CASCADE,
        related_name='upload_batches'
    )
    batch_number = models.PositiveIntegerField(help_text='Sequential batch number (1, 2, or 3)')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='upload_batches'
    )
    file_count = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )
    temp_files = models.JSONField(
        default=list,
        help_text='List of temporary file metadata: [{file_id, filename, file_hash, size, status}]'
    )
    duplicate_summary = models.JSONField(
        null=True,
        blank=True,
        help_text='Duplicate detection results: {duplicates: [...], actions: {...}}'
    )
    
    class Meta:
        ordering = ['batch_number']
        indexes = [
            models.Index(fields=['job_listing', 'batch_number'], name='applications_job_batch_idx'),
            models.Index(fields=['status'], name='applications_ub_status_idx'),
        ]
    
    def add_file(self, file_metadata: dict) -> None:
        """
        Add file metadata to temp_files.
        
        Args:
            file_metadata: Dictionary containing file information
        """
        if not self.temp_files:
            self.temp_files = []
        self.temp_files.append(file_metadata)
        self.file_count = len(self.temp_files)
        self.save()
    
    def get_remaining_capacity(self) -> int:
        """Get remaining file slots in batch (max 100)."""
        return 100 - self.file_count
    
    def can_commit(self) -> tuple[bool, str]:
        """
        Check if batch can be committed.
        
        Returns:
            Tuple of (can_commit: bool, message: str)
        """
        if self.status not in [self.STATUS_VALIDATING, self.STATUS_REVIEW]:
            return False, f"Batch status is {self.status}, not ready for commit"
        if self.file_count == 0:
            return False, "Batch has no files"
        return True, ""


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
    upload_batch = models.ForeignKey(
        'UploadBatch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='applicants',
        help_text='Source upload batch (null for form submissions)'
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
        Auto-generate reference_number and access_token if not set.
        
        Retries up to 5 times if reference_number collision occurs.
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
        return f"{self.first_name} {self.last_name} - {self.job_listing.title}"

    def is_bulk_upload(self) -> bool:
        """Check if applicant was created via bulk upload."""
        return self.upload_batch is not None

    def get_parsing_status(self) -> str:
        """
        Get parsing completeness status.
        
        Returns:
            'complete' if all required fields are present,
            'partial_missing_<fields>' otherwise
        """
        required_fields = ['first_name', 'last_name', 'email', 'phone']
        missing = [f for f in required_fields if not getattr(self, f)]
        if missing:
            return f'partial_missing_{",".join(missing)}'
        return 'complete'

    @classmethod
    def create_from_bulk_upload(cls, file_data: dict, job_listing, upload_batch) -> 'Applicant':
        """
        Create Applicant from bulk upload file data.
        
        Args:
            file_data: Dictionary containing file metadata and parsed data
            job_listing: JobListing instance
            upload_batch: UploadBatch instance
            
        Returns:
            Applicant instance
        """
        return cls.objects.create(
            job_listing=job_listing,
            upload_batch=upload_batch,
            first_name=file_data.get('first_name', ''),
            last_name=file_data.get('last_name', ''),
            email=file_data.get('email', ''),
            phone=file_data.get('phone', ''),
            resume_file=file_data['resume_path'],
            resume_file_hash=file_data['file_hash'],
            resume_parsed_text=file_data['redacted_text'],
            status=cls.STATUS_SUBMITTED
        )


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
        return f"{self.applicant} - Answer to Question {self.question.id}"
