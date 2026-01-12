# Data Model for Remember Me Functionality

## Entities

### RememberMeSession
Represents a user session with extended lifetime enabled through the "Remember Me" functionality.

**Fields**:
- `user_id` (UUID/string): Reference to the user who owns this session
- `session_token` (string): Unique identifier for this session
- `created_at` (datetime): Timestamp when the session was created
- `expires_at` (datetime): Timestamp when the session expires (30 days from creation)
- `auto_refresh_key` (string): Redis key for automatic token refresh

**Relationships**:
- Belongs to one `User` (via user_id foreign key)

**Validation Rules**:
- `user_id` must reference an existing, active user
- `expires_at` must be exactly 30 days after `created_at`
- Only one active RememberMeSession per user at any time

**State Transitions**:
- ACTIVE (when created) → EXPIRED (when expires_at is reached)
- ACTIVE → TERMINATED (when user explicitly logs out)

## Redis Data Structures

### Auto Refresh Entry
Stored in Redis to track when a user has an active "Remember Me" session that requires automatic refresh.

**Key**: `auto_refresh:{user_id}`
**Value**: JSON object containing:
- `session_token`: The session token for this remember me session
- `expires_at`: Unix timestamp when this session expires
- `last_refresh`: Unix timestamp of the last token refresh

**Expiration**: Matches the session expiration time (30 days)

### Token Expiration Tracking
Modified to include remember me status for differentiation between standard and extended sessions.

**Key**: `token_expires:{user_id}`
**Value**: JSON object containing:
- `expires_at`: Unix timestamp when the token expires
- `remember_me`: Boolean indicating if this is a remember me session
- `last_activity`: Unix timestamp of last user activity (for standard sessions)

**Expiration**: 30 minutes for access token, 30 days for refresh token (remember me sessions)