from django.urls import path, include
from . import api

app_name = 'api'
urlpatterns = [
    # Authentication API endpoints
    path('auth/register/', api.register, name='register'),
    path('auth/login/', api.login, name='login'),
    path('auth/logout/', api.logout, name='logout'),
    path('auth/token/cookie-refresh/', api.cookie_token_refresh, name='cookie_token_refresh'),
    path('auth/password/reset/', api.password_reset_request, name='password_reset_request'),
    # Updated to use base64-encoded user ID for password reset
    path('auth/password/reset/validate/<str:uidb64>/<str:token>/', api.validate_password_reset_token, name='validate_password_reset_token'),
    path('auth/password/reset/update/<str:uidb64>/<str:token>/', api.update_password_with_token, name='update_password_with_token'),
    path('auth/users/me/', api.user_profile, name='user_profile'),
    path('auth/social/jwt/', api.social_login_jwt, name='social_login_jwt'),
    path('auth/social/<str:provider>/', api.social_login, name='social_login'),
    path('auth/social/complete/<str:provider>/', api.social_login_complete, name='social_login_complete'),
    # Updated to use base64-encoded user ID for account activation
    path('auth/activate/<str:uidb64>/<str:token>/', api.show_activation_form, name='show_activation_form'),
    path('auth/activate/post/<str:uidb64>/<str:token>/', api.activate_account, name='activate_account'),

    # Existing API endpoints
    path('homepage-content/', api.homepage_content_api, name='homepage_content_api'),
    path('legal-pages/<slug:slug>/', api.legal_pages_api, name='legal_pages_api'),
    path('card-logos/', api.card_logos_api, name='card_logos_api'),
]