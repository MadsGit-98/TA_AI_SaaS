from rest_framework import serializers
from .models import HomePageContent, LegalPage, CardLogo


class HomePageContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = HomePageContent
        fields = ['title', 'subtitle', 'description', 'call_to_action_text', 'pricing_info', 'updated_at']


class LegalPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalPage
        fields = ['title', 'content', 'page_type', 'updated_at']


class CardLogoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CardLogo
        fields = ['id', 'name', 'logo_image', 'display_order']