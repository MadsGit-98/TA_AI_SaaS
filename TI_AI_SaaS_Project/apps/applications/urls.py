"""
URL Configuration for Applications App

Public endpoints for job application submission.
"""

from django.urls import path
from . import views

app_name = 'applications'

urlpatterns = [
    # Template views
    path('apply/<uuid:application_link>/', views.application_form_view, name='application_form'),
    path('application/success/<uuid:application_id>/<uuid:access_token>/', views.application_success_view, name='application_success'),
]
