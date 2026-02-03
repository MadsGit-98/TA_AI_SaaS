from django.urls import path
from . import views

app_name = 'jobs'
urlpatterns = [
    path('jobs/', views.JobListingListView.as_view(), name='job-listing-list'),
    path('jobs/<uuid:pk>/', views.JobListingDetailView.as_view(), name='job-listing-detail'),
    path('jobs/<uuid:pk>/activate/', views.activate_job, name='job-activate'),
    path('jobs/<uuid:pk>/deactivate/', views.deactivate_job, name='job-deactivate'),
    path('jobs/<uuid:pk>/duplicate/', views.duplicate_job, name='job-duplicate'),
    path('jobs/<uuid:job_id>/screening-questions/', views.ScreeningQuestionListView.as_view(), name='screening-question-list'),
    path('jobs/<uuid:job_id>/screening-questions/<uuid:pk>/', views.ScreeningQuestionDetailView.as_view(), name='screening-question-detail'),
    path('common-screening-questions/', views.get_common_screening_questions, name='common-screening-questions'),
]