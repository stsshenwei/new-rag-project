from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any
from uuid import uuid4

TRACE_ID_PLACEHOLDER = "-"
DEFAULT_LOG_FORMAT = "%d %level trace=%traceId %logger | %msg"
LOG_BODY_LIMIT = 2048

_trace_id_var: ContextVar[str] = ContextVar("trace_id", default=TRACE_ID_PLACEHOLDER)
_managed_handler_marker = "_rag_observability_handler"
_trace_filter_marker = "_rag_trace_id_filter"

_SENSITIVE_KEY_RE = re.compile(
    r"(authorization|cookie|set-cookie|password|passwd|token|access[_-]?token|refresh[_-]?token|"
    r"id[_-]?token|api[_-]?key|api[_-]?secret|secret|secret[_-]?key|client[_-]?secret|"
    r"private[_-]?key|bearer)",
    re.IGNORECASE,
)
_TRACE_ID_RE = re.compile(r"[^A-Za-z0-9_.:-]")


def configure_logging_from_env() -> None:
    """Configure project logging from LOG_* environment variables.

    The function is intentionally idempotent so uvicorn reloads and tests can
    import app.main repeatedly without accumulating duplicate handlers.
    """
    level, warning = _parse_log_level(os.getenv("LOG_LEVEL", "info"))
    formatter = ObservabilityFormatter(os.getenv("LOG_FORMAT") or DEFAULT_LOG_FORMAT)
    trace_filter = TraceIdFilter()

    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, _managed_handler_marker, False):
            root.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass

    handlers: list[logging.Handler] = []
    stream_handler = logging.StreamHandler(sys.stdout)
    setattr(stream_handler, _managed_handler_marker, True)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(trace_filter)
    handlers.append(stream_handler)

    log_path = (os.getenv("LOG_PATH") or "").strip()
    file_warning = ""
    if log_path:
        try:
            file_path = Path(log_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(file_path, encoding="utf-8")
            setattr(file_handler, _managed_handler_marker, True)
            file_handler.setFormatter(formatter)
            file_handler.addFilter(trace_filter)
            handlers.append(file_handler)
        except Exception as exc:
            file_warning = f"Failed to open LOG_PATH {log_path!r}: {exc}"

    for handler in handlers:
        root.addHandler(handler)
    _ensure_trace_filter(root, trace_filter)
    root.setLevel(level)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        named = logging.getLogger(logger_name)
        named.handlers = []
        named.propagate = True
        named.setLevel(level)
        _ensure_trace_filter(named, trace_filter)

    if warning:
        logging.getLogger(__name__).warning(warning)
    if file_warning:
        logging.getLogger(__name__).warning(file_warning)


def _ensure_trace_filter(logger: logging.Logger, trace_filter: "TraceIdFilter") -> None:
    if any(getattr(item, _trace_filter_marker, False) for item in logger.filters):
        return
    logger.addFilter(trace_filter)


def _parse_log_level(value: str) -> tuple[int, str]:
    normalized = (value or "info").strip().lower()
    levels = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warn": logging.WARNING,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "fatal": logging.FATAL,
        "critical": logging.CRITICAL,
    }
    if normalized in levels:
        return levels[normalized], ""
    return logging.INFO, f"Invalid LOG_LEVEL={value!r}; falling back to info"


def set_trace_id(trace_id: str | None) -> Any:
    return _trace_id_var.set(sanitize_trace_id(trace_id))


def reset_trace_id(token: Any) -> None:
    _trace_id_var.reset(token)


def get_trace_id() -> str:
    return _trace_id_var.get() or TRACE_ID_PLACEHOLDER


def generate_trace_id() -> str:
    return uuid4().hex


def sanitize_trace_id(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return TRACE_ID_PLACEHOLDER
    sanitized = _TRACE_ID_RE.sub("-", raw)[:128].strip(".:-_")
    return sanitized or TRACE_ID_PLACEHOLDER


@contextmanager
def trace_context(trace_id: str | None = None):
    token = set_trace_id(trace_id or generate_trace_id())
    try:
        yield get_trace_id()
    finally:
        reset_trace_id(token)


class TraceIdFilter(logging.Filter):
    def __init__(self) -> None:
        super().__init__()
        setattr(self, _trace_filter_marker, True)

    def filter(self, record: logging.LogRecord) -> bool:
        trace_id = get_trace_id()
        record.traceId = trace_id
        record.trace_id = trace_id
        return True


class ObservabilityFormatter(logging.Formatter):
    def __init__(self, template: str = DEFAULT_LOG_FORMAT) -> None:
        super().__init__()
        self.template = template or DEFAULT_LOG_FORMAT

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        if datefmt:
            return super().formatTime(record, datefmt)
        formatted = time.strftime("%Y-%m-%d %H:%M:%S", self.converter(record.created))
        millis = int(record.msecs)
        return f"{formatted}.{millis:03d}"

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            record.message = f"{record.message}\n{exc_text}"
        record.message = _redact_sensitive_text(record.message)
        message = self._message_with_extras(record)
        replacements = {
            "%d": self.formatTime(record),
            "%level": record.levelname.upper(),
            "%traceId": str(getattr(record, "traceId", TRACE_ID_PLACEHOLDER) or TRACE_ID_PLACEHOLDER),
            "%logger": record.name,
            "%msg": message,
        }
        output = self.template
        for placeholder, value in replacements.items():
            output = output.replace(placeholder, value)
        return output

    def _message_with_extras(self, record: logging.LogRecord) -> str:
        standard = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)
        standard.update({"message", "asctime", "traceId", "trace_id"})
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in standard and not key.startswith("_")
        }
        if not extras:
            return record.message
        extra_text = " ".join(f"{key}={_safe_log_value(value)}" for key, value in sorted(extras.items()))
        return f"{record.message} {extra_text}"


def sanitize_headers(headers: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in dict(headers or {}).items():
        result[str(key)] = "***" if _SENSITIVE_KEY_RE.search(str(key)) else truncate_text(str(value), LOG_BODY_LIMIT)
    return result


def sanitize_payload(value: Any, *, limit: int = LOG_BODY_LIMIT) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "***" if _SENSITIVE_KEY_RE.search(str(key)) else sanitize_payload(item, limit=limit)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_payload(item, limit=limit) for item in value[:50]]
    if isinstance(value, str):
        return truncate_text(_redact_sensitive_text(value), limit)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return truncate_text(_redact_sensitive_text(str(value)), limit)


def summarize_body(body: bytes, content_type: str = "", *, limit: int = LOG_BODY_LIMIT) -> str:
    content_type = (content_type or "").lower()
    if not body:
        return ""
    if "multipart/" in content_type or "application/octet-stream" in content_type:
        return f"[binary body skipped size={len(body)}]"
    if "text/event-stream" in content_type:
        return "[streaming response skipped]"
    if "json" in content_type:
        try:
            parsed = json.loads(body.decode("utf-8"))
            return truncate_text(json.dumps(sanitize_payload(parsed, limit=limit), ensure_ascii=False), limit)
        except Exception:
            pass
    if "text/" in content_type or "application/x-www-form-urlencoded" in content_type or not content_type:
        try:
            return truncate_text(_redact_sensitive_text(body.decode("utf-8", errors="replace")), limit)
        except Exception:
            return f"[text body decode failed size={len(body)}]"
    return f"[body skipped content_type={content_type or '-'} size={len(body)}]"


def truncate_text(value: str, limit: int = LOG_BODY_LIMIT) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "... [truncated]"


def _redact_sensitive_text(value: str) -> str:
    redacted = re.sub(
        r"(?i)(authorization|password|passwd|token|api[_-]?key|secret|client[_-]?secret)(['\"\s:=]+)([^,'\"\s&}]+)",
        r"\1\2***",
        value,
    )
    redacted = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer ***", redacted)
    return redacted


def _safe_log_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return truncate_text(json.dumps(sanitize_payload(value), ensure_ascii=False, sort_keys=True), LOG_BODY_LIMIT)
    return truncate_text(_redact_sensitive_text(str(value)), LOG_BODY_LIMIT)
