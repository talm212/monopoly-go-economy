# Design Log 022 — AI Chat Assistant

**Date:** 2026-03-19
**Feature:** #22 — Chat assistant for natural language queries about simulation data
**Status:** In Progress

---

## Context

The economy team needs an interactive way to ask questions about simulation results
in plain language. Rather than reading raw tables and charts, they want to type
"What percentage of players exceeded the threshold?" and get a data-backed answer.

## Decision

Create a `ChatAssistant` application service that:
1. Accepts a user question plus simulation context (config, result summary, distribution, KPI metrics).
2. Builds a prompt including the full data context and conversation history.
3. Delegates to the `LLMClient` protocol (provider-agnostic).
4. Returns the LLM's text response, or a user-friendly error message on failure.

Key design choices:
- **Conversation history** via `Message` dataclass, limited to `max_history` turns to prevent context overflow.
- **System prompt** establishes a data analyst persona that always cites numbers.
- **Error handling**: never crashes — returns a helpful fallback string.
- **Dependency injection** of `LLMClient` for testability (all tests use mocks).

## Architecture

- `src/application/chat_assistant.py` — application service (orchestration layer)
- `src/ui/components/ai_chat_panel.py` — Streamlit UI component
- Follows the same pattern as `InsightsAnalyst` in `analyze_results.py`

## Testing

TDD approach: write all tests first, confirm they fail, then implement.
All tests mock `LLMClient` — no real API calls.
