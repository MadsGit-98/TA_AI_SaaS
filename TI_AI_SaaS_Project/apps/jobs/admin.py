from django.contrib import admin
from .models import JobListing, ScreeningQuestion, CommonScreeningQuestion


@admin.register(JobListing)
class JobListingAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'upload_type', 'job_level', 'created_by', 'batch_count', 'total_resumes', 'start_date', 'expiration_date', 'created_at']
    list_filter = ['status', 'upload_type', 'job_level', 'created_at', 'start_date', 'expiration_date']
    search_fields = ['title', 'description']
    readonly_fields = ['id', 'application_link', 'created_at', 'updated_at', 'modification_date', 'batch_count', 'total_resumes']
    date_hierarchy = 'created_at'

    fieldsets = (
        (None, {
            'fields': ('id', 'title', 'description', 'status', 'upload_type')
        }),
        ('Job Details', {
            'fields': ('job_level', 'required_skills', 'required_experience', 'start_date', 'expiration_date')
        }),
        ('Bulk Upload', {
            'fields': ('batch_count', 'total_resumes'),
            'description': 'Batch count increments only when 100 resumes are committed. Maximum 3 full batches (300 resumes) allowed.'
        }),
        ('Metadata', {
            'fields': ('application_link', 'created_by', 'created_at', 'updated_at', 'modification_date', 'analysis_in_progress')
        }),
    )


@admin.register(ScreeningQuestion)
class ScreeningQuestionAdmin(admin.ModelAdmin):
    list_display = ['job_listing', 'question_text', 'question_type', 'required', 'order', 'created_at']
    list_filter = ['question_type', 'required', 'job_listing']
    search_fields = ['question_text', 'job_listing__title']
    readonly_fields = ['id', 'created_at', 'updated_at']

    fieldsets = (
        (None, {
            'fields': ('id', 'job_listing', 'question_text')
        }),
        ('Question Configuration', {
            'fields': ('question_type', 'required', 'order', 'choices')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(CommonScreeningQuestion)
class CommonScreeningQuestionAdmin(admin.ModelAdmin):
    list_display = ['question_text', 'question_type', 'category', 'is_active', 'created_at']
    list_filter = ['question_type', 'category', 'is_active', 'created_at']
    search_fields = ['question_text', 'category']
    readonly_fields = ['id', 'created_at', 'updated_at']

    fieldsets = (
        (None, {
            'fields': ('id', 'question_text', 'question_type')
        }),
        ('Configuration', {
            'fields': ('category', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )
