import uuid
from django.db import models


class Applicant(models.Model):
    """
    Represents a job applicant's submission including contact info and resume.
    
    Per specification: No status workflow - applications are always "submitted"
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
    status = models.CharField(max_length=20, default='submitted')
    
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
            models.Index(fields=['email']),
            models.Index(fields=['phone']),
            models.Index(fields=['resume_file_hash']),
        ]
    
    def __str__(self):
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
        return f"{self.applicant} - Answer to Question {self.question.id}"
