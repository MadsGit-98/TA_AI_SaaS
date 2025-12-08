"""
URL configuration for x_crewter project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
import os


def health_check(request):
    """API health check endpoint"""
    return JsonResponse({'status': 'healthy', 'timestamp': 'datetime'})  # Timestamp will be implemented in future


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.accounts.urls')),  # Include accounts URLs for home page and auth
    path('api/health/', health_check, name='health_check'),
    path('api/accounts/', include('apps.accounts.api_urls')),
    path('api/jobs/', include('apps.jobs.urls')),
    path('api/applications/', include('apps.applications.urls')),
    path('api/analysis/', include('apps.analysis.urls')),
    path('api/subscription/', include('apps.subscription.urls')),
]

# Only add additional URL patterns after all API routes to avoid conflicts
# If there's a need for frontend routing fallback, it should be done properly


# Add fallback pattern for frontend routing (only after all specific routes)
# This ensures the home page remains the landing page for unmatched routes
from django.shortcuts import redirect

def fallback_view(request, *args, **kwargs):
    """Redirect unknown routes to home page to avoid static file serving errors"""
    # Use absolute URL path instead of name to avoid namespace issues
    return redirect('/')

urlpatterns += [
    # Catch all other routes and redirect to home page (avoiding static serve errors)
    re_path(r'^(?!api(?:/|$)|admin(?:/|$)).*$', fallback_view, name='fallback'),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# In production, if using a separate frontend, you might need a catch-all route
# but only after all API and admin routes are defined
# For now, we're ensuring that the home page remains the landing page
# and API routes are properly handled without conflicts
