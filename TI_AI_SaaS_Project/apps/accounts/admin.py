from django.contrib import admin
from .models import HomePageContent, LegalPage, CardLogo, SiteSetting

@admin.register(HomePageContent)
class HomePageContentAdmin(admin.ModelAdmin):
    list_display = ('title', 'subtitle', 'updated_at')
    search_fields = ('title', 'description')
    list_filter = ('updated_at',)
    readonly_fields = ('created_at', 'updated_at')

@admin.register(LegalPage)
class LegalPageAdmin(admin.ModelAdmin):
    list_display = ('title', 'page_type', 'is_active', 'updated_at')
    list_filter = ('page_type', 'is_active', 'updated_at')
    search_fields = ('title', 'content')
    prepopulated_fields = {'slug': ('title',)}

@admin.register(CardLogo)
class CardLogoAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_order', 'is_active', 'created_at')
    list_filter = ('is_active', 'display_order')
    search_fields = ('name',)

@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ('setting_key', 'updated_at')
    list_filter = ('updated_at',)
    search_fields = ('setting_key', 'setting_value')
    readonly_fields = ('updated_at',)
