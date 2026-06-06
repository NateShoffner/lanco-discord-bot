import logging
from typing import Awaitable, Callable

from pydantic_ai.agent import AgentRunResult
from pydantic_ai.exceptions import ModelHTTPError

logger = logging.getLogger(__name__)


def _http_error_msg(e: ModelHTTPError) -> str:
    if e.status_code == 429:
        return "I'm being rate limited right now.\nTry again later!"
    return f"Something went wrong on my end (HTTP {e.status_code}).\nTry again later!"


async def _noop(_: str) -> None:
    pass


async def run_agent(
    agent_call: Callable[[], Awaitable[AgentRunResult]],
    on_error: Callable[[str], Awaitable[None]] = _noop,
) -> AgentRunResult | None:
    """Run a pydantic-ai agent call, invoking on_error with a user-facing message on failure.

    Returns the result on success, or None if an error occurred.
    """
    try:
        return await agent_call()
    except ModelHTTPError as e:
        logger.error("ModelHTTPError during agent run: %s", e)
        await on_error(_http_error_msg(e))
        return None
    except Exception as e:
        logger.error("Unexpected error during agent run: %s", e)
        await on_error("Something went wrong on my end.\nTry again later!")
        return None
