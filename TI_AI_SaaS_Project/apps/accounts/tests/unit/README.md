# Unit Tests for Accounts App

This directory contains comprehensive unit tests for the accounts application, focusing on authentication, authorization, and user management functionality.

## Running the Tests

### Run All Unit Tests
```bash
cd TI_AI_SaaS_Project
python manage.py test apps.accounts.tests.unit
```

### Run Specific Test File
```bash
# Test API helpers
python manage.py test apps.accounts.tests.unit.test_api_helpers

# Test authentication backend
python manage.py test apps.accounts.tests.unit.test_authentication_backend

# Test middleware
python manage.py test apps.accounts.tests.unit.test_middleware

# Test models
python manage.py test apps.accounts.tests.unit.test_models

# Test serializers
python manage.py test apps.accounts.tests.unit.test_serializers

# Test API endpoints
python manage.py test apps.accounts.tests.unit.test_api_endpoints

# Test pipeline
python manage.py test apps.accounts.tests.unit.test_pipeline_extended
```

### Run Specific Test Class
```bash
python manage.py test apps.accounts.tests.unit.test_api_helpers.MaskEmailTestCase
```

### Run with Verbose Output
```bash
python manage.py test apps.accounts.tests.unit --verbosity=2
```

### Run with Coverage Report
```bash
# Install coverage if not already installed
pip install coverage

# Run tests with coverage
coverage run --source='apps.accounts' manage.py test apps.accounts.tests.unit

# Generate coverage report
coverage report

# Generate HTML coverage report
coverage html
# Open htmlcov/index.html in your browser
```

## Test File Overview

### New Test Files

#### test_api_helpers.py
Tests for utility functions and throttle classes:
- `MaskEmailTestCase` - Email masking for privacy
- `GetClientIpTestCase` - IP address extraction
- `GetRedirectUrlAfterLoginTestCase` - Post-login routing
- `SendActivationEmailTestCase` - Email delivery
- `SendPasswordResetEmailTestCase` - Password reset emails
- `ThrottleClassesTestCase` - Rate limiting logic

#### test_authentication_backend.py
Tests for the custom authentication backend:
- `EmailOrUsernameBackendTestCase` - Login with email or username
- Timing attack mitigation
- Inactive user handling
- Case sensitivity tests

#### test_middleware.py
Tests for RBAC middleware:
- `RBACMiddlewareTestCase` - Role-based access control
- Protected path enforcement
- Permission validation
- Missing profile handling

#### test_pipeline_extended.py
Extended tests for social authentication:
- `SaveProfilePipelineTestCase` - OAuth profile handling
- `CreateUserIfNotExistsTestCase` - User creation logic
- `LinkExistingUserTestCase` - Account linking
- `CreateUserProfileTestCase` - Profile initialization

#### test_api_endpoints.py
Comprehensive API endpoint tests:
- `ActivateAccountEndpointTestCase` - Account activation
- `UserProfileEndpointTestCase` - Profile management
- `LogoutEndpointTestCase` - Logout functionality
- `PasswordResetRequestEndpointTestCase` - Password reset flow
- `SocialLoginJWTEndpointTestCase` - Social authentication
- `TokenRefreshEndpointRateLimitingTestCase` - Rate limiting

### Extended Test Files

#### test_serializers.py (Extended)
Additional serializer validation tests:
- Password complexity requirements
- Email uniqueness validation
- Profile field serialization
- Update operations

#### test_models.py (Extended)
Additional model constraint tests:
- Email uniqueness enforcement
- Profile validation rules
- Token expiry logic
- Cascade delete behavior

## Test Categories

### Happy Path Tests
Tests that verify normal, expected behavior when all inputs are valid.

### Edge Case Tests
Tests that verify behavior with boundary conditions:
- Empty strings
- None values
- Maximum/minimum lengths
- Special characters

### Error Handling Tests
Tests that verify proper error responses:
- Invalid inputs
- Missing required fields
- Database errors
- Network failures

### Security Tests
Tests that verify security features:
- Timing attack mitigation
- User enumeration prevention
- Rate limiting
- Token validation

## Common Test Patterns

### Setup and Teardown
```python
def setUp(self):
    """Run before each test"""
    self.user = User.objects.create_user(...)
    
def tearDown(self):
    """Run after each test"""
    cache.clear()
```

### Mocking External Dependencies
```python
@patch('apps.accounts.api.send_mail')
def test_email_sending(self, mock_send_mail):
    # Test code here
    mock_send_mail.assert_called_once()
```

### Testing API Endpoints
```python
response = self.client.post(url, data, format='json')
self.assertEqual(response.status_code, status.HTTP_200_OK)
self.assertIn('expected_field', response.data)
```

## Debugging Failed Tests

### View Test Output
```bash
python manage.py test apps.accounts.tests.unit --verbosity=2
```

### Run Single Test
```bash
python manage.py test apps.accounts.tests.unit.test_api_helpers.MaskEmailTestCase.test_mask_email_valid_email
```

### Enable Debug Logging
Add to your test settings:
```python
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

## Contributing

When adding new tests:
1. Follow existing naming conventions
2. Add docstrings explaining what the test does
3. Use descriptive test names: `test_<function>_<scenario>`
4. Clean up resources in tearDown
5. Mock external dependencies
6. Test both success and failure cases

## Additional Resources

- [Django Testing Documentation](https://docs.djangoproject.com/en/stable/topics/testing/)
- [Django REST Framework Testing](https://www.django-rest-framework.org/api-guide/testing/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)