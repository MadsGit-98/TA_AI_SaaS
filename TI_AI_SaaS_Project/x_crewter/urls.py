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
from django.urls import path, include
from django.views.generic import TemplateView
from django.http import JsonResponse


def home_view(request):
    """
    Render and return the site's home page.
    
    Parameters:
        request (HttpRequest): The incoming Django request.
    
    Returns:
        HttpResponse: Response containing the rendered 'home.html' template.
    """
    return TemplateView.as_view(template_name='home.html')(request)


def health_check(request):
    """
    Provide a simple JSON health check for the API.
    
    Returns:
        JsonResponse: JSON object with keys:
            - 'status': 'healthy'
            - 'timestamp': placeholder string 'datetime' (will be replaced with an actual timestamp)
    """
    return JsonResponse({'status': 'healthy', 'timestamp': 'datetime'})  # Timestamp will be implemented in future


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_view, name='home'),
    path('api/health/', health_check, name='health_check'),
    path('api/auth/', include('apps.accounts.urls')),
    path('api/jobs/', include('apps.jobs.urls')),
    path('api/applications/', include('apps.applications.urls')),
    path('api/analysis/', include('apps.analysis.urls')),
    path('api/subscription/', include('apps.subscription.urls')),
]