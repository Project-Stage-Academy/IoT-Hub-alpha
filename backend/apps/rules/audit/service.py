from __future__ import annotations

import contextvars
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

try:
    from config.logging import get_logging_context
except ImportError:

    def get_logging_context() -> dict[str, str | None]:
        return {
            "request_id": None,
            "task_id": None,
            "task_name": None,
        }


from ..models import Rule, RuleAuditLog

# Keep payload focused on rule configuration changes, not runtime counters/timestamps.
TRACKED_RULE_FIELDS: tuple[str, ...] = (
    "name",
    "description",
    "condition",
    "action_config",
    "is_enabled",
    "device_id",
)

_REDACTED_VALUE = "***redacted***"
_SENSITIVE_KEYWORDS = (
    "token",
    "secret",
    "password",
    "api_key",
    "apikey",
    "authorization",
)

_audit_actor_context: contextvars.ContextVar[dict[str, Any] | None] = (
    contextvars.ContextVar("rule_audit_actor_context", default=None)
)


def bind_audit_actor(user) -> contextvars.Token:
    actor_user_id = None
    actor_username = None

    if user is not None and getattr(user, "is_authenticated", False):
        actor_user_id = user.id
        actor_username = user.get_username()

    return _audit_actor_context.set(
        {
            "actor_user_id": actor_user_id,
            "actor_username": actor_username,
        }
    )


def reset_audit_actor(token: contextvars.Token) -> None:
    _audit_actor_context.reset(token)


def get_bound_audit_actor() -> tuple[int | None, str | None]:
    bound = _audit_actor_context.get()
    if not bound:
        return None, None
    return bound.get("actor_user_id"), bound.get("actor_username")


def normalize_rule_id(rule_id: Any) -> UUID | None:
    if rule_id is None:
        return None
    if isinstance(rule_id, UUID):
        return rule_id
    try:
        return UUID(str(rule_id))
    except (TypeError, ValueError):
        return None


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in _SENSITIVE_KEYWORDS)


def to_json_primitive(value: Any) -> Any:
    if isinstance(value, dict):
        payload: dict[str, Any] = {}
        for key, nested in value.items():
            normalized_key = str(key)
            if _is_sensitive_key(normalized_key):
                payload[normalized_key] = _REDACTED_VALUE
            else:
                payload[normalized_key] = to_json_primitive(nested)
        return payload

    if isinstance(value, list):
        return [to_json_primitive(item) for item in value]

    if isinstance(value, tuple):
        return [to_json_primitive(item) for item in value]

    if isinstance(value, set):
        ordered = sorted(value, key=lambda item: str(item))
        return [to_json_primitive(item) for item in ordered]

    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    return str(value)


def serialize_rule_state(rule: Rule | dict[str, Any]) -> dict[str, Any]:
    state: dict[str, Any] = {}
    for field_name in TRACKED_RULE_FIELDS:
        if isinstance(rule, dict):
            raw_value = rule.get(field_name)
        else:
            raw_value = getattr(rule, field_name)

        state[field_name] = to_json_primitive(deepcopy(raw_value))
    return state


def diff_rule_states(
    before_state: dict[str, Any],
    after_state: dict[str, Any],
) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    changed_fields: list[str] = []
    before_delta: dict[str, Any] = {}
    after_delta: dict[str, Any] = {}

    for field_name in TRACKED_RULE_FIELDS:
        before_value = before_state.get(field_name)
        after_value = after_state.get(field_name)
        if before_value != after_value:
            changed_fields.append(field_name)
            before_delta[field_name] = before_value
            after_delta[field_name] = after_value

    return changed_fields, before_delta, after_delta


def get_request_id_from_request(request) -> str | None:
    request_id = getattr(request, "request_id", None)
    if request_id:
        return str(request_id)

    if hasattr(request, "headers"):
        header_value = request.headers.get("X-Request-ID")
        if header_value:
            return str(header_value)

    return request.META.get("HTTP_X_REQUEST_ID")


def infer_signal_source() -> str:
    context = get_logging_context()
    if context.get("task_id") or context.get("task_name"):
        return RuleAuditLog.Source.SYSTEM
    if context.get("request_id"):
        return RuleAuditLog.Source.API
    return RuleAuditLog.Source.SIGNAL


def create_rule_audit_log(
    *,
    rule_id: Any,
    action: str,
    changed_fields: list[str],
    before: dict[str, Any],
    after: dict[str, Any],
    actor_user_id: int | None = None,
    actor_username: str | None = None,
    request_id: str | None = None,
    source: str | None = None,
) -> RuleAuditLog:
    if actor_user_id is None and actor_username is None:
        actor_user_id, actor_username = get_bound_audit_actor()

    if request_id is None:
        request_id = get_logging_context().get("request_id")

    if source is None:
        source = infer_signal_source()

    return RuleAuditLog.objects.create(
        rule_id=normalize_rule_id(rule_id),
        action=action,
        changed_fields=to_json_primitive(changed_fields),
        before=to_json_primitive(before),
        after=to_json_primitive(after),
        actor_user_id=actor_user_id,
        actor_username=actor_username,
        request_id=request_id,
        source=source,
    )
