from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required


@login_required
def subscription_detail_view(request):
    """
    Placeholder for subscription detail endpoint
    Future implementation will return subscription information
    """
    # Render the landing page template for non-subscribed users
    return render(request, 'subscription/landing_page.html')
