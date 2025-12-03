#!/bin/bash

# X-Crewter Test Runner Script
# This script provides convenient commands for running tests

echo "=========================================="
echo "X-Crewter TA AI SaaS - Test Runner"
echo "=========================================="
echo ""

# Function to run all tests
run_all_tests() {
    echo "Running all tests..."
    python manage.py test --verbosity=2
}

# Function to run specific app tests
run_app_tests() {
    echo "Running tests for app: $1"
    python manage.py test apps.$1 --verbosity=2
}

# Function to run core tests
run_core_tests() {
    echo "Running core component tests..."
    python manage.py test test_urls test_celery_app test_manage test_app_configs --verbosity=2
}

# Function to run integration tests
run_integration_tests() {
    echo "Running integration tests..."
    python manage.py test test_integration --verbosity=2
}

# Main menu
if [ $# -eq 0 ]; then
    echo "Usage: ./run_tests.sh [option]"
    echo ""
    echo "Options:"
    echo "  all              - Run all tests"
    echo "  accounts         - Run accounts app tests"
    echo "  analysis         - Run analysis app tests"
    echo "  applications     - Run applications app tests"
    echo "  jobs             - Run jobs app tests"
    echo "  subscription     - Run subscription app tests"
    echo "  core             - Run core component tests"
    echo "  integration      - Run integration tests"
    echo "  coverage         - Run tests with coverage report"
    echo ""
    exit 1
fi

case "$1" in
    all)
        run_all_tests
        ;;
    accounts|analysis|applications|jobs|subscription)
        run_app_tests $1
        ;;
    core)
        run_core_tests
        ;;
    integration)
        run_integration_tests
        ;;
    coverage)
        echo "Running tests with coverage..."
        coverage run --source='.' manage.py test
        coverage report
        echo ""
        echo "To generate HTML report, run: coverage html"
        ;;
    *)
        echo "Unknown option: $1"
        echo "Run './run_tests.sh' without arguments to see available options"
        exit 1
        ;;
esac