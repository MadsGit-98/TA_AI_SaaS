from django.urls import path, include
from . import api

app_name = 'api'
urlpatterns = [
    # Authentication API endpoints
    path('auth/register/', api.register, name='register'),
    path('auth/login/', api.login, name='login'),
    path('auth/logout/', api.logout, name='logout'),
    path('auth/token/refresh/', api.token_refresh, name='token_refresh'),
    path('auth/password/reset/', api.password_reset_request, name='password_reset_request'),
    path('auth/password/reset/confirm/<str:uid>/<str:token>/', api.password_reset_confirm, name='password_reset_confirm'),
    path('auth/users/me/', api.user_profile, name='user_profile'),
    path('auth/users/me/update/', api.update_user_profile, name='update_user_profile'),  # For backward compatibility
    path('auth/social/<str:provider>/', api.social_login, name='social_login'),
    path('auth/social/jwt/', api.social_login_jwt, name='social_login_jwt'),
    path('auth/social/complete/<str:provider>/', api.social_login_complete, name='social_login_complete'),
    path('auth/activate/<str:uid>/<str:token>/', api.activate_account, name='activate_account'),

    # Existing API endpoints
    path('homepage-content/', api.homepage_content_api, name='homepage_content_api'),
    path('legal-pages/<slug:slug>/', api.legal_pages_api, name='legal_pages_api'),
    path('card-logos/', api.card_logos_api, name='card_logos_api'),
]