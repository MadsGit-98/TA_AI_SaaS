"""
AI Analysis Graphs Service

LangGraph-based workflows for AI-powered resume analysis and scoring.

This package contains:
- Supervisor graph: Map-Reduce orchestrator for bulk applicant analysis
- Worker graph: Sequential analysis pipeline for individual applicants
- Interfaces: Protocol definitions for dependency injection
- Types: Shared TypedDicts for type safety
- Orchestrator: Standalone analysis runner
"""

from services.ai_analysis_graphs.supervisor import create_supervisor_graph
from services.ai_analysis_graphs.worker import create_worker_graph
from services.ai_analysis_graphs.orchestrator import run_analysis

__all__ = [
    'create_supervisor_graph',
    'create_worker_graph',
    'run_analysis',
]
