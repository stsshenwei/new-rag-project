from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator

from app.services.infrastructure.logging_config import get_trace_id

logger = logging.getLogger(__name__)

_current_trace_handle: ContextVar[Any | None] = ContextVar("observability_trace_handle", default=None)
_current_span_handle: ContextVar[Any | None] = ContextVar("observability_span_handle", default=None)
_current_observation_id: ContextVar[str] = ContextVar("observability_observation_id", default="")

_global_sink: "ObservabilitySink | None" = None


@dataclass(frozen=True)
class ObservabilityConfig:
    enabled: bool = False
    host: str = ""
    public_key: str = ""
    secret_key: str = ""
    environment: str = ""
    release: str = ""
    debug: bool = False
    payload_char_limit: int = 2000

    @classmethod
    def from_env(cls) -> "ObservabilityConfig":
        return cls(
            enabled=_env_bool("LANGFUSE_ENABLED", False),
            host=_get_env("LANGFUSE_BASE_URL", "LANGFUSE_HOST"),
            public_key=_get_env("LANGFUSE_PUBLIC_KEY"),
            secret_key=_get_env("LANGFUSE_SECRET_KEY"),
            environment=_get_env("LANGFUSE_ENVIRONMENT"),
            release=_get_env("LANGFUSE_RELEASE"),
            debug=_env_bool("LANGFUSE_DEBUG", False),
            payload_char_limit=_env_int("LANGFUSE_PAYLOAD_CHAR_LIMIT", 2000),
        )

    @property
    def configured(self) -> bool:
        return bool(self.enabled and self.public_key and self.secret_key)


@dataclass
class ObservabilityStatus:
    enabled: bool
    configured: bool
    package_available: bool
    initialized: bool
    failed: bool
    host: str
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ObservationHandle:
    def __init__(self, sink: "ObservabilitySink", raw: Any | None = None, observation_id: str = ""):
        self.sink = sink
        self.raw = raw
        self.observation_id = observation_id

    def finish(
        self,
        *,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
        error: BaseException | None = None,
        usage: dict[str, Any] | None = None,
    ) -> None:
        self.sink.finish_observation(self, output=output, metadata=metadata, error=error, usage=usage)


class ObservabilitySink:
    def status(self) -> ObservabilityStatus:
        return ObservabilityStatus(False, False, True, False, False, "")

    def start_trace(
        self,
        *,
        name: str,
        trace_id: str | None = None,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> ObservationHandle:
        return ObservationHandle(self)

    def resume_trace(self, trace_id: str | None) -> ObservationHandle:
        return ObservationHandle(self)

    def start_span(
        self,
        *,
        name: str,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ObservationHandle:
        return ObservationHandle(self)

    def start_generation(
        self,
        *,
        name: str,
        model: str,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
        model_parameters: dict[str, Any] | None = None,
    ) -> ObservationHandle:
        return ObservationHandle(self)

    def event(self, *, name: str, metadata: dict[str, Any] | None = None, input: Any | None = None) -> None:
        return None

    def finish_observation(
        self,
        handle: ObservationHandle,
        *,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
        error: BaseException | None = None,
        usage: dict[str, Any] | None = None,
    ) -> None:
        return None

    def flush(self) -> None:
        return None

    @contextmanager
    def trace(
        self,
        *,
        name: str,
        trace_id: str | None = None,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Iterator[ObservationHandle]:
        trace = self.start_trace(name=name, trace_id=trace_id, input=input, metadata=metadata, tags=tags)
        trace_token = _current_trace_handle.set(trace.raw)
        parent_token = _current_span_handle.set(None)
        observation_token = _current_observation_id.set(trace.observation_id)
        try:
            yield trace
        except Exception as exc:
            trace.finish(error=exc)
            raise
        else:
            trace.finish()
        finally:
            _current_observation_id.reset(observation_token)
            _current_span_handle.reset(parent_token)
            _current_trace_handle.reset(trace_token)

    @contextmanager
    def span(
        self,
        *,
        name: str,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Iterator[ObservationHandle]:
        span = self.start_span(name=name, input=input, metadata=metadata)
        parent_token = _current_span_handle.set(span.raw)
        observation_token = _current_observation_id.set(span.observation_id)
        try:
            yield span
        except Exception as exc:
            span.finish(error=exc)
            raise
        else:
            span.finish()
        finally:
            _current_observation_id.reset(observation_token)
            _current_span_handle.reset(parent_token)

    @contextmanager
    def generation(
        self,
        *,
        name: str,
        model: str,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
        model_parameters: dict[str, Any] | None = None,
    ) -> Iterator[ObservationHandle]:
        generation = self.start_generation(
            name=name,
            model=model,
            input=input,
            metadata=metadata,
            model_parameters=model_parameters,
        )
        parent_token = _current_span_handle.set(generation.raw)
        observation_token = _current_observation_id.set(generation.observation_id)
        try:
            yield generation
        except Exception as exc:
            generation.finish(error=exc)
            raise
        finally:
            _current_observation_id.reset(observation_token)
            _current_span_handle.reset(parent_token)


class NoopObservabilitySink(ObservabilitySink):
    def __init__(self, config: ObservabilityConfig | None = None, reason: str = "disabled"):
        self.config = config or ObservabilityConfig()
        self.reason = reason

    def status(self) -> ObservabilityStatus:
        return ObservabilityStatus(
            enabled=self.config.enabled,
            configured=self.config.configured,
            package_available=True,
            initialized=False,
            failed=False,
            host=self.config.host,
            reason=self.reason,
        )


class LangfuseObservabilitySink(ObservabilitySink):
    def __init__(self, config: ObservabilityConfig):
        self.config = config
        self._client: Any | None = None
        self._failed_reason = ""
        self._package_available: bool | None = None
        self._warned = False

    def status(self) -> ObservabilityStatus:
        package_available = self._package_available
        if package_available is None:
            package_available = self._check_package_available()
        return ObservabilityStatus(
            enabled=self.config.enabled,
            configured=self.config.configured,
            package_available=package_available,
            initialized=self._client is not None,
            failed=bool(self._failed_reason),
            host=self.config.host,
            reason=self._failed_reason,
        )

    def start_trace(
        self,
        *,
        name: str,
        trace_id: str | None = None,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> ObservationHandle:
        client = self._get_client()
        if client is None:
            return ObservationHandle(self)
        trace_id = _safe_id(trace_id or get_trace_id())
        payload: dict[str, Any] = {
            "id": trace_id,
            "name": name,
            "input": sanitize_observability_payload(input, self.config.payload_char_limit),
            "metadata": sanitize_observability_payload(metadata or {}, self.config.payload_char_limit),
        }
        if tags:
            payload["tags"] = tags
        if self.config.environment:
            payload["environment"] = self.config.environment
        if self.config.release:
            payload["release"] = self.config.release
        try:
            raw = client.trace(**payload)
            return ObservationHandle(self, raw=raw, observation_id=trace_id)
        except Exception as exc:
            self._mark_failed(f"trace start failed: {exc}")
            return ObservationHandle(self)

    def resume_trace(self, trace_id: str | None) -> ObservationHandle:
        if not trace_id:
            return ObservationHandle(self)
        return self.start_trace(name="resume", trace_id=trace_id, metadata={"resumed": True})

    def start_span(
        self,
        *,
        name: str,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ObservationHandle:
        parent = _current_span_handle.get()
        trace = _current_trace_handle.get()
        owner = parent or trace
        if owner is None:
            trace_handle = self.start_trace(name=name, trace_id=get_trace_id())
            owner = trace_handle.raw
            if owner is None:
                return ObservationHandle(self)
            _current_trace_handle.set(owner)
        raw = self._call_start(owner, "span", name=name, input=input, metadata=metadata)
        return ObservationHandle(self, raw=raw, observation_id=_extract_observation_id(raw))

    def start_generation(
        self,
        *,
        name: str,
        model: str,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
        model_parameters: dict[str, Any] | None = None,
    ) -> ObservationHandle:
        parent = _current_span_handle.get()
        trace = _current_trace_handle.get()
        owner = parent or trace
        if owner is None:
            trace_handle = self.start_trace(name=name, trace_id=get_trace_id())
            owner = trace_handle.raw
            if owner is None:
                return ObservationHandle(self)
            _current_trace_handle.set(owner)
        raw = self._call_start(
            owner,
            "generation",
            name=name,
            input=input,
            metadata=metadata,
            model=model,
            model_parameters=model_parameters,
        )
        if raw is None:
            raw = self._call_start(
                owner,
                "span",
                name=name,
                input=input,
                metadata={**(metadata or {}), "model": model, "observation_type": "generation"},
            )
        return ObservationHandle(self, raw=raw, observation_id=_extract_observation_id(raw))

    def event(self, *, name: str, metadata: dict[str, Any] | None = None, input: Any | None = None) -> None:
        owner = _current_span_handle.get() or _current_trace_handle.get()
        event = getattr(owner, "event", None) if owner is not None else None
        if not callable(event):
            return
        try:
            event(
                name=name,
                input=sanitize_observability_payload(input, self.config.payload_char_limit),
                metadata=sanitize_observability_payload(metadata or {}, self.config.payload_char_limit),
            )
        except Exception as exc:
            self._mark_failed(f"event failed: {exc}")

    def finish_observation(
        self,
        handle: ObservationHandle,
        *,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
        error: BaseException | None = None,
        usage: dict[str, Any] | None = None,
    ) -> None:
        raw = handle.raw
        if raw is None:
            return
        safe_output = sanitize_observability_payload(output, self.config.payload_char_limit)
        safe_metadata = sanitize_observability_payload(metadata or {}, self.config.payload_char_limit)
        try:
            end = getattr(raw, "end", None)
            if callable(end):
                kwargs: dict[str, Any] = {"output": safe_output}
                if safe_metadata:
                    kwargs["metadata"] = safe_metadata
                if usage:
                    kwargs["usage"] = usage
                if error is not None:
                    kwargs["level"] = "ERROR"
                    kwargs["status_message"] = _safe_error_message(error)
                end(**kwargs)
                return
            finish = getattr(raw, "finish", None)
            if callable(finish):
                finish(safe_output, usage, error)
        except Exception as exc:
            self._mark_failed(f"finish failed: {exc}")

    def flush(self) -> None:
        client = self._client
        if client is None:
            return
        flush = getattr(client, "flush", None)
        if not callable(flush):
            return
        try:
            flush()
        except Exception as exc:
            self._mark_failed(f"flush failed: {exc}")

    def _call_start(self, owner: Any, method_name: str, **kwargs: Any) -> Any | None:
        method = getattr(owner, method_name, None)
        if not callable(method):
            return None
        payload = {
            key: sanitize_observability_payload(value, self.config.payload_char_limit)
            for key, value in kwargs.items()
            if value is not None
        }
        if "model_parameters" in kwargs and kwargs["model_parameters"] is not None:
            payload["model_parameters"] = sanitize_observability_payload(
                kwargs["model_parameters"], self.config.payload_char_limit
            )
        try:
            return method(**payload)
        except TypeError:
            payload.pop("model_parameters", None)
            try:
                return method(**payload)
            except Exception as exc:
                self._mark_failed(f"{method_name} start failed: {exc}")
                return None
        except Exception as exc:
            self._mark_failed(f"{method_name} start failed: {exc}")
            return None

    def _get_client(self) -> Any | None:
        if self._failed_reason:
            return None
        if not self.config.enabled:
            return None
        if not self.config.public_key or not self.config.secret_key:
            self._mark_failed("missing LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY")
            return None
        if self._client is not None:
            return self._client
        try:
            from langfuse import Langfuse  # type: ignore

            kwargs: dict[str, Any] = {
                "public_key": self.config.public_key,
                "secret_key": self.config.secret_key,
            }
            if self.config.host:
                kwargs["host"] = self.config.host
            self._client = Langfuse(**kwargs)
            self._package_available = True
            logger.info("langfuse.enabled", extra={"host": self.config.host or "default"})
            return self._client
        except ImportError as exc:
            self._package_available = False
            self._mark_failed(f"langfuse package unavailable: {exc}")
            return None
        except Exception as exc:
            self._mark_failed(f"client initialization failed: {exc}")
            return None

    def _check_package_available(self) -> bool:
        try:
            __import__("langfuse")
            self._package_available = True
            return True
        except Exception:
            self._package_available = False
            return False

    def _mark_failed(self, reason: str) -> None:
        self._failed_reason = reason
        if not self._warned or self.config.debug:
            logger.warning("langfuse.unavailable", extra={"reason": reason, "host": self.config.host})
            self._warned = True


def configure_observability_from_env() -> ObservabilitySink:
    config = ObservabilityConfig.from_env()
    if not config.enabled:
        sink: ObservabilitySink = NoopObservabilitySink(config, reason="disabled")
    elif not config.public_key or not config.secret_key:
        sink = NoopObservabilitySink(config, reason="missing credentials")
        logger.warning("langfuse.not_configured", extra={"host": config.host, "reason": "missing credentials"})
    else:
        sink = LangfuseObservabilitySink(config)
    set_observability_sink(sink)
    return sink


def set_observability_sink(sink: ObservabilitySink) -> None:
    global _global_sink
    _global_sink = sink


def get_observability_sink() -> ObservabilitySink:
    return _global_sink or NoopObservabilitySink()


@contextmanager
def use_observability_trace(trace_id: str | None, *, name: str = "resume") -> Iterator[ObservationHandle]:
    sink = get_observability_sink()
    trace = sink.start_trace(name=name, trace_id=trace_id or get_trace_id(), metadata={"resumed": True})
    trace_token = _current_trace_handle.set(trace.raw)
    parent_token = _current_span_handle.set(None)
    observation_token = _current_observation_id.set(trace.observation_id)
    try:
        yield trace
    finally:
        _current_observation_id.reset(observation_token)
        _current_span_handle.reset(parent_token)
        _current_trace_handle.reset(trace_token)


def current_observation_id() -> str:
    return _current_observation_id.get()


@contextmanager
def activate_observation(handle: ObservationHandle | None, *, as_trace: bool = False) -> Iterator[None]:
    if handle is None:
        yield
        return
    if as_trace:
        trace_token = _current_trace_handle.set(handle.raw)
        parent_token = None
    else:
        trace_token = None
        parent_token = _current_span_handle.set(handle.raw)
    observation_token = _current_observation_id.set(handle.observation_id)
    try:
        yield
    finally:
        _current_observation_id.reset(observation_token)
        if parent_token is not None:
            _current_span_handle.reset(parent_token)
        if trace_token is not None:
            _current_trace_handle.reset(trace_token)


def sanitize_observability_payload(value: Any, limit: int = 2000) -> Any:
    secret_markers = (
        "authorization",
        "cookie",
        "password",
        "passwd",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
        "secret",
        "private_key",
        "reasoning_content",
        "hidden_reasoning",
        "raw_prompt",
    )
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            text_key = str(key)
            if any(marker in text_key.lower() for marker in secret_markers):
                sanitized[text_key] = "[redacted]"
            else:
                sanitized[text_key] = sanitize_observability_payload(item, limit)
        return sanitized
    if isinstance(value, (list, tuple, set)):
        result = [sanitize_observability_payload(item, limit) for item in list(value)[:100]]
        if len(value) > 100:
            result.append({"truncated_items": len(value) - 100})
        return result
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str):
        if len(value) > limit:
            return value[:limit] + "...[truncated]"
        return _redact_secret_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if hasattr(value, "model_dump"):
        return sanitize_observability_payload(value.model_dump(), limit)
    return sanitize_observability_payload(str(value), limit)


def _get_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip().strip('"').strip("'")
    return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning("invalid observability int env", extra={"name": name, "value": value})
        return default


def _safe_id(value: str | None) -> str:
    raw = str(value or "").strip()
    return raw or get_trace_id()


def _extract_observation_id(raw: Any | None) -> str:
    if raw is None:
        return ""
    for attr in ("id", "observation_id", "observationId"):
        value = getattr(raw, attr, "")
        if value:
            return str(value)
    return ""


def _safe_error_message(error: BaseException) -> str:
    return sanitize_observability_payload(f"{error.__class__.__name__}: {error}", 512)


def _redact_secret_text(value: str) -> str:
    # Keep this intentionally simple and deterministic; structured keys are
    # handled above, this only catches common inline assignments.
    redacted = value
    for marker in ("api_key", "token", "secret", "password", "authorization"):
        lower = redacted.lower()
        index = lower.find(marker)
        if index >= 0 and len(redacted) - index > 24:
            redacted = redacted[: index + len(marker)] + "=[redacted]"
    return redacted
