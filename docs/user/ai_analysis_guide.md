# User Guide: AI Analysis & Scoring

**Audience**: Talent Acquisition Specialists  
**Last updated**: 2026-04-19  

---

## Overview

AI Analysis scores applicants against a job’s requirements using a dedicated **AI analysis service** (LangGraph + LLM, typically Ollama in development). Django stores results and serves the dashboard; **progress** is shown via **in-app notifications and WebSockets** (`/ws/analysis-notifications/`), not a separate “status” REST button.

You get:

- **Scores** (0–100) for Education, Skills, Experience, plus Supplemental context where applicable  
- **Match categories**: Best Match, Good Match, Partial Match, Mismatched  
- **Text justifications** for each metric  
- **Bulk run**: one action processes all current applicants for the job  

---

## When you can start analysis

You can start analysis when the job has **at least one applicant** and you are allowed to run the action from the dashboard. The backend **does not** require the job to be expired or deactivated before starting analysis—expiration controls **new applications**, not whether you can score existing applicants. (Marketing copy on older screens may still mention “active job” warnings; trust the live app rules.)

If a run is **already in progress** for that job, the API returns a conflict until it finishes or you cancel.

---

## Step-by-step

### 1. Open the job

From **Dashboard**, open the job you want to score. You must be the owner of the listing (or staff).

### 2. Start analysis

Use **Start AI Analysis** (or equivalent) from the dashboard or job detail UI. The server returns **202 Accepted** and enqueues work on the AI service; the UI should direct you to monitor progress via notifications / the analysis views.

### 3. Monitor progress

- **WebSocket**: `/ws/analysis-notifications/` delivers updates to your logged-in session.  
- You may **cancel** a run from the UI where supported; completed rows are kept according to the cancel logic in the API.  
- You can **navigate away**; processing continues server-side.

### 4. View results

Use the analysis **list** and **detail** pages under `/analysis/` (see `apps/analysis/ui_urls.py`). The results table shows scores, categories, and links to **View details** for full justifications.

**AI disclaimer** (always apply): scores are **assistive** only. Use human judgment for hiring decisions.

### 5. Reporting

The **reporting** view (`/analysis/reporting/<job_id>/`) summarizes distributions and metric averages when results exist.

### 6. Re-run

If applicants change or you need a fresh scoring pass, use **Re-run analysis** where the UI offers it. You must **confirm**—the API requires `"confirm": true` and will delete previous `AIAnalysisResult` rows **after** the AI service accepts the new run.

---

## Understanding scores

### Formula (worker implementation)

The analysis service computes:

**Overall score** = floor(Experience × 0.50 + Skills × 0.30 + Education × 0.20)

Supplemental information is surfaced in the UI but does not feed this weighted sum.

### Category bands (typical)

| Category | Score range | Meaning |
|----------|-------------|---------|
| Best Match | 90–100 | Strong alignment |
| Good Match | 70–89 | Solid fit |
| Partial Match | 50–69 | Mixed fit |
| Mismatched | 0–49 | Weak fit |

---

## Unprocessed rows

Applicants may show **Unprocessed** when parsing failed, the file was unusable, or the worker errored. Retry after fixing the resume, or re-run analysis after uploads change.

---

## Troubleshooting

| Issue | What to check |
|--------|----------------|
| “Analysis already running” | Wait, cancel, or retry after cancel completes |
| “No applicants” | No applicants on the job yet |
| Service unavailable | AI service down or misconfigured (`AI_SERVICE_BASE_URL`, `AI_SERVICE_API_KEY`); Ollama/model on the worker host |
| Slow throughput | Roughly **~6 seconds per applicant** in estimates; GPU/CPU load and model size matter |
| WebSocket not updating | Login session, same origin, Redis/Channels running |

---

## Privacy & compliance

Treat AI output as **non-deterministic assistance**. Keep audit trails (stored results and timestamps) as required by your process.

---

## Further reading

- [Analysis API reference](../api/analysis_api.md)  
- [Standalone AI service README](../../TI_AI_SaaS_Project/services/README.md)  
