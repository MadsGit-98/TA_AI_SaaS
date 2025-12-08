# Data Model: User Authentication & Account Management

## Extended User Model (TalentAcquisitionSpecialist)

Based on the requirement to extend the default Django user, we'll create a profile model linked to the default User model via OneToOneField.

### Fields

- **id**: Integer (Primary Key, Auto-generated)
- **user**: OneToOneField (linking to Django's default User model)
- **subscription_status**: CharField
  - Choices: 'active', 'inactive', 'trial', 'cancelled'
  - Default: 'inactive'
- **subscription_end_date**: DateTimeField
  - Nullable: True (null for inactive accounts)
- **chosen_subscription_plan**: CharField
  - Choices: 'basic', 'pro', 'enterprise', 'none'
  - Default: 'none'
- **date_created**: DateTimeField
  - Auto populated: True (on creation)
- **date_updated**: DateTimeField
  - Auto populated: True (on update)
- **is_talent_acquisition_specialist**: BooleanField
  - Default: True (for this user type)

### Relationships
- OneToOne with Django's default User model (auth.User)
- The User model handles: username, email, password, first_name, last_name, is_active, etc.

## Authentication Token Model

For JWT-based authentication, we'll rely on the token generation provided by the libraries rather than creating a custom model.

However, for password reset and email confirmation, we'll need:

### VerificationToken Model
- **id**: Integer (Primary Key, Auto-generated)
- **user**: ForeignKey (to User model)
- **token**: CharField (randomly generated secure token)
- **token_type**: CharField
  - Choices: 'email_confirmation', 'password_reset'
- **expires_at**: DateTimeField (time after which token becomes invalid)
- **created_at**: DateTimeField (auto-populated)
- **is_used**: BooleanField (whether token has been used)

### SocialAccount Model (for social login integration)
- **id**: Integer (Primary Key, Auto-generated)
- **user**: ForeignKey (to User model)
- **provider**: CharField (e.g., 'google', 'linkedin', 'microsoft')
- **provider_account_id**: CharField (unique ID from provider)
- **date_connected**: DateTimeField (auto-populated)
- **extra_data**: JSONField (additional profile data from provider)

## Validation Rules

### User Registration
- Email must be unique
- Password must meet complexity requirements (minimum 8 characters with uppercase, lowercase, numbers, and special characters)
- Username must be unique (if used)

### Subscription Management
- If subscription_status is 'active', then subscription_end_date must not be null
- If subscription_status is 'inactive', then chosen_subscription_plan should be 'none'

### Token Management
- Verification tokens expire after 24 hours (as specified in the requirements)
- Tokens cannot be reused (is_used field)

## State Transitions

### Subscription Status Transitions
- `inactive` → `trial` → `active` → `cancelled` → `inactive`
- `inactive` → `active` (direct upgrade)
- `active` → `inactive` (at end of billing cycle)

### Token State Transitions  
- `created` → `used` (when token is successfully used)
- `created` → `expired` (when token reaches expires_at time)