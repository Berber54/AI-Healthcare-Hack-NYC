"""Invariant 12: retry once, then fall back gracefully - never crash silently
on a read failure. Pattern ported from VoiceAI_Scheduler's services/error_recovery.py.
"""

import logging
from typing import Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_once(fn: Callable[..., T], *args, fallback: Optional[T] = None, **kwargs) -> Optional[T]:
    try:
        return fn(*args, **kwargs)
    except Exception:
        logger.warning("%s failed, retrying once", getattr(fn, "__name__", fn), exc_info=True)
        try:
            return fn(*args, **kwargs)
        except Exception:
            logger.error("%s failed twice, falling back to %r", getattr(fn, "__name__", fn), fallback, exc_info=True)
            return fallback
