from django.urls import path
from . import views

app_name = 'subscription'
urlpatterns = [
    path('', views.subscription_detail_view, name='subscription_detail'),
    # Additional subscription URLs will be defined in future features
]