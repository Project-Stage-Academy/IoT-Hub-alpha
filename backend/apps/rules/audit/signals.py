from __future__ import annotations

import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from ..models import Rule, RuleAuditLog
from .service import (
    TRACKED_RULE_FIELDS,
    create_rule_audit_log,
    diff_rule_states,
    get_bound_audit_actor,
    get_logging_context,
    infer_signal_source,
    serialize_rule_state,
)

logger = logging.getLogger(__name__)


def _safe_create_audit_log(**kwargs) -> None:
    try:
        create_rule_audit_log(**kwargs)
    except Exception:
        logger.exception(
            "rule_audit_write_failed",
            extra={
                "rule_id": (
                    str(kwargs.get("rule_id")) if kwargs.get("rule_id") else None
                ),
                "action": kwargs.get("action"),
                "source": kwargs.get("source"),
            },
        )


@receiver(pre_save, sender=Rule)
def cache_rule_previous_state(sender, instance: Rule, raw: bool = False, **kwargs):
    if raw:
        return

    if not instance.pk:
        instance._audit_previous_state = None
        return

    previous_row = (
        Rule.objects.filter(pk=instance.pk).values(*TRACKED_RULE_FIELDS).first()
    )
    instance._audit_previous_state = (
        serialize_rule_state(previous_row) if previous_row else None
    )


@receiver(post_save, sender=Rule)
def audit_rule_saved(
    sender,
    instance: Rule,
    created: bool,
    raw: bool = False,
    **kwargs,
):
    if raw:
        return

    actor_user_id, actor_username = get_bound_audit_actor()
    request_id = get_logging_context().get("request_id")
    source = infer_signal_source()

    current_state = serialize_rule_state(instance)

    if created:
        changed_fields = list(current_state.keys())
        before_state: dict = {}
        after_state = current_state
        action = RuleAuditLog.Action.CREATE
    else:
        previous_state = getattr(instance, "_audit_previous_state", None) or {}

        changed_fields, before_state, after_state = diff_rule_states(
            previous_state,
            current_state,
        )
        if not changed_fields:
            return

        action = RuleAuditLog.Action.UPDATE

    transaction.on_commit(
        lambda: _safe_create_audit_log(
            rule_id=instance.pk,
            action=action,
            changed_fields=changed_fields,
            before=before_state,
            after=after_state,
            actor_user_id=actor_user_id,
            actor_username=actor_username,
            request_id=request_id,
            source=source,
        ),
        robust=True,
    )


@receiver(post_delete, sender=Rule)
def audit_rule_deleted(sender, instance: Rule, **kwargs):
    actor_user_id, actor_username = get_bound_audit_actor()
    request_id = get_logging_context().get("request_id")
    source = infer_signal_source()

    before_state = serialize_rule_state(instance)
    changed_fields = list(before_state.keys())

    transaction.on_commit(
        lambda: _safe_create_audit_log(
            rule_id=instance.pk,
            action=RuleAuditLog.Action.DELETE,
            changed_fields=changed_fields,
            before=before_state,
            after={},
            actor_user_id=actor_user_id,
            actor_username=actor_username,
            request_id=request_id,
            source=source,
        ),
        robust=True,
    )
