#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """
    Configure Django settings and run the project's command-line management utility.
    
    If the environment variable DJANGO_SETTINGS_MODULE is not set, it is set to 'x_crewter.settings' before invoking Django's command runner with the current process arguments.
    
    Raises:
        ImportError: If Django cannot be imported; the exception message explains the likely causes (missing installation, PYTHONPATH, or inactive virtual environment).
    """
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'x_crewter.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()