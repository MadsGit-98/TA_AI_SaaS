# API Contract: User Endpoints with UUID Support

## Overview
This document defines the API contracts for user-related endpoints that will be updated to use UUIDs and opaque slugs instead of sequential integer IDs.

## Authentication Endpoints

### GET /api/users/{uuid}/
Retrieve user profile by UUID

**Path Parameters:**
- uuid (string, required): User's UUIDv6 identifier

**Response:**
- 200: OK - User profile data
- 404: Not Found - User does not exist
- 403: Forbidden - User not authorized to view profile

### GET /api/users/slug/{slug}/
Retrieve user profile by opaque slug

**Path Parameters:**
- slug (string, required): User's Base62-encoded opaque identifier

**Response:**
- 200: OK - User profile data
- 404: Not Found - User does not exist
- 403: Forbidden - User not authorized to view profile

## Password Reset Endpoints

### POST /api/auth/password-reset/
Initiate password reset process

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response:**
- 200: OK - Password reset initiated
- 400: Bad Request - Invalid email format

### POST /api/auth/reset/{uidb64}/{token}/
Reset password with token

**Path Parameters:**
- uidb64 (string, required): Base64 encoded UUID
- token (string, required): Password reset token

**Request Body:**
```json
{
  "new_password1": "newSecurePassword123",
  "new_password2": "newSecurePassword123"
}
```

**Response:**
- 200: OK - Password reset successful
- 400: Bad Request - Invalid passwords or token
- 404: Not Found - User or token not found

## Account Activation Endpoints

### POST /api/auth/activate/{uidb64}/{token}/
Activate account with activation token

**Path Parameters:**
- uidb64 (string, required): Base64 encoded UUID
- token (string, required): Account activation token

**Response:**
- 200: OK - Account activated successfully
- 400: Bad Request - Invalid token
- 404: Not Found - User or token not found

## Session Management

### POST /api/auth/login/
Authenticate user and create session

**Request Body:**
```json
{
  "username": "user@example.com",
  "password": "userPassword123"
}
```

**Response:**
- 200: OK - Login successful, session created
- 400: Bad Request - Invalid credentials
- 403: Forbidden - Account inactive

### DELETE /api/auth/logout/
Log out user and destroy session

**Response:**
- 200: OK - Logout successful
- 401: Unauthorized - Not authenticated