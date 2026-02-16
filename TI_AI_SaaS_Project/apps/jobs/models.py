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
        """
        Save the model instance to the database while updating its modification_date and validating fields.
        
        On creation, sets modification_date to start_date; on update, sets modification_date to the current time. Runs full_clean() to enforce field constraints before delegating to the base save implementation.
        """
        if not self.pk:  # If this is a new object
            self.modification_date = self.start_date
        else:  # On update, set modification date to current time
            self.modification_date = timezone.now()
        # Call full_clean to enforce field constraints like max_length
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        # Validate that expiration date is after start date
        """
        Validate that the job listing's expiration_date is after its start_date.
        
        Raises:
            ValidationError: If both `start_date` and `expiration_date` are set and `expiration_date` is less than or equal to `start_date`.
        """
        if self.start_date and self.expiration_date and self.expiration_date <= self.start_date:
            raise ValidationError("Expiration date must be after start date.")

    def __str__(self):
        """
        Return the job listing's title as its human-readable representation.
        
        Returns:
            str: The title of the job listing.
        """
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
        """
        Validate the screening question's choices against its question type.
        
        Raises:
            ValidationError: If the question type is 'CHOICE' or 'MULTIPLE_CHOICE' and no `choices` are provided,
            or if the question type is not one of those and `choices` is present.
        """
        if self.question_type in ['CHOICE', 'MULTIPLE_CHOICE'] and not self.choices:
            raise ValidationError("Choices are required for choice-based questions.")
        if self.question_type not in ['CHOICE', 'MULTIPLE_CHOICE'] and self.choices:
            raise ValidationError("Choices should only be provided for choice-based questions.")

    def save(self, *args, **kwargs):
        # Call clean method to validate before saving
        """
        Validate the model instance and persist it to the database.
        
        Calls the model's `clean()` method to enforce field constraints before delegating to the superclass `save()` to perform persistence.
        """
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        """
        Provide a human-readable representation combining the related job listing's title and the question text.
        
        Returns:
            str: A string formatted as "JOB_TITLE: question_text".
        """
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
        """
        Return the text of the screening question for human-readable representations.
        
        Returns:
            str: The value of the `question_text` field.
        """
        return self.question_text