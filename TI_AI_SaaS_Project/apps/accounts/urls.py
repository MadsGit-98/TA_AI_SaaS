from django.urls import path, include
from . import views

app_name = 'accounts'
urlpatterns = [
    # Home page
    path('', views.home_view, name='home'),

    # Authentication URLs
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('password/reset/', views.password_reset_view, name='password_reset'),

    # Legal pages
    path('privacy/', views.privacy_policy_view, name='privacy_policy'),
    path('terms/', views.terms_conditions_view, name='terms_conditions'),
    path('refund/', views.refund_policy_view, name='refund_policy'),
    path('contact/', views.contact_view, name='contact'),

    # Activation pages
    path('activation-success/', views.activation_completed_view, name='activation_completed'),
    path('activation-error/', views.activation_error_view, name='activation_error'),
    path('activation-step/<str:uid>/<str:token>/',views.activation_step_view, name = 'activation_step'), 

    # Password reset pages
    path('password/reset/failure/', views.password_reset_failure_view, name='password_reset_failure'),
    path('password-reset/form/<str:uid>/<str:token>/', views.password_reset_form_view, name='password_reset_form'),

    # Additional authentication URLs will be defined in future features
]