"""Production telemetry: send classification request/response as traces to Confident AI.

When CONFIDENT_API_KEY is set (e.g. in production), every classification response
is recorded as a trace so you get full request/response telemetry and can run
online evals. No-op when the key is not set.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Lazy-loaded deepeval tracing (holder avoids global statement)
_tracing_holder: list[tuple | bool | None] = [None]


def _get_tracing():
    """Lazy import deepeval tracing; return None if key not set or import fails."""
    if _tracing_holder[0] is not None:
        return _tracing_holder[0]
    if not os.environ.get("CONFIDENT_API_KEY"):
        _tracing_holder[0] = False
        return _tracing_holder[0]
    try:
        from deepeval.test_case import LLMTestCase  # noqa: PLC0415
        from deepeval.tracing import update_current_span  # noqa: PLC0415

        _tracing_holder[0] = (update_current_span, LLMTestCase)
        return _tracing_holder[0]
    except ImportError:
        logger.warning("deepeval not installed; telemetry disabled", extra={})
        _tracing_holder[0] = False
        return _tracing_holder[0]


def record_classification(
    *,
    input_message: str,
    channel: str,
    response_json: str,
) -> None:
    """Record one classification as telemetry (trace) for production monitoring.

    Call this inside an @observe()-decorated request path. When CONFIDENT_API_KEY
    is set, the input and response are attached to the current span and sent to
    Confident AI. Safe no-op when key is not set or deepeval is unavailable.
    """
    t = _get_tracing()
    if not t:
        return
    update_current_span, LLMTestCase = t
    try:
        update_current_span(
            test_case=LLMTestCase(
                input=f"[channel={channel}] {input_message}",
                actual_output=response_json,
            ),
        )
    except Exception as e:
        logger.warning("telemetry record_classification failed", extra={"error": str(e)})
