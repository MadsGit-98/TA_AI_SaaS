# Data Model: Compliant Home Page & Core Navigation

## Entities

### HomePageContent
**Purpose:** Stores configurable content for the home page that can be managed through the admin interface

**Fields:**
- `id` (AutoField): Primary key
- `title` (CharField, max_length=200): The main title/headline for the home page
- `subtitle` (TextField): Subtitle or tagline for the home page
- `description` (TextField): Main description of the X-Crewter service
- `call_to_action_text` (CharField, max_length=100): Text for the main call-to-action button
- `pricing_info` (TextField): Information about pricing plans
- `created_at` (DateTimeField): Timestamp when content was created
- `updated_at` (DateTimeField): Timestamp when content was last updated

**Relationships:**
- None (standalone entity for home page content)

### LegalPage
**Purpose:** Stores content for legal pages that need to be accessible from the home page footer

**Fields:**
- `id` (AutoField): Primary key
- `title` (CharField, max_length=200): Title of the legal page
- `slug` (SlugField, unique=True): URL-friendly identifier for the page
- `content` (TextField): Full content of the legal page
- `page_type` (CharField, choices=['privacy', 'terms', 'refund', 'contact']): Type of legal page
- `is_active` (BooleanField): Whether the page is currently published
- `created_at` (DateTimeField): Timestamp when content was created
- `updated_at` (DateTimeField): Timestamp when content was last updated

**Relationships:**
- None (standalone entity for legal pages)

### CardLogo
**Purpose:** Stores information about accepted payment card logos displayed in the footer

**Fields:**
- `id` (AutoField): Primary key
- `name` (CharField, max_length=50): Name of the card type (e.g., Visa, Mastercard)
- `logo_image` (ImageField): Image file for the card logo
- `display_order` (IntegerField): Order in which to display the logos
- `is_active` (BooleanField): Whether to display this logo
- `created_at` (DateTimeField): Timestamp when record was created

**Relationships:**
- None (standalone entity for card logos)

### SiteSetting
**Purpose:** Stores global site settings that affect the home page display

**Fields:**
- `id` (AutoField): Primary key
- `setting_key` (CharField, unique=True, max_length=100): Key for the setting (e.g., 'currency_display', 'contact_email')
- `setting_value` (TextField): Value of the setting
- `description` (TextField): Description of what this setting controls
- `updated_at` (DateTimeField): Timestamp when setting was last updated

**Relationships:**
- None (standalone entity for site settings)

## State Transitions

### LegalPage State Transitions
- `Draft` → `Published`: When content is ready and `is_active` is True
- `Published` → `Archived`: When content is no longer needed but preserved for records

## Validation Rules

### HomePageContent Validation
- `title` must not be empty
- `description` length must be between 50 and 1000 characters
- `call_to_action_text` must not be empty

### LegalPage Validation
- `title` must not be empty
- `slug` must be unique and URL-friendly
- `content` must not be empty
- `page_type` must be one of the allowed choices

### CardLogo Validation
- `name` must not be empty
- `logo_image` must be a valid image file
- `display_order` must be non-negative

### SiteSetting Validation
- `setting_key` must be unique
- `setting_key` must be in allowed list of valid keys