# Quickstart Guide: Secure JWT Refresh and Storage System

## Overview
This guide provides instructions for implementing and using the secure JWT refresh and storage system that stores tokens in Http-Only cookies.

## Prerequisites
- Python 3.11+
- Django 6.0+
- Django REST Framework
- djangorestframework-simplejwt

## Installation

1. Install required dependencies:
   ```bash
   pip install djangorestframework-simplejwt
   ```

2. Add to INSTALLED_APPS in settings.py:
   ```python
   INSTALLED_APPS = [
       # ... other apps
       'rest_framework_simplejwt',
       'rest_framework_simplejwt.token_blacklist',  # For token rotation
   ]
   ```

3. Configure JWT settings in settings.py:
   ```python
   from datetime import timedelta

   SIMPLE_JWT = {
       'ACCESS_TOKEN_LIFETIME': timedelta(minutes=25),  # Will be refreshed 5 min before expiry
       'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
       'ROTATE_REFRESH_TOKENS': True,
       'BLACKLIST_AFTER_ROTATION': True,
       'UPDATE_LAST_LOGIN': False,
   }
   ```

## Implementation Steps

### 1. Update Authentication Backend
Modify `apps/accounts/authentication.py` to prioritize cookie-based token extraction:

```python
# Custom JWT authentication class to extract tokens from cookies
class CookieBasedJWTAuthentication(JWTAuthentication):
    def get_raw_token(self, request):
        # First try to get token from cookies
        if request.COOKIES.get('access_token'):
            return request.COOKIES.get('access_token').encode('utf-8')
        
        # Fallback to Authorization header
        return super().get_raw_token(request)
```

### 2. Create Cookie Token Refresh View
Create a view in `apps/accounts/api.py` to handle token refresh via cookies:

```python
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cookie_token_refresh(request):
    # The JWT middleware has already authenticated the user
    # Generate new tokens
    refresh = RefreshToken.for_user(request.user)
    
    # Set new tokens in Http-Only cookies
    response = Response({'detail': 'Token refreshed successfully'})
    response.set_cookie(
        'access_token',
        str(refresh.access_token),
        httponly=True,
        secure=True,  # Set to False in development with HTTP
        samesite='Lax',
        max_age=60 * 25  # 25 minutes, to be refreshed before expiry
    )
    response.set_cookie(
        'refresh_token',
        str(refresh),
        httponly=True,
        secure=True,  # Set to False in development with HTTP
        samesite='Lax',
        max_age=60 * 60 * 24 * 7  # 7 days
    )
    
    return response
```

### 3. Update URL Configuration
Add the refresh endpoint to `apps/accounts/api_urls.py`:

```python
from . import api

urlpatterns = [
    # ... other URLs
    path('auth/token/refresh/', api.cookie_token_refresh, name='cookie_token_refresh'),
]
```

### 4. Frontend Integration
Update your frontend API client to handle cookies:

```javascript
// Configure axios to include credentials (cookies) in requests
axios.defaults.withCredentials = true;

// Add interceptor to handle 401 responses and trigger refresh
axios.interceptors.response.use(
  response => response,
  async error => {
    if (error.response?.status === 401) {
      // Attempt token refresh
      try {
        await axios.post('/api/accounts/auth/token/refresh/');
        // Retry original request
        return axios.request(error.config);
      } catch (refreshError) {
        // Redirect to login if refresh fails
        window.location.href = '/login/';
      }
    }
    return Promise.reject(error);
  }
);
```

## Testing

1. Unit tests should verify:
   - Tokens are correctly stored in Http-Only cookies
   - Token refresh works properly
   - Inactive users are prevented from obtaining tokens
   - Refresh token rotation occurs

2. Integration tests should verify:
   - End-to-end authentication flow
   - Automatic token refresh
   - Proper cookie security attributes

## Security Considerations

1. Always use HTTPS in production (Secure cookie attribute)
2. Implement CSRF protection for state-changing requests
3. Rotate refresh tokens on each use
4. Set appropriate expiration times for tokens
5. Ensure cookies are not accessible via JavaScript (HttpOnly)
6. Use SameSite=Lax to prevent CSRF attacks