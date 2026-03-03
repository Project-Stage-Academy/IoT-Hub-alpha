"""
Real-time rule evaluator.

Orchestrates evaluation of all rules for a device against single telemetry point.
Maintains window states for windowed rules.
"""

import logging
from uuid import UUID
from typing import Dict, List

from apps.rules.models import Rule
from apps.rules.services.window_state import WindowState, TelemetryPoint
from apps.rules.services.data_structure import Condition, EvalResults
from apps.rules.services.rule_eval import eval_rule
from apps.rules.services.trigger_engine import trigger_engine_realtime
from apps.rules.services.metrics import (
    track_rule_evaluation,
    record_rule_result,
    record_window_state_points,
    record_evaluator_cache_stats,
    track_window_state_cleanup,
)

logger = logging.getLogger("rules.evaluator")


class RealTimeRuleEvaluator:
    """
    Orchestrates real-time rule evaluation.

    Maintains:
    - Window states for each rule (for windowed rules)
    - Cache of rules per device
    - Optional Kafka producer for event dispatch
    """

    def __init__(self, producer=None):
        self.window_states: Dict[UUID, WindowState] = {}
        self.rule_cache: Dict[UUID, List[Rule]] = {}
        self.producer = producer  # Optional Kafka producer

    def evaluate(
        self, device_id: UUID, telemetry_point: TelemetryPoint
    ) -> Dict[UUID, EvalResults]:
        """
        Evaluate all enabled rules for a device against single point.

        Args:
            device_id: Device UUID
            telemetry_point: Single (timestamp, value) pair

        Returns:
            Dict of {rule_id: EvalResults} for triggered rules (empty dict if none)
        """
        triggered = {}

        rules = self._get_rules_for_device(device_id)

        cached_rules = len(rules)
        hit_rate = (100 * len(self.rule_cache)) / max(1, len(self.rule_cache) + 1)
        record_evaluator_cache_stats(device_id, cached_rules, hit_rate)

        for rule in rules:
            try:
                window_state = self.window_states.get(
                    rule.id,
                    WindowState(window_seconds=rule.condition.get("window_seconds", 1)),
                )

                window_state.add_point(telemetry_point.ts, telemetry_point.value)

                record_window_state_points(rule.id, device_id, len(window_state.values))

                condition = Condition.model_validate(rule.condition)
                initial_trigger = EvalResults(
                    trigger=False,
                    values=[],
                    start=(
                        window_state.values[0].ts
                        if window_state.values
                        else telemetry_point.ts
                    ),
                    end=telemetry_point.ts,
                )

                operator = condition.operator or "compound"
                with track_rule_evaluation(rule.id, device_id, operator):
                    result = eval_rule(
                        condition=condition,
                        telemetry_chunks=window_state.values,
                        aggregate_trigger=initial_trigger,
                        device_id=device_id,
                    )

                self.window_states[rule.id] = window_state

                record_rule_result(rule.id, device_id, result.trigger)

                if result.trigger:
                    triggered[rule.id] = result

            except Exception as e:
                logger.error(
                    f"Error evaluating rule {rule.id}: {e}",
                    exc_info=True,
                    extra={"rule_id": str(rule.id), "device_id": str(device_id)},
                )
                continue

        if self.producer and triggered:
            for rule_id, result in triggered.items():
                try:
                    trigger_engine_realtime(rule_id, device_id, result, self.producer)
                except Exception as e:
                    logger.error(
                        f"Error dispatching rule {rule_id} to Kafka: {e}",
                        exc_info=True,
                        extra={"rule_id": str(rule_id), "device_id": str(device_id)},
                    )

        return triggered

    def _get_rules_for_device(self, device_id: UUID) -> List[Rule]:
        """
        Retrieve enabled rules for device with LRU caching.

        Queries database once per device and caches result. Subsequent calls for
        same device return cached rules without database hit. Cache is invalidated
        when rule is updated via on_rule_updated() signal handler.

        Args:
            device_id: Device UUID to fetch rules for

        Returns:
            List of enabled Rule objects for device (sorted by creation if needed)

        Caching:
            - First call: Database query executed and results cached
            - Subsequent calls: Return cached results (O(1) lookup)
            - Cache lifetime: Until on_rule_updated() or clear_cache() called
        """
        if device_id not in self.rule_cache:
            rules = Rule.objects.filter(device_id=device_id, is_enabled=True).only(
                "id", "condition", "action_config", "device_id"
            )
            self.rule_cache[device_id] = list(rules)
            logger.info(
                "Loaded %d rules for device %s",
                len(self.rule_cache[device_id]),
                str(device_id),
            )
            for rule in self.rule_cache[device_id]:
                logger.info(
                    "  Rule %s: %s",
                    rule.id,
                    rule.condition,
                )

        return self.rule_cache[device_id]

    def clear_old_states(self, older_than_seconds: int = 3600) -> None:
        """
        Cleanup expired telemetry points from window states and remove empty states.

        Iterates through all window states, removes expired telemetry points (older than
        older_than_seconds), and deletes window states that have no remaining points.
        Should be called periodically (e.g., hourly) to prevent unbounded memory growth.

        Args:
            older_than_seconds: Age threshold in seconds - points older than
                               this are removed (default: 3600 = 1 hour)

        Side Effects:
        - Removes expired TelemetryPoint objects from each window state
        - Deletes entries from window_states dict for rules with no remaining points
        - Records cleanup timing metrics via track_window_state_cleanup()

        Performance:
        - O(n*m) where n = number of window states, m = average points per window
        - Typical execution: < 10ms for 1000 window states with 10 points each
        """
        from django.utils import timezone

        now = timezone.now()
        to_delete = []

        for rule_id, state in self.window_states.items():
            with track_window_state_cleanup(rule_id):
                state.cleanup_expired(now)
            # Delete if no points left
            if not state.values:
                to_delete.append(rule_id)

        for rule_id in to_delete:
            del self.window_states[rule_id]

    def on_rule_updated(self, rule_id: UUID) -> None:
        """
        Invalidate cached state for updated rule (called by Django signal handler).

        When a rule is updated, its evaluation results become stale. This method
        invalidates all caches related to that rule:
        1. Deletes window state for rule (will be recreated on next eval)
        2. Clears device rule caches (next eval will re-query database)

        This method must be connected to Rule.post_save signal to ensure consistency.

        Usage (in signals.py):
            @receiver(post_save, sender=Rule)
            def on_rule_updated(sender, instance, **kwargs):
                evaluator.on_rule_updated(instance.id)

        Args:
            rule_id: UUID of rule that was updated

        Side Effects:
        - Removes rule from window_states dict (if present)
        - Clears all device rule caches (forces re-query on next eval)
        """
        # Clear window state so it's recreated on next eval
        self.window_states.pop(rule_id, None)
        # Clear device caches
        for device_id in list(self.rule_cache.keys()):
            self.rule_cache[device_id] = []

    def clear_cache(self, device_id: UUID) -> None:
        """
        Clear cached rules for specific device (forces re-query on next eval).

        Removes device from rule_cache dict. Next call to _get_rules_for_device()
        will query database instead of returning cached results. Useful when:
        - Device rules are modified outside evaluator (direct DB update)
        - Device is deleted (prevent stale rule references)
        - Testing/debugging (force fresh data)

        Args:
            device_id: Device UUID whose rule cache should be cleared
        """
        self.rule_cache.pop(device_id, None)

    def get_metrics(self) -> dict:
        """
        Return current evaluator performance metrics for monitoring.

        Provides snapshot of evaluator internal state useful for debugging and
        monitoring. Can be exposed via HTTP endpoint or logged periodically.

        Returns:
            Dict with keys:
            - cached_rules: Total number of rules cached across all devices
            - active_windows: Number of window states (one per active rule)
            - total_points_in_windows: Total accumulated telemetry points
                                       across all windows

        Example Output:
            {
                'cached_rules': 150,
                'active_windows': 45,
                'total_points_in_windows': 2300
            }

        Usage:
            metrics = evaluator.get_metrics()
            print(f"Evaluator state: {metrics['cached_rules']} rules, "
                  f"{metrics['active_windows']} windows")
        """
        return {
            "cached_rules": sum(len(r) for r in self.rule_cache.values()),
            "active_windows": len(self.window_states),
            "total_points_in_windows": sum(
                len(s.values) for s in self.window_states.values()
            ),
        }
