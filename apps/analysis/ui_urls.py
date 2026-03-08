"""
URLs for AI Analysis UI Views

These are the frontend views accessible to users.
Mounted at /analysis/ in main urls.py
"""

from django.urls import path
from . import views

app_name = 'analysis'

urlpatterns = [
    # UI Views
    path('', views.analysis_dashboard_view, name='analysis_dashboard'),
    path('list/', views.analysis_list_view, name='analysis_list'),
    path('reporting/<uuid:job_id>/', views.reporting_page_view, name='reporting_page'),
    path('<int:id>/', views.analysis_detail_view, name='analysis_detail'),
]
