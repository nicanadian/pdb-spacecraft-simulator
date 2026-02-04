"""Structured logging for modelgen operations.

Conventions:
- All log messages include a correlation ID for tracing multi-step operations
- Log levels: DEBUG (internal), INFO (user-facing progress), WARNING (non-fatal), ERROR (fatal)
- Timing hooks on extraction, building, and serialization phases
- Logs go to stderr by default (stdout reserved for data output)

Usage:
    from tools.modelgen.logging import get_logger, timed_operation

    log = get_logger("extractor")
    log.info("Scanning", module="sim.core.types", file_count=5)

    with timed_operation(log, "extraction"):
        # ... work ...
        pass
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator


# Correlation ID for the current run
_correlation_id: str = ""


def new_correlation_id() -> str:
    """Generate a new correlation ID for a pipeline run."""
    global _correlation_id
    _correlation_id = uuid.uuid4().hex[:8]
    return _correlation_id


def get_correlation_id() -> str:
    """Get the current correlation ID."""
    return _correlation_id or "no-corr"


class StructuredFormatter(logging.Formatter):
    """Formatter that outputs structured JSON log lines."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "corr_id": get_correlation_id(),
        }
        # Add extra fields
        for key in ("module_name", "file_count", "node_count", "edge_count",
                     "elapsed_ms", "phase", "error"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val
        return json.dumps(entry)


class HumanFormatter(logging.Formatter):
    """Formatter for human-readable output."""

    COLORS = {
        "DEBUG": "\033[90m",
        "INFO": "\033[36m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET
        corr = get_correlation_id()
        timestamp = self.formatTime(record, "%H:%M:%S")
        msg = record.getMessage()

        # Append extra fields inline
        extras = []
        for key in ("module_name", "file_count", "node_count", "edge_count",
                     "elapsed_ms", "phase"):
            val = getattr(record, key, None)
            if val is not None:
                extras.append(f"{key}={val}")
        extra_str = f" [{', '.join(extras)}]" if extras else ""

        return f"{color}{timestamp} [{corr}] {record.levelname:7s}{reset} {record.name}: {msg}{extra_str}"


def get_logger(name: str, structured: bool = False) -> logging.Logger:
    """Get a logger with modelgen conventions.

    Args:
        name: Logger name (e.g., "extractor", "builder", "cli").
        structured: If True, use JSON output. If False, use human-readable.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(f"modelgen.{name}")

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        if structured:
            handler.setFormatter(StructuredFormatter())
        else:
            handler.setFormatter(HumanFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger


@contextmanager
def timed_operation(
    logger: logging.Logger,
    operation: str,
    **extra: Any,
) -> Generator[dict[str, Any], None, None]:
    """Context manager that logs timing for an operation.

    Usage:
        with timed_operation(log, "extraction", file_count=42) as ctx:
            # do work
            ctx["node_count"] = 100  # add metrics to the completion log

    Args:
        logger: Logger instance.
        operation: Name of the operation.
        **extra: Additional fields to log.
    """
    ctx: dict[str, Any] = {}
    start = time.monotonic()
    logger.info(f"Starting {operation}", extra={"phase": f"{operation}:start", **extra})
    try:
        yield ctx
        elapsed_ms = round((time.monotonic() - start) * 1000)
        logger.info(
            f"Completed {operation}",
            extra={"phase": f"{operation}:done", "elapsed_ms": elapsed_ms, **ctx, **extra},
        )
    except Exception as e:
        elapsed_ms = round((time.monotonic() - start) * 1000)
        logger.error(
            f"Failed {operation}: {e}",
            extra={"phase": f"{operation}:error", "elapsed_ms": elapsed_ms, "error": str(e), **extra},
        )
        raise


@dataclass
class PipelineMetrics:
    """Collects metrics across the modelgen pipeline for reporting."""

    correlation_id: str = ""
    phases: list[dict[str, Any]] = field(default_factory=list)

    def record(self, phase: str, elapsed_ms: float, **metrics: Any) -> None:
        self.phases.append({
            "phase": phase,
            "elapsed_ms": elapsed_ms,
            **metrics,
        })

    def summary(self) -> dict[str, Any]:
        total_ms = sum(p.get("elapsed_ms", 0) for p in self.phases)
        return {
            "correlation_id": self.correlation_id,
            "total_ms": total_ms,
            "phases": self.phases,
        }
