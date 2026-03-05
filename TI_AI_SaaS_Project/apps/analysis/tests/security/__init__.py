"""
Security Tests for Analysis Application

This package contains comprehensive security tests for the AI Analysis application,
covering authentication, authorization, input validation, API security, data integrity,
Redis security, LLM security, and logging security.

Test Categories:
- test_authentication.py: JWT token validation, session security
- test_authorization.py: RBAC, horizontal/vertical privilege escalation
- test_input_validation.py: SQL injection, XSS, parameter validation
- test_api_security.py: HTTP method security, content-type validation
- test_data_integrity.py: Data isolation, sensitive data exposure, race conditions
- test_redis_security.py: Lock security, cache security
- test_llm_security.py: Prompt injection, LLM output validation
- test_logging_security.py: Security event logging, log security
"""
