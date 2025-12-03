from django.urls import path
from . import views

app_name = 'jobs'
urlpatterns = [
    path('', views.jobs_list_view, name='jobs_list'),
    path('create/', views.jobs_create_view, name='jobs_create'),
    # Additional job URLs will be defined in future features
]