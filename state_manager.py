# File: state_manager.py
"""
Manages the persistence of daily chore completion state using a JSON file.

Handles loading the state at startup, checking completion status for a given child
and date, updating the state in memory, and saving the state back to the file.
"""

import json
import logging
import os
from typing import Dict, Optional

# Initialize logger for this module
logger = logging.getLogger(__name__)

# --- Custom Exceptions ---
class StateManagerError(Exception):
    """Base exception for StateManager specific errors."""
    pass

class StateFileError(StateManagerError):
    """Error related to reading from or writing to the state file."""
    pass

# --- StateManager Class ---
class StateManager:
    """
    Handles loading, accessing, updating, and saving the application's
    daily completion state persisted in a JSON file.
    """
    # Expected structure (example): {"daniel": "2023-10-27", "sophie": "2023-10-26"}
    _state: Dict[str, str]

    def __init__(self, state_file_path: str):
        """
        Initializes the StateManager.

        Args:
            state_file_path: The full path to the JSON file used for persistence.

        Raises:
            ValueError: If state_file_path is empty or invalid.
        """
        if not state_file_path:
            msg = "State file path cannot be empty."
            logger.critical(msg)
            raise ValueError(msg)

        self.state_file_path = state_file_path
        self._state = {} # Initialize with empty state in memory
        logger.info("StateManager initialized with state file path: %s", state_file_path)

    def load_state(self):
        """
        Loads the chore completion state from the JSON file into memory.

        Handles file not found (treats as initial run with empty state) and
        JSON decoding errors (treats as corrupted file, starts with empty state).
        """
        logger.info("Attempting to load state from: %s", self.state_file_path)
        loaded_state: Dict[str, str] = {}
        try:
            with open(self.state_file_path, 'r', encoding='utf-8') as f:
                loaded_state = json.load(f)
            # Basic validation: Ensure it's a dictionary
            if not isinstance(loaded_state, dict):
                 logger.warning("State file content is not a valid dictionary. Resetting to empty state. File: %s", self.state_file_path)
                 loaded_state = {}
            else:
                 # Optional: Add more specific validation if needed (e.g., check keys/value formats)
                 logger.debug("Successfully loaded state data: %s", loaded_state)

        except FileNotFoundError:
            logger.info("State file not found at '%s'. Assuming first run or state reset. Starting with empty state.", self.state_file_path)
            loaded_state = {} # Explicitly ensure it's empty
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON from state file '%s'. File might be corrupted. Starting with empty state.", self.state_file_path, exc_info=True)
            loaded_state = {} # Reset state if file is corrupt
        except (IOError, OSError) as e:
            logger.error("Error reading state file '%s': %s. Starting with empty state.", self.state_file_path, e, exc_info=True)
            loaded_state = {} # Reset state on read error
        except Exception as e:
            logger.exception("Unexpected error loading state file '%s': %s. Starting with empty state.", self.state_file_path, e, exc_info=True)
            loaded_state = {} # Reset state on unexpected error

        self._state = loaded_state
        logger.info("State loading complete. Current in-memory state: %s", self._state)


    def save_state(self):
        """
        Saves the current in-memory state dictionary to the JSON file.

        Overwrites the existing file with the current state. Ensures the JSON
        is pretty-printed for readability.

        Raises:
            StateFileError: If an error occurs during file writing.
        """
        logger.info("Attempting to save state to: %s", self.state_file_path)
        logger.debug("State data to be saved: %s", self._state)
        try:
            # Ensure directory exists before writing
            state_dir = os.path.dirname(self.state_file_path)
            if state_dir and not os.path.exists(state_dir):
                 logger.info("State file directory '%s' does not exist. Attempting to create it.", state_dir)
                 os.makedirs(state_dir, exist_ok=True)

            with open(self.state_file_path, 'w', encoding='utf-8') as f:
                json.dump(self._state, f, indent=4, sort_keys=True) # Pretty print
            logger.info("Successfully saved state to %s", self.state_file_path)

        except (IOError, OSError, TypeError) as e:
             # TypeError could happen if _state is somehow not serializable
            msg = f"Failed to write state file '{self.state_file_path}': {e}"
            logger.error(msg, exc_info=True)
            raise StateFileError(msg) from e
        except Exception as e:
             msg = f"Unexpected error saving state file '{self.state_file_path}': {e}"
             logger.exception(msg, exc_info=True)
             raise StateFileError(msg) from e

    def check_if_done_today(self, child_name: str, today_str: str) -> bool:
        """
        Checks if a child is marked as having completed chores today in the state.

        Args:
            child_name: The name of the child (case-insensitive).
            today_str: The date string for today in 'YYYY-MM-DD' format.

        Returns:
            True if the child's state entry matches today's date string, False otherwise.
        """
        if not child_name or not today_str:
             logger.warning("check_if_done_today called with empty child_name or today_str. Returning False.")
             return False

        normalized_child_name = child_name.lower()
        stored_date = self._state.get(normalized_child_name)

        is_done = stored_date == today_str

        logger.debug("Checking if '%s' is done today ('%s'): Stored='%s', Result=%s",
                     child_name, today_str, stored_date, is_done)
        return is_done

    def mark_done_today(self, child_name: str, today_str: str):
        """
        Updates the in-memory state to mark a child as having completed chores today.

        Note: This only modifies the state in memory. `save_state()` must be
        called separately to persist this change to the file.

        Args:
            child_name: The name of the child (case-insensitive).
            today_str: The date string for today in 'YYYY-MM-DD' format.
        """
        if not child_name or not today_str:
             logger.warning("mark_done_today called with empty child_name or today_str. No state updated.")
             return

        normalized_child_name = child_name.lower()
        logger.info("Marking '%s' as done for today ('%s') in memory. Previous state: '%s'",
                    child_name, today_str, self._state.get(normalized_child_name))
        self._state[normalized_child_name] = today_str
        logger.debug("Current in-memory state after update: %s", self._state)