#!/usr/bin/env python
"""
Test coverage measurement script
This script runs the test suite and measures code coverage
"""
import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner

if __name__ == "__main__":
    os.environ['DJANGO_SETTINGS_MODULE'] = 'x_crewter.settings'
    django.setup()

    # Import coverage here to allow for better control
    try:
        import coverage
        cov = coverage.Coverage()
        cov.start()

        # Run tests with Django test runner programmatically to avoid sys.exit()
        from django.test.runner import DiscoverRunner
        test_runner = DiscoverRunner(verbosity=2, interactive=False, failfast=False)
        failures = test_runner.run_tests(["apps.accounts.tests"])

        cov.stop()
        cov.save()

        # Report coverage stats
        print("\n" + "="*60)
        print("CODE COVERAGE REPORT")
        print("="*60)
        total_coverage = cov.report(show_missing=True)

        print("\n" + "="*60)
        print(f"Total Coverage: {total_coverage}%")

        if total_coverage >= 90.0:
            print("✓ Coverage requirement (90%) satisfied!")
        else:
            print(f"✗ Coverage requirement (90%) not met. Current: {total_coverage}%")

        # Exit based on test failures after coverage reporting
        if failures > 0 or total_coverage < 90.0:
            sys.exit(1)
        else:
            sys.exit(0)
    except ImportError:
        print("Coverage module not installed. Please install it with: pip install coverage")
        # Run tests without coverage using the Django test runner
        from django.test.runner import DiscoverRunner
        test_runner = DiscoverRunner(verbosity=2, interactive=False, failfast=False)
        failures = test_runner.run_tests(["apps.accounts.tests"])
        sys.exit(0 if failures == 0 else 1)