from django.core.management.base import BaseCommand
from apps.accounts.models import SiteSetting, CardLogo
from django.core.files.base import ContentFile
import tempfile
import os


class Command(BaseCommand):
    help = 'Add SiteSetting and CardLogo placeholder data'

    def handle(self, *args, **options):
        # Add SiteSetting for currency display
        currency_setting, created = SiteSetting.objects.get_or_create(
            setting_key='currency_display',
            defaults={
                'setting_value': 'USD, EUR, GBP',
                'description': 'Currency display information shown in footer'
            }
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created SiteSetting: {currency_setting.setting_key}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'SiteSetting already exists: {currency_setting.setting_key}')
            )
        
        # Add SiteSetting for contact information
        contact_setting, created = SiteSetting.objects.get_or_create(
            setting_key='contact_email',
            defaults={
                'setting_value': 'info@x-crewter.com',
                'description': 'Contact email address shown in footer'
            }
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created SiteSetting: {contact_setting.setting_key}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'SiteSetting already exists: {contact_setting.setting_key}')
            )
        
        # Add CardLogo entries
        card_logos = [
            {'name': 'Visa', 'display_order': 1, 'description': 'Visa logo'},
            {'name': 'Mastercard', 'display_order': 2, 'description': 'Mastercard logo'},
            {'name': 'American Express', 'display_order': 3, 'description': 'American Express logo'},
        ]
        
        for card in card_logos:
            card_logo, created = CardLogo.objects.get_or_create(
                name=card['name'],
                defaults={
                    'display_order': card['display_order'],
                    'is_active': True,
                    'description': card['description']
                }
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully created CardLogo: {card_logo.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'CardLogo already exists: {card_logo.name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS('Successfully added SiteSetting and CardLogo data')
        )