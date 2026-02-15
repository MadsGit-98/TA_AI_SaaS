from django.urls import path
from . import views
from . import api

app_name = 'jobs'
urlpatterns = [
    # API endpoints for jobs
    path('jobs/', api.JobListingListView.as_view(), name='job-listing-list'),
    path('jobs/<uuid:pk>/', api.JobListingDetailView.as_view(), name='job-listing-detail'),
    path('jobs/<uuid:pk>/activate/', api.activate_job, name='job-activate'),
    path('jobs/<uuid:pk>/deactivate/', api.deactivate_job, name='job-deactivate'),
    path('jobs/<uuid:pk>/duplicate/', api.duplicate_job, name='job-duplicate'),
    
    # Screening questions API endpoints - these need to be accessible from both /api/ and /dashboard/ contexts
    path('jobs/<uuid:job_id>/screening-questions/', api.ScreeningQuestionListView.as_view(), name='screening-question-list'),
    path('jobs/<uuid:job_id>/screening-questions/<uuid:pk>/', api.ScreeningQuestionDetailView.as_view(), name='screening-question-detail'),
    path('common-screening-questions/', api.get_common_screening_questions, name='common-screening-questions'),

    # Template rendering views
    # Empty path maps to 'dashboard/' due to prefix in main urls.py
    path('', views.dashboard_view, name='dashboard'),
    path('create/', views.create_job_view, name='create-job'),
    path('<uuid:job_id>/edit/', views.edit_job_view, name='edit-job'),
    path('<uuid:job_id>/add-screening-question/', views.add_screening_question_view, name='add-screening-question'),
]