#!/usr/bin/env python
"""Django's command-line utility for the standalone AI service layer.

Run from the project root (TI_AI_SaaS_Project/):
    python services/manage.py runserver 0.0.0.0:9000
    python services/manage.py check
    python services/manage.py test services.tests
"""
import os
import sys
from pathlib import Path


def main():
    """Run administrative tasks for the AI service layer."""
    # Ensure the project root (TI_AI_SaaS_Project/) is on sys.path so that
    # `services.*` imports resolve when this script is run directly.
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'services.config.settings')
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
