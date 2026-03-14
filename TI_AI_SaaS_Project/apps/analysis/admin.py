from django.contrib import admin
from .models import AIAnalysisResult


@admin.register(AIAnalysisResult)
class AIAnalysisResultAdmin(admin.ModelAdmin):
    """Admin configuration for AIAnalysisResult model."""

    list_display = (
        'id',
        'applicant_name',
        'job_listing_title',
        'overall_score',
        'category',
        'status',
        'created_at',
    )

    list_filter = (
        'status',
        'category',
        'job_listing',
        'created_at',
    )

    search_fields = (
        'applicant__first_name',
        'applicant__last_name',
        'applicant__email',
        'job_listing__title',
    )

    readonly_fields = (
        'id',
        'created_at',
        'updated_at',
    )

    fieldsets = (
        ('Identification', {
            'fields': ('id', 'applicant', 'job_listing')
        }),
        ('Scores', {
            'fields': (
                'education_score',
                'skills_score',
                'experience_score',
                'supplemental_score',
                'overall_score',
            )
        }),
        ('Category & Status', {
            'fields': ('category', 'status', 'error_message')
        }),
        ('Justifications', {
            'fields': (
                'education_justification',
                'skills_justification',
                'experience_justification',
                'supplemental_justification',
                'overall_justification',
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'analysis_started_at',
                'analysis_completed_at',
            ),
            'classes': ('collapse',)
        }),
    )

    def applicant_name(self, obj):
        """
        Get the applicant's full name.
        
        Returns:
            str: Applicant's full name in the format "FirstName LastName".
        """
        return f"{obj.applicant.first_name} {obj.applicant.last_name}"
    applicant_name.short_description = 'Applicant'

    def job_listing_title(self, obj):
        """
        Return the title of the job listing related to the given AIAnalysisResult.
        
        Parameters:
            obj (AIAnalysisResult): The AIAnalysisResult instance whose related job listing title will be returned.
        
        Returns:
            str: The job listing title.
        """
        return obj.job_listing.title
    job_listing_title.short_description = 'Job Listing'
