# Secure JWT Authentication System Documentation

## Overview
This document describes the secure JWT refresh and storage system that transitions the application from client-side JavaScript token management to a secure, browser-managed Http-Only cookie storage model.

## Architecture

### Components
1. **Cookie-Based JWT Authentication**: Custom authentication class that extracts tokens from HttpOnly cookies
2. **Token Refresh Mechanism**: Automatic refresh 5 minutes before token expiration
3. **Session Management**: 60-minute inactivity timeout with automatic logout
4. **Security Features**: HttpOnly, Secure, SameSite=Lax cookie attributes

### Files
- `apps/accounts/authentication.py`: Custom JWT authentication class
- `apps/accounts/api.py`: Login, logout, and token refresh endpoints
- `apps/accounts/utils.py`: Cookie utility functions
- `apps/accounts/session_utils.py`: Session timeout utilities
- `apps/accounts/middleware.py`: Session timeout and RBAC middleware

## Implementation Details

### Cookie Storage
- Access tokens stored in `access_token` cookie
- Refresh tokens stored in `refresh_token` cookie
- All cookies use HttpOnly, Secure, and SameSite=Lax attributes
- Access tokens expire after 25 minutes (refreshed automatically)
- Refresh tokens expire after 7 days

### Token Refresh
- Automatic refresh 5 minutes before access token expiration
- Refresh tokens are rotated on each use
- Uses `/api/accounts/auth/token/cookie-refresh/` endpoint
- Frontend should monitor token expiration and call refresh endpoint

### Session Timeout
- 60-minute inactivity timeout
- Activity tracked via API calls to protected endpoints
- Session cleared when timeout reached
- Implemented via SessionTimeoutMiddleware

### Security Measures
- HttpOnly cookies prevent XSS attacks
- SameSite=Lax attribute prevents CSRF attacks
- Refresh token rotation prevents replay attacks
- User active status verified on each authentication

## API Endpoints

### Login: `POST /api/accounts/auth/login/`
- Request: `{"username": "user", "password": "pass"}`
- Response: User data (no tokens in response body)
- Sets `access_token` and `refresh_token` cookies

### Logout: `POST /api/accounts/auth/logout/`
- Request: No body required
- Response: 204 No Content
- Clears authentication cookies

### Token Refresh: `POST /api/accounts/auth/token/cookie-refresh/`
- Request: No body required (uses cookies)
- Response: Success message
- Sets new `access_token` and `refresh_token` cookies

### User Profile: `GET /api/accounts/auth/users/me/`
- Response: User profile data
- Updates activity timestamp for session timeout

## Frontend Integration

### JavaScript Configuration
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
        await axios.post('/api/accounts/auth/token/cookie-refresh/');
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

### Unit Tests
Located in `apps/accounts/tests/unit/`
- `test_jwt_authentication.py`: Core authentication functionality
- `test_inactive_user_prevention.py`: Inactive user handling

### Integration Tests
Located in `apps/accounts/tests/integration/`
- `test_jwt_authentication_integration.py`: Complete flow tests

### Security Tests
Located in `apps/accounts/tests/security/`
- `test_jwt_security.py`: XSS, CSRF, and token security tests

## Configuration

### Settings
- `SIMPLE_JWT.ACCESS_TOKEN_LIFETIME`: 25 minutes
- `TOKEN_REFRESH_CONFIG.REFRESH_THRESHOLD_SECONDS`: 300 (5 minutes)

## Error Handling

### Common Error Responses
- `400 Bad Request`: Invalid credentials or inactive account
- `401 Unauthorized`: Invalid or expired token, inactive user
- `429 Too Many Requests`: Rate limiting exceeded

## Deployment Notes

### Production Requirements
- HTTPS required for Secure cookie attribute
- Redis required for session timeout tracking
- Proper CORS configuration for credentials

### Environment Variables
- `REDIS_URL`: URL for Redis connection (default: redis://localhost:6379/0)
- `DEBUG`: Set to False in production (affects cookie Secure attribute)