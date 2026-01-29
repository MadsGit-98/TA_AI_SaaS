# Data Model: Job Listing Management

## Overview
This document defines the data models for the Job Listing Management feature, including entities, their attributes, relationships, and validation rules.

## Entity: JobListing

### Description
Represents a job posting with attributes including title, description, required skills, experience level, start date, expiration date, status (active/inactive), and associated screening questions.

### Fields
- **id**: UUID (Primary Key, auto-generated)
- **title**: String (max_length=200, required)
- **description**: Text (max_length=3000, required)
- **required_skills**: JSONField or ArrayField (required, stores list of skills)
- **required_experience**: Integer (required, years of experience)
- **job_level**: Enum (choices: 'Intern', 'Entry', 'Junior', 'Senior', required)
- **start_date**: DateTime (required, when the job listing becomes active)
- **expiration_date**: DateTime (required, when the job listing becomes inactive)
- **modification_date**: DateTime (auto-updated when edited, initially equals start_date)
- **status**: Enum (choices: 'Active', 'Inactive', default: 'Inactive')
- **application_link**: UUID (unique public link for applications, auto-generated)
- **created_at**: DateTime (auto-created)
- **updated_at**: DateTime (auto-updated)
- **created_by**: ForeignKey to User (Talent Acquisition Specialist who created the listing)

### Validation Rules
- expiration_date must be after start_date
- title must not exceed 200 characters
- description must not exceed 3000 characters
- required_experience must be a positive integer
- status can only be changed by authorized users

### State Transitions
- Created → Inactive (default upon creation)
- Inactive → Active (on start_date or manual activation)
- Active → Inactive (on expiration_date, manual deactivation, or system deactivation)

## Entity: ScreeningQuestion

### Description
Represents custom questions tied to specific job listings to gather targeted information from applicants.

### Fields
- **id**: UUID (Primary Key, auto-generated)
- **job_listing**: ForeignKey to JobListing (required, defines the parent job)
- **question_text**: Text (required, the actual question)
- **question_type**: Enum (choices: 'TEXT', 'YES_NO', 'CHOICE', 'MULTIPLE_CHOICE', 'FILE_UPLOAD', required)
- **required**: Boolean (default: True)
- **order**: Integer (optional, defines the order of questions)
- **choices**: JSONField (optional, for CHOICE and MULTIPLE_CHOICE types, stores available options)
- **created_at**: DateTime (auto-created)
- **updated_at**: DateTime (auto-updated)

### Validation Rules
- question_text must not be empty
- question_type must be one of the allowed choices
- choices field is required when question_type is 'CHOICE' or 'MULTIPLE_CHOICE'
- order must be a positive integer if provided

### Relationships
- One JobListing can have many ScreeningQuestions (One-to-Many)
- ScreeningQuestion belongs to exactly one JobListing

## Entity: ApplicationLink

### Description
Represents the unique, public URL for submitting applications to a specific job listing.

### Fields
- **id**: UUID (Primary Key, auto-generated, same as the job_listing's application_link)
- **job_listing**: ForeignKey to JobListing (required, unique)
- **is_active**: Boolean (computed property based on job listing status and dates)
- **created_at**: DateTime (auto-created)

### Validation Rules
- Each job listing must have exactly one unique application link
- The link should be accessible only when the associated job listing is active

### Relationships
- One-to-One relationship with JobListing
- Derived from JobListing's application_link field

## Entity: TalentAcquisitionSpecialist (extends User)

### Description
The user role authorized to create, manage, and edit job listings. This extends the base User model.

### Fields
- Inherits all fields from Django's AbstractUser
- Additional fields may include department, permissions, etc.

### Validation Rules
- Only users with this role can create, edit, or manage job listings
- Access control enforced through Django's permission system

## Relationships Summary

```
JobListing (1) <---> (0..n) ScreeningQuestion
JobListing (1) <---> (1) ApplicationLink
User (1) <---> (0..n) JobListing (created_by)
```

## Indexes for Performance

- Index on JobListing.status for quick filtering of active/inactive listings
- Index on JobListing.start_date and expiration_date for efficient scheduling queries
- Index on JobListing.created_at for chronological ordering
- Composite index on (status, start_date, expiration_date) for common queries
- Index on ScreeningQuestion.job_listing_id for foreign key lookups
- Index on ScreeningQuestion.order for ordered question presentation