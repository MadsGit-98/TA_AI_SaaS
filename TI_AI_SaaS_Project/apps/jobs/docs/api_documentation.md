# Job Listing Management API Documentation

## Overview
The Job Listing Management API allows Talent Acquisition Specialists to create, manage, and expire job listings with associated screening questions. All endpoints require authentication via JWT token.

## Authentication
All endpoints require a valid JWT token in the Authorization header:
```
Authorization: Bearer <jwt_token>
```

## Base URL
```
https://api.x-crewter.com/v1
```

## Endpoints

### Job Listings

#### List all job listings
- **GET** `/jobs/`
- **Description**: Retrieve a paginated list of job listings with optional filtering
- **Query Parameters**:
  - `status`: Filter by job status (active, inactive)
  - `start_date_after`: Filter jobs with start date after this date
  - `expiration_date_before`: Filter jobs with expiration date before this date
  - `page`: Page number for pagination (default: 1)
  - `limit`: Number of items per page (default: 20)
- **Response**: 200 OK with list of job listings
- **Example Request**:
```
GET /dashboard/jobs/?status=active&page=1&limit=10
Authorization: Bearer <jwt_token>
```

#### Create a new job listing
- **POST** `/jobs/`
- **Description**: Create a new job listing with all required details
- **Request Body**:
```json
{
  "title": "Software Engineer",
  "description": "We are looking for a skilled software engineer...",
  "required_skills": ["Python", "Django", "REST API"],
  "required_experience": 3,
  "job_level": "Senior",
  "start_date": "2023-06-01T09:00:00Z",
  "expiration_date": "2023-07-01T09:00:00Z"
}
```
- **Response**: 201 Created with created job listing
- **Example Request**:
```
POST /dashboard/jobs/
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "title": "Software Engineer",
  "description": "We are looking for a skilled software engineer...",
  "required_skills": ["Python", "Django", "REST API"],
  "required_experience": 3,
  "job_level": "Senior",
  "start_date": "2023-06-01T09:00:00Z",
  "expiration_date": "2023-07-01T09:00:00Z"
}
```

#### Retrieve a specific job listing
- **GET** `/jobs/{id}/`
- **Description**: Get details of a specific job listing by ID
- **Path Parameter**: `id` - Unique identifier of the job listing (UUID)
- **Response**: 200 OK with job listing details
- **Example Request**:
```
GET /dashboard/jobs/123e4567-e89b-12d3-a456-426614174000/
Authorization: Bearer <jwt_token>
```

#### Update a job listing
- **PUT** `/jobs/{id}/`
- **Description**: Update all fields of an existing job listing
- **Path Parameter**: `id` - Unique identifier of the job listing (UUID)
- **Request Body**: Same as create endpoint
- **Response**: 200 OK with updated job listing
- **Example Request**:
```
PUT /dashboard/jobs/123e4567-e89b-12d3-a456-426614174000/
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "title": "Senior Software Engineer",
  "description": "We are looking for a senior software engineer...",
  "required_skills": ["Python", "Django", "REST API", "AWS"],
  "required_experience": 5,
  "job_level": "Senior",
  "start_date": "2023-06-01T09:00:00Z",
  "expiration_date": "2023-07-01T09:00:00Z",
  "status": "Active"
}
```

#### Partially update a job listing
- **PATCH** `/jobs/{id}/`
- **Description**: Update specific fields of an existing job listing
- **Path Parameter**: `id` - Unique identifier of the job listing (UUID)
- **Request Body**: Subset of fields to update
- **Response**: 200 OK with partially updated job listing
- **Example Request**:
```
PATCH /dashboard/jobs/123e4567-e89b-12d3-a456-426614174000/
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "title": "Lead Software Engineer",
  "status": "Active"
}
```

#### Delete a job listing
- **DELETE** `/jobs/{id}/`
- **Description**: Permanently delete a job listing
- **Path Parameter**: `id` - Unique identifier of the job listing (UUID)
- **Response**: 204 No Content
- **Example Request**:
```
DELETE /dashboard/jobs/123e4567-e89b-12d3-a456-426614174000/
Authorization: Bearer <jwt_token>
```

### Job Status Management

#### Activate a job listing
- **POST** `/jobs/{id}/activate/`
- **Description**: Manually activate a job listing regardless of start date
- **Path Parameter**: `id` - Unique identifier of the job listing (UUID)
- **Response**: 200 OK with activated job listing
- **Example Request**:
```
POST /dashboard/jobs/123e4567-e89b-12d3-a456-426614174000/activate/
Authorization: Bearer <jwt_token>
```

#### Deactivate a job listing
- **POST** `/jobs/{id}/deactivate/`
- **Description**: Manually deactivate a job listing regardless of expiration date
- **Path Parameter**: `id` - Unique identifier of the job listing (UUID)
- **Response**: 200 OK with deactivated job listing
- **Example Request**:
```
POST /dashboard/jobs/123e4567-e89b-12d3-a456-426614174000/deactivate/
Authorization: Bearer <jwt_token>
```

#### Duplicate a job listing
- **POST** `/jobs/{id}/duplicate/`
- **Description**: Create a copy of an existing job listing as a template for a new position
- **Path Parameter**: `id` - Unique identifier of the job listing to duplicate (UUID)
- **Response**: 201 Created with duplicated job listing
- **Example Request**:
```
POST /dashboard/jobs/123e4567-e89b-12d3-a456-426614174000/duplicate/
Authorization: Bearer <jwt_token>
```

### Screening Questions

#### List screening questions for a job
- **GET** `/jobs/{id}/screening-questions/`
- **Description**: Retrieve all screening questions associated with a specific job listing
- **Path Parameter**: `id` - Unique identifier of the job listing (UUID)
- **Response**: 200 OK with list of screening questions
- **Example Request**:
```
GET /dashboard/jobs/123e4567-e89b-12d3-a456-426614174000/screening-questions/
Authorization: Bearer <jwt_token>
```

#### Add a screening question to a job
- **POST** `/jobs/{id}/screening-questions/`
- **Description**: Create a new screening question associated with a specific job listing
- **Path Parameter**: `id` - Unique identifier of the job listing (UUID)
- **Request Body**:
```json
{
  "question_text": "What is your experience with Python?",
  "question_type": "TEXT",
  "required": true,
  "order": 1
}
```
- **Response**: 201 Created with created screening question
- **Example Request**:
```
POST /dashboard/jobs/123e4567-e89b-12d3-a456-426614174000/screening-questions/
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "question_text": "What is your experience with Python?",
  "question_type": "TEXT",
  "required": true,
  "order": 1
}
```

#### Retrieve a specific screening question
- **GET** `/jobs/{job_id}/screening-questions/{question_id}/`
- **Description**: Get details of a specific screening question by ID
- **Path Parameters**:
  - `job_id`: Unique identifier of the job listing (UUID)
  - `question_id`: Unique identifier of the screening question (UUID)
- **Response**: 200 OK with screening question details
- **Example Request**:
```
GET /dashboard/jobs/123e4567-e89b-12d3-a456-426614174000/screening-questions/123e4567-e89b-12d3-a456-426614174001/
Authorization: Bearer <jwt_token>
```

#### Update a screening question
- **PUT** `/jobs/{job_id}/screening-questions/{question_id}/`
- **Description**: Update all fields of an existing screening question
- **Path Parameters**:
  - `job_id`: Unique identifier of the job listing (UUID)
  - `question_id`: Unique identifier of the screening question (UUID)
- **Request Body**: Same as create endpoint
- **Response**: 200 OK with updated screening question
- **Example Request**:
```
PUT /dashboard/jobs/123e4567-e89b-12d3-a456-426614174000/screening-questions/123e4567-e89b-12d3-a456-426614174001/
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "question_text": "What is your extensive experience with Python?",
  "question_type": "TEXT",
  "required": true,
  "order": 1
}
```

#### Delete a screening question
- **DELETE** `/jobs/{job_id}/screening-questions/{question_id}/`
- **Description**: Permanently delete a screening question
- **Path Parameters**:
  - `job_id`: Unique identifier of the job listing (UUID)
  - `question_id`: Unique identifier of the screening question (UUID)
- **Response**: 204 No Content
- **Example Request**:
```
DELETE /dashboard/jobs/123e4567-e89b-12d3-a456-426614174000/screening-questions/123e4567-e89b-12d3-a456-426614174001/
Authorization: Bearer <jwt_token>
```

### Common Screening Questions

#### Get common screening questions
- **GET** `/common-screening-questions/`
- **Description**: Retrieve a list of common screening questions that can be suggested to users
- **Response**: 200 OK with list of common screening questions
- **Example Request**:
```
GET /dashboard/common-screening-questions/
Authorization: Bearer <jwt_token>
```

## Error Responses

All error responses follow the same format:
```json
{
  "error": "Error message",
  "details": {
    "field_name": ["Specific error message"]
  }
}
```

## Rate Limits
- Anonymous users: 100 requests per day
- Authenticated users: 1000 requests per day
- Login attempts: 5 per minute
- Password reset attempts: 3 per minute

## Data Formats
- Dates and times: ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)
- IDs: UUID format
- Text fields: UTF-8 encoded