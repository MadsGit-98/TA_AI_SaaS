from django.core.management.base import BaseCommand
from apps.accounts.models import HomePageContent

class Command(BaseCommand):
    help = 'Add placeholder subscription plan information to HomePageContent'

    def handle(self, *args, **options):
        # Check if HomePageContent already exists to avoid duplicates
        if HomePageContent.objects.exists():
            self.stdout.write(
                self.style.WARNING('HomePageContent already exists. Skipping placeholder data creation.')
            )
            return

        # Create HomePageContent with placeholder data
        home_content = HomePageContent.objects.create(
            title="X-Crewter - AI-Powered Resume Analysis for Talent Acquisition",
            subtitle="Automate Your Hiring Process",
            description=(
                "X-Crewter helps Talent Acquisition Specialists automatically analyze, "
                "score (0-100), and categorize bulk resumes (PDF/Docx), significantly "
                "reducing screening time. Our AI-powered platform streamlines the "
                "candidate evaluation process for SMBs."
            ),
            call_to_action_text="Get Started Free",
            pricing_info=(
                "Basic Plan: $29/month - Up to 50 resume analyses\n"
                "Professional Plan: $79/month - Up to 200 resume analyses\n"
                "Enterprise Plan: $199/month - Unlimited resume analyses\n"
                "\nAll plans include AI analysis, custom screening questions, and detailed reports."
            )
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created placeholder HomePageContent: {home_content.title}'
            )
        )