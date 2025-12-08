from django.urls import path
from . import views

app_name = 'analysis'
urlpatterns = [
    path('', views.analysis_dashboard_view, name='analysis_dashboard'),
    path('list/', views.analysis_list_view, name='analysis_list'),
    path('<int:id>/', views.analysis_detail_view, name='analysis_detail'),
    # Additional analysis URLs will be defined in future features
]