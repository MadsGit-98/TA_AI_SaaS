# Data Model: UUID Migration

## Overview
This document describes the data model changes required for the UUID migration feature, focusing on the transition from sequential integer primary keys to UUIDv6 for the CustomUser model and related dependencies.

## Entity: CustomUser
### Fields
- **id** (Primary Key): UUIDField (v6) - replaces current AutoField
- **uuid_slug** (Unique): CharField - Base62-encoded opaque identifier for public URLs
- [other existing fields remain unchanged]

### Relationships
- One-to-One: UserProfile (related_name='user')
- One-to-Many: VerificationToken (related_name='user')
- One-to-Many: SocialAccount (related_name='user')
- [other existing relationships remain unchanged]

### Validation Rules
- id must be a valid UUIDv6
- uuid_slug must be unique across all users
- uuid_slug must use Base62 alphabet (0-9, a-z, A-Z)
- uuid_slug must be between 10-22 characters for optimal length

### State Transitions
- User creation: Generates UUIDv6 and Base62 slug
- User deletion: Removes associated UUID and slug from Redis caches

## Entity: UserProfile
### Fields
- **id**: AutoField (unchanged)
- **user_id** (Foreign Key): UUIDField (v6) - references CustomUser.id
- [other existing fields remain unchanged]

### Relationships
- Many-to-One: CustomUser (related_name='profile')

### Validation Rules
- user_id must reference a valid CustomUser.id
- user_id cannot be null

## Entity: VerificationToken
### Fields
- **id**: AutoField (unchanged)
- **user_id** (Foreign Key): UUIDField (v6) - references CustomUser.id
- **token**: CharField (unique)
- [other existing fields remain unchanged]

### Relationships
- Many-to-One: CustomUser (related_name='verification_tokens')

### Validation Rules
- user_id must reference a valid CustomUser.id
- token must be unique across all verification tokens

## Entity: SocialAccount
### Fields
- **id**: AutoField (unchanged)
- **user_id** (Foreign Key): UUIDField (v6) - references CustomUser.id
- [other existing fields remain unchanged]

### Relationships
- Many-to-One: CustomUser (related_name='social_accounts')

### Validation Rules
- user_id must reference a valid CustomUser.id

## Entity: Session
### Fields
- **session_key**: CharField (primary key)
- **session_data**: TextField
- **expire_date**: DateTimeField

### Relationships
- References CustomUser via session data (stores user's UUID)

### Validation Rules
- expire_date must be in the future
- session_data must be valid serialized data

## Entity: Redis Cache Entries
### Structure
- **user_sessions:{uuid}**: Stores session information for user
- **user_activity:{uuid}**: Tracks user activity by UUID
- [other cache entries will be updated to use UUID instead of integer ID]

### Validation Rules
- Keys must use the user's UUID as identifier
- Expire times must be properly set to prevent stale data