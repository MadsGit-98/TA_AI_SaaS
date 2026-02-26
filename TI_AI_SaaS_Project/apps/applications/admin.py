"""
Admin interface for Applications app
"""

from django.contrib import admin
from apps.applications.models import Applicant, ApplicationAnswer


@admin.register(Applicant)
class ApplicantAdmin(admin.ModelAdmin):
    """Admin interface for Applicant model"""
    
    list_display = [
        'first_name',
        'last_name',
        'email',
        'phone',
        'job_listing',
        'submitted_at',
        'status'
    ]
    
    list_filter = [
        'status',
        'submitted_at',
        'job_listing'
    ]
    
    search_fields = [
        'first_name',
        'last_name',
        'email',
        'phone',
        'job_listing__title'
    ]
    
    readonly_fields = [
        'id',
        'submitted_at',
        'resume_file_hash',
        'resume_parsed_text',
        'status'
    ]
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'email', 'phone')
        }),
        ('Job Application', {
            'fields': ('job_listing', 'status')
        }),
        ('Resume', {
            'fields': ('resume_file', 'resume_file_hash', 'resume_parsed_text')
        }),
        ('Metadata', {
            'fields': ('id', 'submitted_at'),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'submitted_at'
    ordering = ['-submitted_at']


@admin.register(ApplicationAnswer)
class ApplicationAnswerAdmin(admin.ModelAdmin):
    """Admin interface for ApplicationAnswer model"""
    
    list_display = [
        'applicant',
        'question',
        'answer_text',
        'created_at'
    ]
    
    list_filter = [
        'created_at',
        'question__job_listing'
    ]
    
    search_fields = [
        'applicant__first_name',
        'applicant__last_name',
        'applicant__email',
        'question__question_text',
        'answer_text'
    ]
    
    readonly_fields = ['id', 'created_at']
    
    fieldsets = (
        ('Answer Details', {
            'fields': ('applicant', 'question', 'answer_text')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
