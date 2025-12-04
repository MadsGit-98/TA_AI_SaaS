from django.urls import path, include
from . import views

app_name = 'accounts'
urlpatterns = [
    # Home page
    path('', views.home_view, name='home'),

    # Authentication URLs
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),

    # Legal pages
    path('privacy/', views.privacy_policy_view, name='privacy_policy'),
    path('terms/', views.terms_conditions_view, name='terms_conditions'),
    path('refund/', views.refund_policy_view, name='refund_policy'),
    path('contact/', views.contact_view, name='contact'),

    # API endpoints
    path('api/', include('apps.accounts.api_urls')),

    # Additional authentication URLs will be defined in future features
]