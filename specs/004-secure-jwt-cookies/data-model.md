# Data Model: Secure JWT Refresh and Storage System

## Entities

### Authentication Token
- **Description**: Represents user's authenticated session state, consisting of access and refresh tokens stored in Http-Only cookies with Secure and SameSite attributes
- **Fields**:
  - token_type: String (access/refresh)
  - token_value: String (JWT token string)
  - user: Reference to CustomUser
  - expires_at: DateTime
  - created_at: DateTime
  - is_rotated: Boolean (for refresh tokens that have been rotated)

### User Session
- **Description**: Represents the duration of authenticated user interaction with the application, managed by the token lifecycle, with automatic termination after 60 minutes of inactivity
- **Fields**:
  - user: Reference to CustomUser
  - session_start: DateTime
  - last_activity: DateTime
  - is_active: Boolean
  - session_timeout: Integer (in minutes, default 60)

### Token Refresh Mechanism
- **Description**: System component responsible for automatically renewing access tokens 5 minutes before expiration and rotating refresh tokens
- **Fields**:
  - refresh_token: String (current refresh token)
  - new_refresh_token: String (new refresh token after rotation)
  - user: Reference to CustomUser
  - last_refresh: DateTime
  - next_refresh: DateTime (when next refresh is scheduled)

## Validation Rules

1. **FR-001**: Authentication tokens must be stored with Http-Only, Secure, and SameSite=Lax attributes
2. **FR-002**: Access tokens must be refreshed 5 minutes before expiration
3. **FR-003**: Inactive users cannot obtain or refresh authentication tokens
4. **FR-009**: CSRF protection must be implemented for all authentication-related endpoints
5. **FR-014**: Refresh tokens must be rotated on each use
6. **FR-015**: Cookies must be restricted to the same domain only
7. **FR-016**: User sessions must terminate after 60 minutes of inactivity

## State Transitions

### Authentication Token States
- **Active**: Token is valid and within expiration time
- **Expired**: Token has exceeded its expiration time
- **Revoked**: Token has been invalidated before expiration (e.g., logout)

### User Session States
- **Active**: User is authenticated and has performed activity within the timeout period
- **Inactive**: User has not performed any activity for more than the timeout period
- **Terminated**: Session has ended due to logout or timeout