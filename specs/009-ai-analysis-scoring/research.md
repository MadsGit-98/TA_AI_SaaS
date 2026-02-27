# Research & Technical Decisions: AI Analysis & Scoring

**Feature**: 009-ai-analysis-scoring  
**Date**: 2026-02-28  
**Phase**: 0 (Research & Discovery)

---

## 1. LangGraph Map-Reduce Pattern

### Decision
Use LangGraph supervisor graph pattern with explicit state management for orchestrating the Map-Reduce workflow. The supervisor graph will control the flow between decision nodes, map steps (ThreadPoolExecutor), and reduce steps (bulk persistence).

### Rationale
- LangGraph provides built-in state graph management ideal for multi-step workflows
- Supervisor pattern allows centralized control over concurrent worker execution
- Native support for conditional edges (decision nodes) and parallel execution (map step)
- Integrates seamlessly with Celery for async task execution
- Aligns with existing LangChain 1.1.x and LangGraph 1.0.x dependencies in requirements.txt

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| Celery chord + group | More complex error handling, less visibility into individual worker state |
| Manual threading with queues | Reinvents workflow orchestration, harder to maintain |
| LangChain SequentialChain | Doesn't support parallel map operations natively |

### Implementation Pattern
```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class AnalysisState(TypedDict):
    job_id: str
    unanalyzed_applicants: List[dict]
    results: List[dict]
    processed_count: int
    total_count: int

# Supervisor Graph
workflow = StateGraph(AnalysisState)
workflow.add_node("decision", decision_node)
workflow.add_node("map_workers", map_workers_node)
workflow.add_node("bulk_persist", bulk_persistence_node)
workflow.add_conditional_edges("decision", should_continue, {
    "continue": "map_workers",
    "end": "bulk_persist"
})
```

---

## 2. Ollama Integration

### Decision
Use LangChain's Ollama integration (`langchain_community.llms.Ollama` or `langchain_ollama.OllamaLLM`) with base URL configured via environment variable `OLLAMA_BASE_URL`. Default: `http://localhost:11434`.

### Rationale
- LangChain provides abstraction layer for prompt templating and structured output
- Environment-based configuration allows flexibility (local dev vs. dedicated LLM server)
- Built-in retry logic and connection pooling in LangChain
- Consistent with existing LangChain dependency in project

### Configuration
```python
# settings.py or .env
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama2:7b')

# In service
from langchain_ollama import OllamaLLM
llm = OllamaLLM(
    base_url=settings.OLLAMA_BASE_URL,
    model=settings.OLLAMA_MODEL,
    temperature=0.1,  # Low temperature for consistent scoring
    format="json"     # Force JSON output for structured parsing
)
```

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| Direct HTTP calls to Ollama API | More boilerplate, no retry logic, manual JSON parsing |
| Ollama Python client | Less integration with LangChain prompt templates |
| Hardcoded localhost | Inflexible for production deployment |

### Error Handling
```python
from langchain_community.callbacks.manager import CallbackManager
from langchain_core.exceptions import OutputParserException

try:
    response = llm.invoke(prompt)
except Exception as e:
    # Flag applicant as Unprocessed
    return {"status": "Unprocessed", "error": str(e)}
```

---

## 3. ThreadPoolExecutor Sizing

### Decision
Use `ThreadPoolExecutor` with `max_workers=min(32, (CPU_COUNT or 1) * 2)` for concurrent applicant processing. This provides balanced concurrency without overwhelming system resources.

### Rationale
- Thread pool is I/O-bound (LLM API calls, DB queries), not CPU-bound
- 10 resumes/minute target = ~6 seconds per applicant average
- LLM call latency typically 2-4 seconds per call (2 calls per applicant)
- 32 max workers provides upper bound to prevent resource exhaustion
- Formula scales with available CPU cores for different deployment sizes

### Implementation
```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

def get_max_workers():
    cpu_count = os.cpu_count() or 1
    return min(32, cpu_count * 2)

def process_applicants_concurrently(applicants, worker_graph):
    results = []
    max_workers = get_max_workers()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_applicant = {
            executor.submit(worker_graph.invoke, {"applicant": app}): app
            for app in applicants
        }
        
        for future in as_completed(future_to_applicant):
            result = future.result()
            results.append(result)
    
    return results
```

### Performance Calculation
- Target: 10 resumes/minute = 600 seconds / 10 = 60 seconds per batch of 10
- With 10 concurrent workers: 6 seconds per applicant average
- Each applicant: 2 LLM calls (scoring + justification) @ 2-3 seconds each = 4-6 seconds
- **Conclusion**: 10 concurrent workers meets target; 32 max provides headroom

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| ProcessPoolExecutor | Overkill for I/O-bound workload, higher memory overhead |
| Asyncio with async LLM calls | Ollama LangChain integration may not support async natively |
| Fixed worker count (e.g., 10) | Doesn't scale with hardware capabilities |

---

## 4. Bulk Database Operations

### Decision
Use Django's `bulk_create()` with `batch_size=50` and `update_conflicts=True` for efficient result persistence. For updates, use `bulk_update()` with explicit field specification.

### Rationale
- Single bulk operation reduces database round-trips
- Batch size of 50 balances memory usage vs. performance
- `update_conflicts=True` handles re-run scenarios (overwrites previous results)
- Consistent with Sqlite3 initial database (also works with PostgreSQL upgrade)

### Implementation
```python
from apps.analysis.models import AIAnalysisResult

def bulk_save_results(results, job_listing):
    """
    Bulk insert or update AI analysis results.
    
    Args:
        results: List[AIAnalysisResult] instances
        job_listing: JobListing instance
    """
    # Prepare for bulk_create with update on conflict
    AIAnalysisResult.objects.bulk_create(
        results,
        batch_size=50,
        update_conflicts=True,
        update_fields=[
            'overall_score', 'category', 'status',
            'education_score', 'skills_score', 'experience_score', 'supplemental_score',
            'education_justification', 'skills_justification', 
            'experience_justification', 'supplemental_justification', 'overall_justification',
            'updated_at'
        ],
        unique_fields=['applicant_id']  # OneToOne with Applicant
    )
```

### Re-run Scenario Handling
```python
def prepare_for_rerun(job_listing):
    """Delete previous results before re-run to ensure clean state."""
    AIAnalysisResult.objects.filter(job_listing=job_listing).delete()
```

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| Individual save() in loop | N database queries, slow for large batches |
| Transaction with individual saves | Better than nothing, still N queries |
| Raw SQL bulk insert | Loses Django ORM validation and signals |

---

## 5. Redis Lock Pattern

### Decision
Implement Redis-based distributed lock using `SET NX EX` pattern with 5-minute TTL and automatic expiration. Lock key format: `analysis_lock:{job_id}`.

### Rationale
- Prevents duplicate analysis initiation for same job listing
- Redis already configured in project (Celery broker)
- Automatic expiration prevents deadlocks if worker crashes
- Simple, battle-tested pattern

### Implementation
```python
import redis
from django.conf import settings
from uuid import UUID

class AnalysisLockError(Exception):
    pass

def acquire_analysis_lock(job_id: UUID, ttl_seconds: int = 300) -> bool:
    """
    Acquire distributed lock for analysis initiation.
    
    Returns:
        True if lock acquired, False if already running
    """
    r = redis.from_url(settings.REDIS_URL)
    lock_key = f"analysis_lock:{job_id}"
    
    # SET NX EX: Set if Not eXists, with EXpiration
    acquired = r.set(lock_key, "locked", nx=True, ex=ttl_seconds)
    return bool(acquired)

def release_analysis_lock(job_id: UUID):
    """Release lock after analysis completion."""
    r = redis.from_url(settings.REDIS_URL)
    lock_key = f"analysis_lock:{job_id}"
    r.delete(lock_key)

# In API endpoint
from django.core.exceptions import PermissionDenied

def initiate_analysis(request, job_id):
    if not acquire_analysis_lock(job_id):
        return Response({
            "status": "already_running",
            "message": "Analysis already in progress for this job listing"
        }, status=409)
    
    try:
        task = run_ai_analysis.delay(job_id)
        return Response({"task_id": task.id, "status": "started"})
    except Exception as e:
        release_analysis_lock(job_id)
        raise
```

### TTL Justification
- 5 minutes = 300 seconds
- At 10 resumes/minute, handles up to 50 applicants
- If job has more applicants, lock can be renewed or extended
- Automatic cleanup prevents orphaned locks

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| Database row lock (SELECT FOR UPDATE) | Holds DB connection, doesn't work across workers |
| Django cache lock (cache.add) | Less explicit control over TTL |
| File-based lock | Doesn't work across multiple workers/servers |

---

## 6. Weighted Score Calculation

### Decision
Implement weighted average formula: `overall_score = floor((experience * 0.50) + (skills * 0.30) + (education * 0.20))`. Use Python's `math.floor()` for deterministic rounding.

### Rationale
- Clarification session confirmed fixed weights: Experience 50%, Skills 30%, Education 20%
- Floor rounding ensures consistent category boundaries (no ambiguity at edges)
- Simple, auditable formula (no hidden complexity)
- Deterministic (no randomness, reproducible results)

### Implementation
```python
import math

def calculate_overall_score(experience: int, skills: int, education: int, supplemental: int = 0) -> int:
    """
    Calculate weighted overall score with floor rounding.
    
    Weights:
    - Experience: 50%
    - Skills: 30%
    - Education: 20%
    - Supplemental: Not included in overall (tracked separately)
    
    Returns:
        Floored integer score (0-100)
    """
    weighted_sum = (experience * 0.50) + (skills * 0.30) + (education * 0.20)
    return math.floor(weighted_sum)

def assign_category(overall_score: int) -> str:
    """
    Assign match category based on floored overall score.
    
    Categories:
    - Best Match: 90-100
    - Good Match: 70-89
    - Partial Match: 50-69
    - Mismatched: 0-49
    """
    if overall_score >= 90:
        return "Best Match"
    elif overall_score >= 70:
        return "Good Match"
    elif overall_score >= 50:
        return "Partial Match"
    else:
        return "Mismatched"
```

### Category Boundary Examples
| Scores (Exp, Skills, Edu) | Weighted Avg | Floored | Category |
|---------------------------|--------------|---------|----------|
| 100, 100, 100 | 100.0 | 100 | Best Match |
| 90, 90, 90 | 90.0 | 90 | Best Match |
| 89, 89, 89 | 89.0 | 89 | Good Match |
| 89.9 (e.g., 95, 85, 90) | 89.9 | 89 | Good Match |
| 70, 70, 70 | 70.0 | 70 | Good Match |
| 69, 69, 69 | 69.0 | 69 | Partial Match |
| 50, 50, 50 | 50.0 | 50 | Partial Match |
| 49, 49, 49 | 49.0 | 49 | Mismatched |

---

## 7. Cancellation and Re-run Handling

### Decision
Support both cancellation of running analysis and re-run after completion:
- **Cancellation**: Set cancellation flag in Redis; workers check flag and exit gracefully; preserve completed results
- **Re-run**: Delete previous results, acquire lock, start fresh analysis

### Rationale
- Real-world scenarios: new applicants apply, requirements change, user wants fresh analysis
- Graceful cancellation preserves partial work (doesn't waste completed LLM calls)
- Re-run overwrites previous results (single source of truth)

### Cancellation Implementation
```python
def cancel_analysis(job_id: UUID) -> dict:
    """
    Cancel running analysis for a job listing.
    
    Returns:
        {"status": "cancelled", "preserved_count": int}
    """
    r = redis.from_url(settings.REDIS_URL)
    cancel_key = f"analysis_cancel:{job_id}"
    r.setex(cancel_key, 60, "cancelled")  # TTL 60 seconds
    
    # Count preserved results
    preserved = AIAnalysisResult.objects.filter(
        job_listing=job_listing,
        status="Analyzed"
    ).count()
    
    return {"status": "cancelled", "preserved_count": preserved}

# In worker sub-graph
def check_cancellation_flag(job_id: UUID) -> bool:
    """Check if cancellation was requested."""
    r = redis.from_url(settings.REDIS_URL)
    cancel_key = f"analysis_cancel:{job_id}"
    return r.exists(cancel_key)

# Worker node checks before processing each applicant
if check_cancellation_flag(job_id):
    return {"status": "cancelled", "applicant": applicant.id}
```

### Re-run Implementation
```python
def re_run_analysis(job_id: UUID) -> dict:
    """
    Re-run analysis for a job listing (overwrites previous results).
    """
    # Delete previous results
    AIAnalysisResult.objects.filter(job_listing=job_id).delete()
    
    # Acquire lock and start task
    if not acquire_analysis_lock(job_id):
        raise AnalysisLockError("Another analysis is already running")
    
    task = run_ai_analysis.delay(job_id)
    return {"task_id": task.id, "status": "started"}
```

---

## 8. AI Disclaimer Presentation

### Decision
Display AI disclaimer as a **passive notice** (no acknowledgment required) prominently on all pages showing AI analysis results.

### Rationale
- Reduces friction for users (no extra click to acknowledge)
- Still provides legal/ethical transparency about AI limitations
- Consistent with industry best practices for AI-assisted tools
- Meets spec requirement (FR-015) without adding barriers

### UI Placement
```html
<!-- In analysis results template -->
<div class="ai-disclaimer">
    <strong>AI Disclaimer:</strong> 
    These results are generated by artificial intelligence and should be 
    used as supplementary information only. Do not rely solely on AI 
    scores for hiring decisions. Always conduct human review.
</div>
```

### Styling (per Constitution Color Grading)
```css
.ai-disclaimer {
    background-color: var(--code-block-bg);  /* #E0E0E0 */
    border-left: 4px solid var(--secondary-text);  /* #A0A0A0 */
    padding: 1rem;
    margin: 1rem 0;
    font-size: 0.875rem;
    color: var(--secondary-text);
}
```

---

## 9. Notification Delivery

### Decision
Implement **in-app notification only** (no email). Display notification via Django messages framework or real-time update when user is on the page.

### Rationale
- Simpler implementation (no email service integration)
- Users typically wait for analysis results (short-running operation)
- Reduces email fatigue
- Consistent with spec clarification (Question 4: Option A)

### Implementation
```python
from django.contrib import messages

# In Celery task completion callback
def notify_analysis_complete(request, job_id):
    messages.success(
        request,
        f"AI analysis completed for job listing '{job_title}'. "
        f"Processed {count} applicants."
    )
```

### Real-time Option (Future Enhancement)
```python
# Using Django Channels for WebSocket notification
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

channel_layer = get_channel_layer()
async_to_sync(channel_layer.group_send)(
    f"user_{user_id}",
    {"type": "analysis_complete", "job_id": str(job_id)}
)
```

---

## 10. Error Handling and Unprocessed Flag

### Decision
Implement comprehensive error handling at each worker node. Any exception results in "Unprocessed" status with error message logged (without PII).

### Rationale
- Spec requirement (FR-009): Flag failed applicants without stopping bulk operation
- LLM calls can fail (timeout, model error, malformed output)
- Parsing can fail (corrupted files, unsupported formats)
- Graceful degradation maintains overall workflow reliability

### Error Handling Pattern
```python
def worker_subgraph(applicant: Applicant, job_listing: JobListing) -> dict:
    """
    Process single applicant through all analysis nodes.
    
    Returns:
        AIAnalysisResult dict or error dict with Unprocessed status
    """
    try:
        # Node 1: Data Retrieval
        resume_text = applicant.resume_parsed_text
        if not resume_text:
            raise ValueError("No parsed resume text available")
        
        # Node 2: Classification
        classified_data = classify_resume(resume_text, job_listing)
        
        # Node 3: Scoring (LLM call)
        scores = llm_score_candidate(classified_data, job_listing)
        
        # Node 4: Categorization (deterministic)
        overall_score = calculate_overall_score(
            scores['experience'],
            scores['skills'],
            scores['education']
        )
        category = assign_category(overall_score)
        
        # Node 5: Justification (LLM call)
        justifications = llm_generate_justifications(
            scores, category, classified_data
        )
        
        # Build result
        return {
            "applicant": applicant,
            "job_listing": job_listing,
            "education_score": scores['education'],
            "skills_score": scores['skills'],
            "experience_score": scores['experience'],
            "supplemental_score": scores.get('supplemental', 0),
            "overall_score": overall_score,
            "category": category,
            "justifications": justifications,
            "status": "Analyzed"
        }
        
    except Exception as e:
        # Log error (without PII)
        logger.warning(f"AI analysis failed for applicant {applicant.id}: {str(e)}")
        
        return {
            "applicant": applicant,
            "job_listing": job_listing,
            "status": "Unprocessed",
            "error_message": str(e)[:500]  # Truncate long errors
        }
```

---

## Summary of Technical Decisions

| # | Decision | Chosen Approach |
|---|----------|-----------------|
| 1 | Workflow Orchestration | LangGraph supervisor graph with state management |
| 2 | LLM Integration | LangChain Ollama with env-based URL config |
| 3 | Concurrency | ThreadPoolExecutor with `min(32, CPU_COUNT * 2)` workers |
| 4 | Database Persistence | Django bulk_create with batch_size=50, update_conflicts=True |
| 5 | Distributed Locking | Redis SET NX EX with 5-minute TTL |
| 6 | Score Calculation | Weighted avg (50/30/20) with floor rounding |
| 7 | Cancellation/Re-run | Redis cancellation flag + delete-and-restart pattern |
| 8 | AI Disclaimer | Passive notice (no acknowledgment) |
| 9 | Notifications | In-app only (Django messages) |
| 10 | Error Handling | Per-applicant try/catch with Unprocessed flag |

---

## Next Steps

1. **Phase 1**: Create `data-model.md` with AIAnalysisResult model specification
2. **Phase 1**: Generate API contracts in `contracts/` directory (OpenAPI YAML)
3. **Phase 1**: Write `quickstart.md` setup guide
4. **Phase 1**: Update agent context with new technologies
5. **Phase 2**: Generate task breakdown via `/speckit.tasks`
