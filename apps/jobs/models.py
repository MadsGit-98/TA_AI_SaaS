import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxLengthValidator
from django.utils import timezone


class JobListing(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]

    JOB_LEVEL_CHOICES = [
        ('Intern', 'Intern'),
        ('Entry', 'Entry'),
        ('Junior', 'Junior'),
        ('Senior', 'Senior'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, validators=[MaxLengthValidator(200)])
    description = models.TextField(validators=[MaxLengthValidator(3000)])
    required_skills = models.JSONField()
    required_experience = models.IntegerField(validators=[MinValueValidator(0)])
    job_level = models.CharField(max_length=10, choices=JOB_LEVEL_CHOICES)
    start_date = models.DateTimeField()
    expiration_date = models.DateTimeField()
    modification_date = models.DateTimeField(null=True, blank=True)  # Updated when edited
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Inactive')
    application_link = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        # Ensure modification date equals start date when first created
        if self._state.adding:  # If this is a new object
            self.modification_date = self.start_date
        else:  # On update, set modification date to current time
            self.modification_date = timezone.now()
        # Call full_clean to enforce field constraints like max_length
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        # Validate that expiration date is after start date
        if self.start_date and self.expiration_date and self.expiration_date <= self.start_date:
            raise ValidationError("Expiration date must be after start date.")

    def __str__(self):
        return self.title

    class Meta:
        # Add indexes for performance optimization
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['start_date']),
            models.Index(fields=['expiration_date']),
            models.Index(fields=['status', 'start_date', 'expiration_date']),
            models.Index(fields=['created_at']),
        ]


class ScreeningQuestion(models.Model):
    QUESTION_TYPE_CHOICES = [
        ('TEXT', 'Text'),
        ('YES_NO', 'Yes/No'),
        ('CHOICE', 'Choice'),
        ('MULTIPLE_CHOICE', 'Multiple Choice'),
        ('FILE_UPLOAD', 'File Upload'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_listing = models.ForeignKey(JobListing, on_delete=models.CASCADE, related_name='screening_questions')
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES)
    required = models.BooleanField(default=True)
    order = models.IntegerField(null=True, blank=True)
    choices = models.JSONField(null=True, blank=True)  # For choice-based questions
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']
        indexes = [
            models.Index(fields=['job_listing']),
            models.Index(fields=['order']),
        ]

    def clean(self):
        # Validate that choices are provided when question type requires them
        if self.question_type in ['CHOICE', 'MULTIPLE_CHOICE'] and not self.choices:
            raise ValidationError("Choices are required for choice-based questions.")
        if self.question_type not in ['CHOICE', 'MULTIPLE_CHOICE'] and self.choices:
            raise ValidationError("Choices should only be provided for choice-based questions.")

    def save(self, *args, **kwargs):
        # Call clean method to validate before saving
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.job_listing.title}: {self.question_text}"


class CommonScreeningQuestion(models.Model):
    """
    Model to store common screening questions that can be suggested to users
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question_text = models.TextField(unique=True)
    question_type = models.CharField(max_length=20, choices=ScreeningQuestion.QUESTION_TYPE_CHOICES)
    category = models.CharField(max_length=50, default='General')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.question_text
