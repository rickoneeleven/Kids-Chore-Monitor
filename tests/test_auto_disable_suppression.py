#!/usr/bin/env python3
"""
Unit tests for per-child auto_disable suppression logic.

Verifies that children configured with auto_disable=False do not have their
firewall rule auto-disabled (Internet ON) either before cutoff or after
cutoff when chores are complete, while still allowing ENABLE actions
for bedtime and incomplete chores after cutoff.
"""

import unittest
import sys
import os
import datetime
import pytz
from unittest.mock import MagicMock

# Add parent directory to path to import main module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main


class TestAutoDisableSuppression(unittest.TestCase):
    def setUp(self):
        self.mock_todoist = MagicMock()
        self.mock_sophos = MagicMock()
        self.mock_sophos.set_rule_status.return_value = True
        self.mock_state_manager = MagicMock()

        self.services = {
            'todoist': self.mock_todoist,
            'sophos': self.mock_sophos,
            'state_manager': self.mock_state_manager,
        }

        self.tz = pytz.timezone('Europe/London')

        # Sophie-like config: auto_disable suppressed
        self.child_suppressed = {
            "name": "Sophie",
            "todoist_section_id": "section_sophie",
            "sophos_rule_name": "Sophie_Block_Rule",
            "auto_disable": False,
        }

        # Daniel-like config: auto_disable allowed
        self.child_allowed = {
            "name": "Daniel",
            "todoist_section_id": "section_daniel",
            "sophos_rule_name": "Daniel_Block_Rule",
            "auto_disable": True,
        }

    def _time_status(self, hour, minute=0, cutoff_hour=14):
        now = datetime.datetime(2025, 8, 8, hour, minute, 0, tzinfo=self.tz)
        return {
            "now": now,
            "today_str": now.strftime('%Y-%m-%d'),
            "current_hour": hour,
            "cutoff_hour": cutoff_hour,
            "is_after_cutoff": hour >= cutoff_hour,
        }

    def test_before_cutoff_disable_is_suppressed(self):
        # Before cutoff, default logic would DISABLE (Internet ON). For auto_disable=False, suppress it.
        self.mock_sophos.reset_mock()
        ts = self._time_status(9, 30)  # Before cutoff
        main.process_child(self.child_suppressed, ts, self.services)
        self.assertFalse(self.mock_sophos.set_rule_status.called,
                         "Expected DISABLE to be suppressed before cutoff for auto_disable=False")

    def test_after_cutoff_complete_tasks_disable_is_suppressed_and_state_not_marked(self):
        self.mock_sophos.reset_mock()
        self.mock_state_manager.reset_mock()
        self.services['todoist'].are_child_tasks_incomplete.return_value = False
        self.services['state_manager'].check_if_done_today.return_value = False

        ts = self._time_status(16, 0)  # After cutoff
        main.process_child(self.child_suppressed, ts, self.services)

        self.assertFalse(self.mock_sophos.set_rule_status.called,
                         "Expected DISABLE to be suppressed after cutoff when chores complete for auto_disable=False")
        self.assertFalse(self.mock_state_manager.mark_done_today.called,
                         "State should not be marked done when DISABLE is suppressed")

    def test_after_cutoff_incomplete_tasks_enables_rule(self):
        self.mock_sophos.reset_mock()
        self.services['todoist'].are_child_tasks_incomplete.return_value = True
        self.services['state_manager'].check_if_done_today.return_value = False

        ts = self._time_status(16, 0)  # After cutoff
        main.process_child(self.child_suppressed, ts, self.services)

        self.assertTrue(self.mock_sophos.set_rule_status.called,
                        "Expected ENABLE to be applied when chores incomplete after cutoff")
        kwargs = self.mock_sophos.set_rule_status.call_args[1]
        self.assertTrue(kwargs.get('target_enabled_state'),
                        "Expected target_enabled_state=True (ENABLE) when chores incomplete")

    def test_bedtime_enables_rule_even_when_suppressed(self):
        self.mock_sophos.reset_mock()
        ts = self._time_status(20, 15)  # Bedtime hours
        main.process_child(self.child_suppressed, ts, self.services)
        self.assertTrue(self.mock_sophos.set_rule_status.called,
                        "Expected ENABLE at bedtime regardless of auto_disable flag")
        kwargs = self.mock_sophos.set_rule_status.call_args[1]
        self.assertTrue(kwargs.get('target_enabled_state'),
                        "Expected target_enabled_state=True (ENABLE) at bedtime")

    def test_default_child_still_disables_before_cutoff(self):
        # Control: For auto_disable=True, before cutoff should DISABLE (Internet ON)
        self.mock_sophos.reset_mock()
        ts = self._time_status(9, 0)
        main.process_child(self.child_allowed, ts, self.services)
        self.assertTrue(self.mock_sophos.set_rule_status.called,
                        "Expected DISABLE before cutoff for auto_disable=True child")
        kwargs = self.mock_sophos.set_rule_status.call_args[1]
        self.assertFalse(kwargs.get('target_enabled_state'),
                         "Expected target_enabled_state=False (DISABLE) before cutoff for auto_disable=True")


if __name__ == '__main__':
    unittest.main(verbosity=2)

