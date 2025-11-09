"""
Scheduled actions for firewall rules.

Provides a small scheduler to enforce a once-per-day disable of a specific
firewall rule at a configured local time. Independent from chore logic.
"""

from __future__ import annotations

import logging
import datetime
from typing import Tuple

import pytz


logger = logging.getLogger(__name__)


def _parse_hhmm(time_str: str) -> Tuple[int, int]:
    if not time_str or ":" not in time_str:
        raise ValueError("time_str must be in HH:MM format")
    parts = time_str.split(":", 1)
    hour = int(parts[0])
    minute = int(parts[1])
    if hour < 0 or hour > 23:
        raise ValueError("Hour must be between 0 and 23")
    if minute < 0 or minute > 59:
        raise ValueError("Minute must be between 0 and 59")
    return hour, minute


def _action_key_for_rule(rule_name: str) -> str:
    base = (rule_name or "").strip().lower()
    safe = "".join(ch if ch.isalnum() else "_" for ch in base)
    return f"disable_{safe}_at_time"


class ScheduledRuleEnforcer:
    def __init__(self, sophos_client, state_manager, timezone_str: str):
        if not timezone_str:
            raise ValueError("timezone_str is required")
        try:
            self._tz = pytz.timezone(timezone_str)
        except pytz.UnknownTimeZoneError as e:
            raise ValueError(f"Invalid timezone: {timezone_str}") from e
        self._sophos = sophos_client
        self._state = state_manager

    def enforce_daily_disable(self, rule_name: str, at_time_str: str) -> bool:
        """
        Disable a specific rule once per day at or after the given local time.

        - If now is before the scheduled time, does nothing and returns False.
        - If now is after the scheduled time and the action has not yet run
          today, attempts to set the rule to disabled. On success or if
          already disabled, records completion for today and returns True.
        - If the API call fails, does not record completion and returns False.
        - If already completed earlier today, does nothing and returns False.
        """
        if not rule_name:
            logger.debug("Scheduled disable skipped: rule_name not set")
            return False

        try:
            target_hour, target_minute = _parse_hhmm(at_time_str)
        except ValueError as e:
            logger.error("Invalid scheduled time '%s': %s", at_time_str, e)
            return False

        now = datetime.datetime.now(self._tz)
        today_str = now.strftime("%Y-%m-%d")
        scheduled_dt = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

        if now < scheduled_dt:
            logger.debug("Now %s is before scheduled time %s. No action.", now.strftime('%H:%M'), scheduled_dt.strftime('%H:%M'))
            return False

        action_key = _action_key_for_rule(rule_name)
        if self._state and self._state.has_action_run_today(action_key, today_str):
            logger.debug("Scheduled disable already completed today for key '%s'", action_key)
            return False

        logger.info("Scheduled enforcement: disabling rule '%s' (time window %02d:%02d onward)", rule_name, target_hour, target_minute)

        try:
            success = self._sophos.set_rule_status(rule_name, target_enabled_state=False)
        except Exception as e:
            logger.error("Failed to disable rule '%s' during scheduled enforcement: %s", rule_name, e, exc_info=True)
            return False

        if success:
            logger.info("Scheduled enforcement: rule '%s' is disabled (or already disabled). Recording completion for %s.", rule_name, today_str)
            if self._state:
                self._state.mark_action_run_today(action_key, today_str)
            return True
        else:
            logger.error("Scheduled enforcement: API reported failure disabling rule '%s'. Will retry on next run.", rule_name)
            return False

