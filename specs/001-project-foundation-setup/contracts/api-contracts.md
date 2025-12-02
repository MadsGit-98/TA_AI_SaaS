# API Contracts: X-Crewter Project Setup

## Authentication Endpoints

### POST /api/auth/register/
- **Purpose**: Register a new user
- **Request**:
  - Content-Type: application/json
  - Body: { "username": "string", "email": "string", "password": "string" }
- **Response**:
  - 201 Created: { "id": "int", "username": "string", "email": "string" }
  - 400 Bad Request: { "error": "string" }

### POST /api/auth/login/
- **Purpose**: Authenticate user and return token
- **Request**:
  - Content-Type: application/json
  - Body: { "username": "string", "password": "string" }
- **Response**:
  - 200 OK: { "token": "string" }
  - 401 Unauthorized: { "error": "string" }

## Job Listing Endpoints

### GET /api/jobs/
- **Purpose**: Get all job listings
- **Authentication**: Required (for sensitive endpoints)
- **Response**:
  - 200 OK: [{ "id": "int", "title": "string", "description": "string" }]

### POST /api/jobs/
- **Purpose**: Create a new job listing
- **Authentication**: Required
- **Request**:
  - Content-Type: application/json
  - Body: { "title": "string", "description": "string" }
- **Response**:
  - 201 Created: { "id": "int", "title": "string", "description": "string" }

## Application Endpoints

### POST /api/applications/submit/
- **Purpose**: Submit a new application with resume
- **Request**:
  - Content-Type: multipart/form-data
  - Body: { "resume_file": "file" }
- **Response**:
  - 201 Created: { "id": "int", "status": "string" }
  - 400 Bad Request: { "error": "string" }

## Analysis Endpoints

### GET /api/analysis/{id}/
- **Purpose**: Get analysis results for an application
- **Authentication**: Required
- **Response**:
  - 200 OK: { "id": "int", "application_id": "int", "score": "int", "feedback": "string" }
  - 404 Not Found: { "error": "string" }

## Subscription Endpoints

### GET /api/subscription/
- **Purpose**: Get user's subscription details
- **Authentication**: Required
- **Response**:
  - 200 OK: { "id": "int", "user_id": "int", "plan_name": "string", "start_date": "datetime", "end_date": "datetime" }

## Health Check Endpoint

### GET /api/health/
- **Purpose**: Check the health status of the API
- **Authentication**: Not required
- **Response**:
  - 200 OK: { "status": "healthy", "timestamp": "datetime" }