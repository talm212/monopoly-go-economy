"""Safe async-to-sync helper for running coroutines from Streamlit's sync context."""

from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Coroutine
from typing import Any


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run an async coroutine safely from a synchronous context.

    Uses a ThreadPoolExecutor to avoid conflicts with any already-running
    event loop (e.g., in some Streamlit deployment environments).
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()
