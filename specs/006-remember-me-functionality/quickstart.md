# Quickstart Guide: Remember Me Functionality

## Overview
This guide explains how to implement and use the "Remember Me" functionality in the X-Crewter application. The feature allows users to maintain extended sessions beyond the standard 26-minute inactivity timeout.

## Frontend Implementation

### 1. Update Login Form JavaScript
Modify `apps/accounts/static/js/auth.js` to include the "remember_me" flag in login requests:

```javascript
async function handleLogin(e) {
    e.preventDefault();

    // ... existing code ...

    // Get remember me setting
    const rememberMeCheckbox = document.getElementById('remember-me');
    const rememberMe = rememberMeCheckbox ? rememberMeCheckbox.checked : false;

    // Include rememberMe in form data
    const formData = {
        username: document.getElementById('login-email').value,
        password: document.getElementById('login-password').value,
        remember_me: rememberMe  // Add this line
    };

    // ... rest of existing code ...
}
```

### 2. Update Auth Interceptor
Modify `apps/jobs/static/js/auth-interceptor.js` to handle different refresh intervals:

```javascript
// Call checkAndRefreshToken based on remember me status
if (rememberMeChecked) {
    // Refresh token every 20 minutes for remember me sessions
    setInterval(checkAndRefreshToken, 20 * 60 * 1000);
} else {
    // Only refresh when user is active for standard sessions
    handleUserActivity();  // Existing behavior
}
```

## Backend Implementation

### 1. Update Login Serializer
Modify `apps/accounts/serializers.py` to accept the remember_me field:

```python
class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True, help_text="Username or email address")
    password = serializers.CharField(required=True, write_only=True)
    remember_me = serializers.BooleanField(default=False, required=False)  # Add this line
```

### 2. Update Login API
Modify `apps/accounts/api.py` to process the remember_me flag:

```python
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle, LoginAttemptThrottle])
def login(request):
    # ... existing code until token generation ...

    if user is not None:
        if user.is_active:
            auth_login(request, user)
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            # Get remember_me flag from request
            remember_me = serializer.validated_data.get('remember_me', False)
            
            # Trigger the refresh_user_token task with remember_me flag
            refresh_user_token.delay(user.id, remember_me=remember_me)

            # ... rest of existing code ...
```

### 3. Update Celery Tasks
Modify `apps/accounts/tasks.py` to handle the remember_me flag:

```python
@app.task
def refresh_user_token(user_id, remember_me=False):
    """
    Refresh the token for a specific user
    If remember_me is True, create auto-refresh entry in Redis
    """
    logger.info(f"Refreshing token for user ID: {user_id}, remember_me: {remember_me}")

    try:
        # ... existing code ...

        if remember_me:
            # Create auto-refresh entry in Redis for remember me sessions
            auto_refresh_key = f"auto_refresh:{user_id}"
            auto_refresh_data = {
                'session_token': str(uuid.uuid4()),  # Generate unique session token
                'expires_at': (timezone.now() + timedelta(days=30)).timestamp(),
                'last_refresh': timezone.now().timestamp()
            }
            redis_client.setex(
                auto_refresh_key,
                timedelta(days=30),  # 30-day expiration
                json.dumps(auto_refresh_data, default=str)
            )

        # ... rest of existing code ...
    except Exception as e:
        logger.error(f"Error refreshing token for user {user_id}: {str(e)}")
        return {'error': f'Error refreshing token for user {user_id}: {str(e)}'}

@app.task
def monitor_and_refresh_tokens():
    """
    Celery task to monitor user tokens and refresh them before expiration.
    Modified to handle Remember Me sessions differently.
    """
    # ... existing code ...

    for key in token_keys:
        try:
            # ... existing code until the conditional ...

            # Check if this user has an active "Remember Me" session
            auto_refresh_key = f"auto_refresh:{user_id}"
            has_remember_me = redis_client.exists(auto_refresh_key)

            # For Remember Me sessions, ignore inactivity and refresh based on expiration only
            if has_remember_me:
                tokens_to_refresh.append(user_id)
                logger.info(f"Remember Me session for user {user_id} expires at {token_expire_time}, marking for refresh")
            else:
                # Standard session logic (existing behavior)
                last_activity = get_last_user_activity(user_id)
                if last_activity:
                    current_time = timezone.now().timestamp()
                    time_since_activity = current_time - last_activity
                    
                    if time_since_activity <= (26 * 60):  # 26 minutes in seconds
                        tokens_to_refresh.append(user_id)
                        logger.info(f"Standard session for user {user_id} expires at {token_expire_time}, marking for refresh (user was recently active)")
                    else:
                        tokens_to_logout.append(user_id)
                        logger.info(f"Standard session for user {user_id} expires at {token_expire_time} with no recent activity, marking for logout")
                else:
                    tokens_to_logout.append(user_id)
                    logger.info(f"Standard session for user {user_id} expires at {token_expire_time} with no activity record, marking for logout")

        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Error processing token key {key}: {str(e)}")
            continue

    # ... rest of existing code ...
```

## Testing the Implementation

### 1. Unit Tests
Create unit tests in `apps/accounts/tests/unit/` to verify the remember me functionality:

```python
# Test that remember_me flag is processed correctly in login
def test_login_with_remember_me():
    # Create user and login data with remember_me=True
    # Verify that the appropriate session tokens are created
    # Verify that Redis entries are created for remember me sessions
    pass

# Test that remember_me sessions are handled differently in monitor task
def test_monitor_task_handles_remember_me_sessions():
    # Create a remember me session in Redis
    # Run the monitor_and_refresh_tokens task
    # Verify that the session is refreshed despite inactivity
    pass
```

### 2. Integration Tests
Create integration tests in `apps/accounts/tests/integration/` to verify end-to-end functionality:

```python
# Test the complete remember me flow from login to token refresh
def test_remember_me_flow():
    # Simulate user login with remember_me checked
    # Verify extended session behavior
    # Verify automatic token refresh
    pass
```

## Security Considerations

1. Remember Me sessions should be limited to one per user at a time
2. When a user logs out, all active Remember Me sessions should be terminated
3. Remember Me sessions should have a maximum lifespan (e.g., 30 days)
4. Monitor for suspicious activity on Remember Me sessions

## Troubleshooting

### Common Issues:
- Remember Me sessions not persisting: Check Redis connectivity and expiration settings
- Tokens not refreshing: Verify Celery worker is running and processing tasks
- Conflicting sessions: Ensure only one Remember Me session per user is allowed