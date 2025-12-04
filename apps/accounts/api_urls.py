from django.urls import path
from . import api

app_name = 'api'
urlpatterns = [
    # API endpoints
    path('homepage-content/', api.homepage_content_api, name='homepage_content_api'),
    path('legal-pages/<slug:slug>/', api.legal_pages_api, name='legal_pages_api'),
    path('card-logos/', api.card_logos_api, name='card_logos_api'),
]