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
        
        # Run tests with Django test command
        from django.core.management import execute_from_command_line
        execute_from_command_line([sys.argv[0], "test", "apps.accounts.tests", "--verbosity=2"])
        
        cov.stop()
        cov.save()
        
        # Report coverage stats
        print("\n" + "="*60)
        print("CODE COVERAGE REPORT")
        print("="*60)
        cov.report(show_missing=True)
        
        # Get the overall coverage percentage
        total_coverage = cov.report(show_missing=False)
        
        print("\n" + "="*60)
        print(f"Total Coverage: {total_coverage}%")
        
        if total_coverage >= 90.0:
            print("✓ Coverage requirement (90%) satisfied!")
            sys.exit(0)
        else:
            print(f"✗ Coverage requirement (90%) not met. Current: {total_coverage}%")
            sys.exit(1)
            
    except ImportError:
        print("Coverage.py is not installed. Please install it with: pip install coverage")
        # Run tests without coverage
        from django.core.management import execute_from_command_line
        execute_from_command_line([sys.argv[0], "test", "apps.accounts.tests", "--verbosity=2"])
        sys.exit(0)