#!/usr/bin/env python3
"""
Unit tests for time-based logic and bedtime control in main.py
"""

import unittest
import sys
import os
import datetime
import pytz
from unittest.mock import MagicMock, patch

# Add parent directory to path to import main module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main


class TestTimeBedtimeLogic(unittest.TestCase):
    """Test cases for bedtime control and time-based rule logic"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_todoist = MagicMock()
        self.mock_sophos = MagicMock()
        self.mock_sophos.set_rule_status.return_value = True
        self.mock_state_manager = MagicMock()
        
        self.services = {
            'todoist': self.mock_todoist,
            'sophos': self.mock_sophos,
            'state_manager': self.mock_state_manager
        }
        
        self.child_config = {
            "name": "TestChild",
            "todoist_section_id": "123456",
            "sophos_rule_name": "TestChild_Block_Rule"
        }
        
        self.timezone = pytz.timezone('Europe/London')
    
    def _create_time_status(self, hour, minute=0):
        """Helper to create time status dict for testing"""
        mock_now = datetime.datetime(2025, 8, 8, hour, minute, 0, tzinfo=self.timezone)
        return {
            "now": mock_now,
            "today_str": "2025-08-08",
            "current_hour": hour,
            "cutoff_hour": 14,
            "is_after_cutoff": hour >= 14,
        }
    
    def _get_rule_action(self):
        """Helper to extract the rule action from mock calls"""
        if self.mock_sophos.set_rule_status.called:
            call_args = self.mock_sophos.set_rule_status.call_args
            enabled_state = call_args[1].get('target_enabled_state', None)
            return "ENABLE" if enabled_state else "DISABLE"
        return None
    
    def test_bedtime_hours_midnight_to_morning(self):
        """Test that internet is OFF during bedtime hours (00:00-06:59)"""
        test_hours = [0, 3, 6]
        for hour in test_hours:
            with self.subTest(hour=hour):
                self.mock_sophos.reset_mock()
                time_status = self._create_time_status(hour, 30)
                main.process_child(self.child_config, time_status, self.services)
                self.assertEqual(self._get_rule_action(), "ENABLE", 
                               f"Hour {hour}:30 should ENABLE rule (Internet OFF)")
    
    def test_morning_transition_at_7am(self):
        """Test transition from bedtime to morning at 07:00"""
        # Test 06:59 - should be bedtime
        self.mock_sophos.reset_mock()
        time_status = self._create_time_status(6, 59)
        main.process_child(self.child_config, time_status, self.services)
        self.assertEqual(self._get_rule_action(), "ENABLE",
                        "06:59 should still be bedtime (Internet OFF)")
        
        # Test 07:00 - should be morning
        self.mock_sophos.reset_mock()
        time_status = self._create_time_status(7, 0)
        main.process_child(self.child_config, time_status, self.services)
        self.assertEqual(self._get_rule_action(), "DISABLE",
                        "07:00 should be morning (Internet ON)")
    
    def test_morning_hours_free_time(self):
        """Test that internet is ON during morning hours (07:00-13:59)"""
        test_hours = [7, 9, 11, 13]
        for hour in test_hours:
            with self.subTest(hour=hour):
                self.mock_sophos.reset_mock()
                time_status = self._create_time_status(hour, 30)
                main.process_child(self.child_config, time_status, self.services)
                self.assertEqual(self._get_rule_action(), "DISABLE",
                               f"Hour {hour}:30 should DISABLE rule (Internet ON)")
    
    def test_cutoff_transition_at_2pm(self):
        """Test transition from morning to chore-checking at 14:00"""
        # Test 13:59 - should be morning free time
        self.mock_sophos.reset_mock()
        time_status = self._create_time_status(13, 59)
        main.process_child(self.child_config, time_status, self.services)
        self.assertEqual(self._get_rule_action(), "DISABLE",
                        "13:59 should still be morning (Internet ON)")
        
        # Test 14:00 - should check chores
        self.mock_sophos.reset_mock()
        self.mock_todoist.are_child_tasks_incomplete.return_value = True
        self.mock_state_manager.check_if_done_today.return_value = False
        time_status = self._create_time_status(14, 0)
        main.process_child(self.child_config, time_status, self.services)
        self.assertEqual(self._get_rule_action(), "ENABLE",
                        "14:00 with incomplete chores should be Internet OFF")
    
    def test_chore_checking_hours(self):
        """Test chore checking logic during 14:00-19:59"""
        # Test with incomplete chores
        self.mock_sophos.reset_mock()
        self.mock_todoist.are_child_tasks_incomplete.return_value = True
        self.mock_state_manager.check_if_done_today.return_value = False
        time_status = self._create_time_status(16, 0)
        main.process_child(self.child_config, time_status, self.services)
        self.assertEqual(self._get_rule_action(), "ENABLE",
                        "16:00 with incomplete chores should be Internet OFF")
        
        # Test with complete chores
        self.mock_sophos.reset_mock()
        self.mock_todoist.are_child_tasks_incomplete.return_value = False
        self.mock_state_manager.check_if_done_today.return_value = False
        time_status = self._create_time_status(16, 0)
        main.process_child(self.child_config, time_status, self.services)
        self.assertEqual(self._get_rule_action(), "DISABLE",
                        "16:00 with complete chores should be Internet ON")
    
    def test_bedtime_transition_at_8pm(self):
        """Test transition to bedtime at 20:00"""
        # Test 19:59 with complete chores - should be ON
        self.mock_sophos.reset_mock()
        self.mock_state_manager.check_if_done_today.return_value = True
        time_status = self._create_time_status(19, 59)
        main.process_child(self.child_config, time_status, self.services)
        self.assertEqual(self._get_rule_action(), "DISABLE",
                        "19:59 with complete chores should be Internet ON")
        
        # Test 20:00 - should be bedtime regardless of chores
        self.mock_sophos.reset_mock()
        time_status = self._create_time_status(20, 0)
        main.process_child(self.child_config, time_status, self.services)
        self.assertEqual(self._get_rule_action(), "ENABLE",
                        "20:00 should be bedtime (Internet OFF) regardless of chores")
    
    def test_bedtime_overrides_completed_chores(self):
        """Test that bedtime hours override completed chores"""
        # Set up completed chores
        self.mock_todoist.are_child_tasks_incomplete.return_value = False
        self.mock_state_manager.check_if_done_today.return_value = True
        
        # Test at 20:30 - bedtime should override
        self.mock_sophos.reset_mock()
        time_status = self._create_time_status(20, 30)
        main.process_child(self.child_config, time_status, self.services)
        self.assertEqual(self._get_rule_action(), "ENABLE",
                        "Bedtime should override completed chores")
    
    def test_late_night_hours(self):
        """Test that internet is OFF during late night hours (20:00-23:59)"""
        test_hours = [20, 21, 22, 23]
        for hour in test_hours:
            with self.subTest(hour=hour):
                self.mock_sophos.reset_mock()
                time_status = self._create_time_status(hour, 30)
                main.process_child(self.child_config, time_status, self.services)
                self.assertEqual(self._get_rule_action(), "ENABLE",
                               f"Hour {hour}:30 should ENABLE rule (Internet OFF)")


class TestCompleteTimeFlow(unittest.TestCase):
    """Test complete 24-hour flow"""
    
    def test_full_day_cycle(self):
        """Test all critical hours in a 24-hour cycle"""
        mock_sophos = MagicMock()
        mock_sophos.set_rule_status.return_value = True
        
        services = {
            'todoist': MagicMock(),
            'sophos': mock_sophos,
            'state_manager': MagicMock()
        }
        
        child_config = {
            "name": "TestChild",
            "todoist_section_id": "123456",
            "sophos_rule_name": "TestChild_Block_Rule"
        }
        
        timezone = pytz.timezone('Europe/London')
        
        # Define expected behavior for each hour
        hour_expectations = {
            0: "ENABLE",   # Midnight - bedtime
            3: "ENABLE",   # Middle of night - bedtime
            6: "ENABLE",   # Early morning - still bedtime
            7: "DISABLE",  # Morning start
            10: "DISABLE", # Mid-morning
            13: "DISABLE", # Just before cutoff
            14: "ENABLE",  # Cutoff (assuming incomplete chores)
            16: "ENABLE",  # Afternoon (assuming incomplete chores)
            19: "ENABLE",  # Evening (assuming incomplete chores)
            20: "ENABLE",  # Bedtime start
            23: "ENABLE",  # Late night
        }
        
        # Set up mocks for chore checking hours
        services['todoist'].are_child_tasks_incomplete.return_value = True
        services['state_manager'].check_if_done_today.return_value = False
        
        for hour, expected_action in hour_expectations.items():
            with self.subTest(hour=hour):
                mock_sophos.reset_mock()
                
                mock_now = datetime.datetime(2025, 8, 8, hour, 0, 0, tzinfo=timezone)
                time_status = {
                    "now": mock_now,
                    "today_str": "2025-08-08",
                    "current_hour": hour,
                    "cutoff_hour": 14,
                    "is_after_cutoff": hour >= 14,
                }
                
                main.process_child(child_config, time_status, services)
                
                if mock_sophos.set_rule_status.called:
                    enabled_state = mock_sophos.set_rule_status.call_args[1].get('target_enabled_state')
                    actual_action = "ENABLE" if enabled_state else "DISABLE"
                    self.assertEqual(actual_action, expected_action,
                                   f"Hour {hour:02d}:00 expected {expected_action} but got {actual_action}")


if __name__ == '__main__':
    unittest.main(verbosity=2)