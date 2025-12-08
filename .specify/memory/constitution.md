<!--
Sync Impact Report:
- Version change: 1.0.0 → 1.1.0
- Added sections: 6. Color Grading Non-Negotiables with specific color values and UI principles
- Modified sections: 1. Non-Negotiable Governing Principles (UX Philosophy and Typography & Aesthetics updated to reference color grading)
- Templates requiring updates: ⚠ plan-template.md, spec-template.md, tasks-template.md (need to verify alignment with new color grading principles)
- Follow-up TODOs: RATIFICATION_DATE needs to be set to actual adoption date
-->
# X-Crewter Constitution

## Core Principles

### 1. Non-Negotiable Governing Principles

**Goal**: Create X-Crewter, an AI-powered platform for Talent Acquisition Specialists (TAS) in SMBs to automatically analyze, score (0-100), and categorize bulk resumes (PDF/Docx), significantly reducing screening time.

**UX Philosophy**: Radical Simplicity. Clean, minimalist, distraction-free design utilizing shadcn_django components with strict adherence to the defined color grading philosophy.

**Typography & Aesthetics**:
- Primary: Sans-Serif
- Data/Scores: Monospace
- Color Palette: Dark Mode with high contrast as defined in the Color Grading Non-Negotiables

**Applicant View**:
- Public, unauthenticated form
- Mobile-responsive design
- Strict file validation (.pdf/.docx only)
- Immediate rejection of unsupported file formats

**AI Disclaimer**: Mandatory clear disclosure that AI results are supplementary and not the sole decision criteria.

**Data Integrity**: Applicant state MUST be persisted immediately upon submission.

**Legal Footer**: Required on all pages with anchors for Terms and Conditions, Refund Policies, Cancellation/Replacement Policies, Accepted payment methods and Accepted currencies.

### 2. Architecture and Structure Mandate

**Core Setup**:
- Framework: Django, Django REST Framework (DRF)
- Database: Sqlite3 (Initial)
- Root Structure: Must include a top-level celery.py file

**Django Applications**:
- **accounts**: TAS User Authentication, Registration, Login/Logout, Profile Management
- **jobs**: Job Listing CRUD (Create, Read, Update, Deactivate), screening questions, and requirements definition
- **applications**: Public form handler, Resume Upload/Storage, Applicant persistence, and initiates parsing/analysis via Celery
- **analysis**: TAS Dashboard View, AI results display, bulk analysis initiation/filtering
- **subscription**: Subscription scaffolding, Amazon Payment Services (APS) integration

### 3. App Subdirectory Structure

Each Django application MUST contain the following structure:
- **templates/**: For all application-specific .html files
- **static/**
  - **js/**: Non-negotiable location for all JavaScript scripts
  - **css/**: Non-negotiable location for all CSS styling files
  - **images/**: Non-negotiable location for all static image assets
- **tasks.py**: Required only for Celery integration (applications and analysis apps)
- **tests/**: Must house all tests, divided into: tests/Integration/, tests/Unit/, tests/E2E/

### 4. Decoupled Services (Located in Project Root services/ directory)

The following services MUST be implemented as distinct, decoupled Python modules:
- **ai_analysis_service**: LLM/Langchain/Langgraph integration for scoring, justification, and categorization. Handles the "Unprocessed" flag on analysis failure
- **resume_parsing_service**: PYPDF/python-docx validation and text extraction
- **reporting_utils**: Utilities for result sorting, filtering, and retrieval
- **logging_service**: Centralized debugging utility (staged for removal in production)
- **ai_email_assistance_service**: TAS support for drafting follow-up emails

### 5. Quality, Testing, and Security Standards

**Coding & Quality**:
- Coding Style: PEP 8 compliant Python
- Naming Conventions: Models = Singular PascalCase (e.g., JobListing), Functions/Variables = snake_case
- Strictly use the django template language (DTL) in developing html pages.

**Testing Mandate**:
- Unit Tests: Python native unittest module with minimum 90% line coverage
- Integration/E2E Tests: Selenium

**Security Compliance**:
- Access Control: Implement Role-Based Access Control (RBAC) scaffolding
- SSL Configuration (Mandatory): Secure cookies, HSTS, HTTPS Redirection Enforcement, Content Security Policy (CSP), and addressing Mixed Content/Referrer Policy

### 6. Color Grading Non-Negotiables

**Colors**:
- **primary-bg**: #FFFFFF (Pure White - Provides the bright, clean canvas for the Light Mode interface.)
- **primary-text**: #000000 (Pure Black - Optimal contrast for high readability across all main text elements.)
- **secondary-text**: #A0A0A0 (Medium Grey - Subtle metadata/supporting text)
- **accent-cta**: #080707 (Black - Primary call-to-action/link color)
- **code-block-bg**: #E0E0E0 (Subtle Dark Grey - Code and card background)
- **cta-text**: (Pure White - Ensures the text is highly legible against the dark Charcoal Black background. )

**UI Principles**:
- **Theme**: Dark Mode, High Contrast.
- **Contrast Rule**: All primary text elements must achieve WCAG AAA contrast ratio against the primary-bg color.
- **Emphasis Rule**: The accent-cta color must be reserved exclusively for primary interactive elements (buttons, links, active states) to drive conversion and focus.
- **Hierarchy Rule**: The secondary-text color must be used to de-emphasize less critical information, creating a clear visual hierarchy.

## Implementation Standards

**Technology Stack**: Django with Django REST Framework for backend API, Sqlite3 for initial database.

**Application Structure**: The system is divided into five core Django applications (accounts, jobs, applications, analysis, subscription) following the separation of concerns principle.

**File Handling**: Strict validation for .pdf/.docx files only, with immediate rejection of unsupported formats.

**Security**: Mandatory SSL configuration, RBAC implementation, and secure data handling practices.

## Development Workflow

**Code Quality**: All code must comply with PEP 8 standards, with 90% unit test coverage minimum using Python's unittest module.

**Testing Strategy**: Integration and E2E tests to be implemented with Selenium, with emphasis on TDD practices.

**Review Process**: All pull requests must be reviewed for compliance with architectural constraints and security requirements.

## Governance

The X-Crewter Constitution supersedes all other development practices and guidelines. All amendments to this constitution require formal documentation, approval by project maintainers, and a migration plan if applicable. All pull requests and code reviews must verify compliance with these principles. All contributors must ensure that complexity is justified by clear business or technical requirements.

**Version**: 1.1.0 | **Ratified**: TODO(RATIFICATION_DATE): Date of original adoption | **Last Amended**: 2025-12-07