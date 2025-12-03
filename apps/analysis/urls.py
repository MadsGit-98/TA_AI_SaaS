from django.urls import path
from . import views

app_name = 'analysis'
urlpatterns = [
    path('<int:id>/', views.analysis_detail_view, name='analysis_detail'),
    # Additional analysis URLs will be defined in future features
]