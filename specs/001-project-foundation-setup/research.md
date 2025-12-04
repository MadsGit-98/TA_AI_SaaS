# Research Report: Project Setup and Foundational Architecture

## Ollama Client Integration

### Decision: 
Use langchain and langgraph libraries to integrate with Ollama as the LLM gateway.

### Rationale: 
The feature specification explicitly mentions the need for Ollama client integration for LLM functionality. Langchain provides robust integration patterns with Ollama, and langgraph enables stateful AI workflows which are essential for the resume analysis functionality of the X-Crewter platform.

### Alternatives Considered:
- Direct HTTP API calls to Ollama: Less maintainable and lacks advanced features
- Alternative LLM libraries: Less compatible with Ollama than Langchain
- Pre-built AI service: Contradicts the requirement to use Ollama as the LLM gateway

## Production CORS Configuration for Django

### Decision:
Use django-cors-headers package with security-focused configuration settings.

### Rationale:
The feature specification requires implementing CORS headers configured for production security. Django-cors-headers is the standard package for handling CORS in Django applications and provides fine-grained control over security policies. Configuration will include restricting allowed origins, methods, and headers to the minimum required for functionality.

### Alternatives Considered:
- Manual CORS headers: Error-prone and inconsistent implementation
- Server-level CORS management: Reduces flexibility and maintainability
- Minimal CORS configuration: Would not meet production security requirements

## shadcn_django Non-React Implementation

### Decision:
Implement shadcn_django as CSS/JS components that integrate directly with Django templates, avoiding React entirely.

### Rationale:
The feature specification explicitly states "Frontend: Django Templates, Tailwind CSS, and standard JavaScript (no React)" and "UI/UX: shadcn_django (via a non-React implementation method)". This means we need to use the CSS/JS-based components of shadcn that can be integrated with Django templates rather than the React components.

### Alternatives Considered:
- Full React implementation: Contradicts explicit "no React" requirement
- Custom UI components: Would require more time and not leverage shadcn_django benefits
- Alternative component libraries: Would not meet the specified shadcn_django requirement