from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser,
    HomePageContent,
    LegalPage,
    CardLogo,
    SiteSetting,
    UserProfile,
    VerificationToken,
    SocialAccount
)

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined')

    # Include all fields from the parent UserAdmin
    fieldsets = UserAdmin.fieldsets
    add_fieldsets = UserAdmin.add_fieldsets

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'subscription_status', 'chosen_subscription_plan', 'is_talent_acquisition_specialist', 'updated_at')
    list_filter = ('subscription_status', 'chosen_subscription_plan', 'is_talent_acquisition_specialist', 'updated_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(VerificationToken)
class VerificationTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token_type', 'expires_at', 'is_used', 'created_at')
    list_filter = ('token_type', 'is_used', 'expires_at')
    search_fields = ('user__username', 'user__email', 'token')
    readonly_fields = ('created_at',)

@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'provider', 'provider_account_id', 'date_connected')
    list_filter = ('provider', 'date_connected')
    search_fields = ('user__username', 'user__email', 'provider', 'provider_account_id')

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
