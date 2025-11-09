#!/usr/bin/env python3
"""
Unit tests for scheduled daily disable of Sophie's manual allow rule.
"""

import unittest
from unittest.mock import MagicMock, patch
import datetime
import pytz

import scheduled_actions as sa
import types


class TestScheduledDisable(unittest.TestCase):
    def setUp(self):
        self.tz = 'Europe/London'
        self.mock_sophos = MagicMock()
        self.mock_state = MagicMock()
        self.enforcer = sa.ScheduledRuleEnforcer(
            sophos_client=self.mock_sophos,
            state_manager=self.mock_state,
            timezone_str=self.tz,
        )
        self.rule_name = 'Manual Sophie - Allow'

    def _patch_now(self, dt: datetime.datetime):
        class FixedDateTime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return dt
        fake_module = types.SimpleNamespace(datetime=FixedDateTime)
        return patch('scheduled_actions.datetime', fake_module)

    def test_before_time_no_action(self):
        dt = pytz.timezone(self.tz).localize(datetime.datetime(2025, 8, 8, 19, 29, 0))
        with self._patch_now(dt):
            self.mock_state.has_action_run_today.return_value = False
            result = self.enforcer.enforce_daily_disable(self.rule_name, '19:30')
        self.assertFalse(result)
        self.mock_sophos.set_rule_status.assert_not_called()
        self.mock_state.mark_action_run_today.assert_not_called()

    def test_after_time_first_run_disables_and_records(self):
        dt = pytz.timezone(self.tz).localize(datetime.datetime(2025, 8, 8, 19, 35, 0))
        with self._patch_now(dt):
            self.mock_state.has_action_run_today.return_value = False
            self.mock_sophos.set_rule_status.return_value = True
            result = self.enforcer.enforce_daily_disable(self.rule_name, '19:30')
        self.assertTrue(result)
        self.mock_sophos.set_rule_status.assert_called_once_with(self.rule_name, target_enabled_state=False)
        self.mock_state.mark_action_run_today.assert_called_once()

    def test_after_time_already_recorded_noop(self):
        dt = pytz.timezone(self.tz).localize(datetime.datetime(2025, 8, 8, 20, 0, 0))
        with self._patch_now(dt):
            self.mock_state.has_action_run_today.return_value = True
            result = self.enforcer.enforce_daily_disable(self.rule_name, '19:30')
        self.assertFalse(result)
        self.mock_sophos.set_rule_status.assert_not_called()

    def test_after_time_api_failure_does_not_record(self):
        dt = pytz.timezone(self.tz).localize(datetime.datetime(2025, 8, 8, 19, 45, 0))
        with self._patch_now(dt):
            self.mock_state.has_action_run_today.return_value = False
            self.mock_sophos.set_rule_status.return_value = False
            result = self.enforcer.enforce_daily_disable(self.rule_name, '19:30')
        self.assertFalse(result)
        self.mock_state.mark_action_run_today.assert_not_called()

    def test_next_day_runs_again(self):
        tz = pytz.timezone(self.tz)
        dt1 = tz.localize(datetime.datetime(2025, 8, 8, 19, 40, 0))
        dt2 = tz.localize(datetime.datetime(2025, 8, 9, 19, 40, 0))

        # Day 1: run and record
        with self._patch_now(dt1):
            self.mock_state.has_action_run_today.return_value = False
            self.mock_sophos.set_rule_status.return_value = True
            r1 = self.enforcer.enforce_daily_disable(self.rule_name, '19:30')
        self.assertTrue(r1)

        # Day 2: ensure we run again (state mock returns False for new date)
        self.mock_sophos.reset_mock()
        with self._patch_now(dt2):
            self.mock_state.has_action_run_today.return_value = False
            self.mock_sophos.set_rule_status.return_value = True
            r2 = self.enforcer.enforce_daily_disable(self.rule_name, '19:30')
        self.assertTrue(r2)
        self.mock_sophos.set_rule_status.assert_called_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)
