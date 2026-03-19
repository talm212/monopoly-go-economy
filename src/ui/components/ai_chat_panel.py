"""AI chat panel: Streamlit component for natural language queries about simulation data."""

from __future__ import annotations

import logging
from typing import Any

import streamlit as st

from src.application.chat_assistant import ChatAssistant, Message
from src.ui.async_helper import run_async

logger = logging.getLogger(__name__)

_SESSION_KEY_HISTORY = "ai_chat_history"


def render_ai_chat_panel(
    assistant: ChatAssistant,
    result_summary: dict[str, Any],
    distribution: dict[str, int],
    config: dict[str, Any],
    kpi_metrics: dict[str, float],
) -> None:
    """Render a chat interface for asking questions about simulation data.

    Args:
        assistant: ChatAssistant instance wired with an LLM client.
        result_summary: High-level summary dict from SimulationResult.to_summary_dict().
        distribution: Success distribution from SimulationResult.get_distribution().
        config: Configuration dict from SimulatorConfig.to_dict().
        kpi_metrics: KPI dict from SimulationResult.get_kpi_metrics().
    """
    st.subheader("Ask about your simulation")

    # Initialize chat history in session state
    if _SESSION_KEY_HISTORY not in st.session_state:
        st.session_state[_SESSION_KEY_HISTORY] = []

    history: list[dict[str, str]] = st.session_state[_SESSION_KEY_HISTORY]

    # Display message history
    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input box for new questions
    question = st.chat_input("Ask a question about the simulation results...")

    if question:
        # Show user message immediately
        with st.chat_message("user"):
            st.markdown(question)

        # Build Message objects from history for the assistant
        message_history = [
            Message(role=msg["role"], content=msg["content"]) for msg in history
        ]

        # Call the assistant
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = run_async(
                    assistant.answer(
                        question=question,
                        result_summary=result_summary,
                        distribution=distribution,
                        config=config,
                        kpi_metrics=kpi_metrics,
                        history=message_history,
                    )
                )
            st.markdown(response)

        # Append both messages to history
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": response})
        st.session_state[_SESSION_KEY_HISTORY] = history
