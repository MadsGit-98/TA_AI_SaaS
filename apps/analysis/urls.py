from django.urls import path
from . import views
from .api import (
    initiate_analysis,
    analysis_status,
    analysis_results,
    analysis_result_detail,
    cancel_analysis,
    rerun_analysis,
    analysis_statistics,
)

app_name = 'analysis'

urlpatterns = [
    # UI Views
    path('', views.analysis_dashboard_view, name='analysis_dashboard'),
    path('list/', views.analysis_list_view, name='analysis_list'),
    path('reporting/<uuid:job_id>/', views.reporting_page_view, name='reporting_page'),
    path('<int:id>/', views.analysis_detail_view, name='analysis_detail'),

    # API Endpoints
    path('api/jobs/<uuid:job_id>/analysis/initiate/', initiate_analysis, name='api-initiate-analysis'),
    path('api/jobs/<uuid:job_id>/analysis/status/', analysis_status, name='api-analysis-status'),
    path('api/jobs/<uuid:job_id>/analysis/results/', analysis_results, name='api-analysis-results'),
    path('api/analysis/results/<uuid:result_id>/', analysis_result_detail, name='api-analysis-result-detail'),
    path('api/jobs/<uuid:job_id>/analysis/cancel/', cancel_analysis, name='api-cancel-analysis'),
    path('api/jobs/<uuid:job_id>/analysis/re-run/', rerun_analysis, name='api-rerun-analysis'),
    path('api/jobs/<uuid:job_id>/analysis/statistics/', analysis_statistics, name='api-analysis-statistics'),
]
