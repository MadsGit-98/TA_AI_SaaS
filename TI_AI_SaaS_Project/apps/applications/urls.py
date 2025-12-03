from django.urls import path
from . import views

app_name = 'applications'
urlpatterns = [
    path('submit/', views.applications_submit_view, name='applications_submit'),
    # Additional application URLs will be defined in future features
]