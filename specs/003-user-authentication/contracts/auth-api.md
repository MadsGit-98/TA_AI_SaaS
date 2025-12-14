# Authentication API Contracts

## Base URL
`/api/auth/`

## Authentication Endpoints

### 1. User Registration
**POST** `/api/auth/register/`

#### Request
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "first_name": "John",
  "last_name": "Doe"
}
```

#### Response (Success - 201 Created)
```json
{
  "user": {
    "id": 1,
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  },
  "access": "jwt_access_token",
  "refresh": "jwt_refresh_token"
}
```

#### Response (Error - 400 Bad Request)
```json
{
  "email": ["Enter a valid email address."],
  "password": ["This password is too short. It must contain at least 8 characters.",
               "This password is too common.",
               "This password is entirely numeric."]
}
```

### 2. User Login
**POST** `/api/auth/login/`

#### Request
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

#### Response (Success - 200 OK)
```json
{
  "user": {
    "id": 1,
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  },
  "access": "jwt_access_token",
  "refresh": "jwt_refresh_token"
}
```

#### Response (Error - 400/401)
```json
{
  "non_field_errors": ["Unable to log in with provided credentials."]
}
```

### 3. User Logout
**POST** `/api/auth/logout/`

#### Request Headers
```
Authorization: Bearer {access_token}
```

#### Request Body
```json
{
  "refresh": "refresh_token_to_blacklist"
}
```

#### Response (Success - 204 No Content)
```
No content
```

### 4. Token Refresh
**POST** `/api/auth/token/refresh/`

#### Request
```json
{
  "refresh": "current_refresh_token"
}
```

#### Response (Success - 200 OK)
```json
{
  "access": "new_access_token"
}
```

### 5. Request Password Reset
**POST** `/api/auth/password/reset/`

#### Request
```json
{
  "email": "user@example.com"
}
```

#### Response (Success - 200 OK)
```json
{
  "detail": "Password reset e-mail has been sent."
}
```

#### Response (Error - 400 Bad Request)
```json
{
  "email": ["This field is required."],
  "detail": "No user found with the given email."
}
```

### 6. Confirm Password Reset
**POST** `/api/auth/password/reset/confirm/`

#### Request
```json
{
  "uid": "user_id_base64_encoded",
  "token": "password_reset_token",
  "new_password": "NewSecurePassword123!",
  "re_new_password": "NewSecurePassword123!"
}
```

#### Response (Success - 200 OK)
```json
{
  "detail": "Password has been reset successfully."
}
```

### 7. Social Login
**POST** `/api/auth/social/{provider}/`

Where `{provider}` can be `google`, `linkedin`, or `microsoft`

#### Request
```json
{
  "access_token": "oauth_provider_access_token"
}
```

#### Response (Success - 200 OK)
```json
{
  "user": {
    "id": 1,
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  },
  "access": "jwt_access_token",
  "refresh": "jwt_refresh_token"
}
```

### 8. Get User Profile
**GET** `/api/auth/users/me/`

#### Request Headers
```
Authorization: Bearer {access_token}
```

#### Response (Success - 200 OK)
```json
{
  "id": 1,
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "subscription_status": "active",
  "subscription_end_date": "2023-12-31T23:59:59Z",
  "chosen_subscription_plan": "pro"
}
```

### 9. Update User Profile
**PATCH** `/api/auth/users/me/`

#### Request Headers
```
Authorization: Bearer {access_token}
```

#### Request
```json
{
  "first_name": "Jane",
  "last_name": "Smith"
}
```

#### Response (Success - 200 OK)
```json
{
  "id": 1,
  "email": "user@example.com",
  "first_name": "Jane",
  "last_name": "Smith",
  "subscription_status": "active",
  "subscription_end_date": "2023-12-31T23:59:59Z",
  "chosen_subscription_plan": "pro"
}
```

## Rate Limiting

All authentication endpoints are subject to rate limiting:
- Maximum 5 failed login attempts per 15 minutes
- Excessive requests will result in temporary blocking

## Security Considerations

1. All authentication-related endpoints must use HTTPS
2. JWT tokens should be stored securely on the client-side
3. Refresh tokens should be rotated after use
4. All sensitive operations require valid authentication tokens
5. Password reset links expire after 24 hours