from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import HomePageContent, LegalPage, CardLogo
from .serializers import HomePageContentSerializer, LegalPageSerializer, CardLogoSerializer


@api_view(['GET'])
def homepage_content_api(request):
    """
    Retrieve configurable content for the home page
    """
    try:
        home_content = HomePageContent.objects.latest('updated_at')
        serializer = HomePageContentSerializer(home_content)
        return Response(serializer.data)
    except HomePageContent.DoesNotExist:
        return Response(
            {'error': 'No homepage content available'}, 
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
def legal_pages_api(request, slug):
    """
    Retrieve content for a specific legal page (privacy policy, terms, etc.)
    """
    try:
        legal_page = LegalPage.objects.get(slug=slug, is_active=True)
        serializer = LegalPageSerializer(legal_page)
        return Response(serializer.data)
    except LegalPage.DoesNotExist:
        return Response(
            {'error': 'Legal page not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
def card_logos_api(request):
    """
    Retrieve information about accepted payment card logos for display
    """
    card_logos = CardLogo.objects.filter(is_active=True).order_by('display_order')
    serializer = CardLogoSerializer(card_logos, many=True)
    return Response(serializer.data)