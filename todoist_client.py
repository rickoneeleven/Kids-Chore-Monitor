# File: todoist_client.py
"""
Client module for interacting with the Todoist API.

Handles fetching tasks and determining completion status based on project/section.
"""

import logging
import time
import datetime
import pytz
from todoist_api_python.api import TodoistAPI
# Attempt to import specific exceptions if they exist and are relevant
try:
    # Use official API error if available
    from todoist_api_python.api_error import TodoistAPIError as OfficialTodoistAPIError
    # Also consider requests exceptions for lower-level network issues
    import requests.exceptions
    BASE_API_EXCEPTION = (OfficialTodoistAPIError, requests.exceptions.RequestException)
except ImportError:
    # Fallback if specific exceptions aren't available or names change
    import requests.exceptions
    # Broaden the catch if specific Todoist errors aren't importable
    BASE_API_EXCEPTION = (requests.exceptions.RequestException, Exception)

# Initialize logger for this module
logger = logging.getLogger(__name__)

# --- Constants ---
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5

# --- Custom Exceptions ---
class TodoistClientError(Exception):
    """Custom base exception for errors originating from the TodoistClient."""
    pass

class TodoistApiError(TodoistClientError):
    """Custom exception for persistent Todoist API errors after retries."""
    pass

class TodoistConfigurationError(TodoistClientError):
    """Custom exception for configuration-related errors."""
    pass


class TodoistClient:
    """
    A client for interacting with the Todoist API, focused on chore monitoring needs.
    """

    def __init__(self, api_key: str, timezone_str: str):
        """
        Initializes the TodoistClient.

        Args:
            api_key: The Todoist API key for authentication.
            timezone_str: The pytz-compatible timezone string (e.g., 'Europe/London').

        Raises:
            TodoistConfigurationError: If the API key is not provided or timezone is invalid.
            RuntimeError: If the underlying Todoist API client cannot be initialized.
        """
        if not api_key:
            msg = "Todoist API key is required."
            logger.error(msg)
            raise TodoistConfigurationError(msg)
        self._api_key = api_key

        if not timezone_str:
             msg = "Timezone string is required."
             logger.error(msg)
             raise TodoistConfigurationError(msg)

        try:
            self._timezone = pytz.timezone(timezone_str)
            logger.info("Timezone '%s' loaded successfully.", timezone_str)
        except pytz.exceptions.UnknownTimeZoneError:
            msg = f"Invalid timezone string provided: '{timezone_str}'"
            logger.error(msg)
            raise TodoistConfigurationError(msg)

        try:
            # Initialize the official Todoist API client instance
            self._api = TodoistAPI(api_key)
            logger.info("Todoist API client initialized successfully.")
        except Exception as e:
            logger.exception("Failed to initialize TodoistAPI instance.", exc_info=True)
            raise RuntimeError(f"Could not initialize underlying Todoist API: {e}") from e

    def _test_connection(self):
        """
        Performs a basic API call to verify connectivity and authentication.
        """
        logger.debug("Attempting to test connection to Todoist API...")
        try:
            user = self._api.get_user()
            logger.info("Successfully tested connection to Todoist API. User ID: %s", user.id)
        except BASE_API_EXCEPTION as e:
            logger.error("Failed to connect or authenticate with Todoist API during connection test.", exc_info=True)
            raise ConnectionError(f"Todoist API connection test failed: {e}") from e
        except Exception as e: # Catch any other unexpected errors during the test
             logger.error("An unexpected error occurred during Todoist connection test.", exc_info=True)
             raise ConnectionError(f"Unexpected error during Todoist API connection test: {e}") from e


    def are_child_tasks_incomplete(self, section_id: str) -> bool:
        """
        Checks if a child has incomplete tasks due today or overdue within a specific section.

        Fetches tasks for the given section (handling pagination), filters them for active
        tasks due on or before the current date in the configured timezone. Implements retry
        logic for API calls.

        Args:
            section_id: The ID of the Todoist section to check.

        Returns:
            True if any incomplete tasks due today or earlier are found, False otherwise.

        Raises:
            TodoistApiError: If the Todoist API cannot be reached after multiple retries.
            ValueError: If the provided section_id is invalid (e.g., empty).
            TodoistClientError: For other client-side issues like time determination failures
                                or unexpected processing errors after retries.
        """
        if not section_id:
             logger.error("Invalid section_id provided (empty).")
             raise ValueError("section_id cannot be empty.")

        logger.info("Checking for incomplete tasks in section ID: %s", section_id)
        try:
            today = datetime.datetime.now(self._timezone).date()
            logger.debug("Determined 'today' as: %s (Timezone: %s)", today, self._timezone)
        except Exception as e:
            logger.exception("Failed to determine current date/time for timezone %s", self._timezone, exc_info=True)
            raise TodoistClientError(f"Failed to get current date for timezone {self._timezone}") from e


        for attempt in range(MAX_RETRIES):
            try:
                logger.debug("Attempt %d/%d: Fetching tasks from Todoist API for section %s...",
                             attempt + 1, MAX_RETRIES, section_id)

                # *** FIX: Correctly handle the ResultsPaginator object ***
                tasks_paginator = self._api.get_tasks(section_id=section_id)
                collected_tasks = []

                # Iterate through the paginator to collect all task objects
                # Paginators often yield pages (lists of items).
                if tasks_paginator:
                    for page in tasks_paginator: # Assuming it yields lists (pages)
                        if isinstance(page, list):
                            collected_tasks.extend(page)
                        else:
                             # Log if the paginator yields something unexpected (e.g., single task)
                             # Adjust logic here if the library's paginator behaves differently
                             logger.warning("Paginator yielded non-list item type: %s. Attempting to process as single task.", type(page))
                             if hasattr(page, 'id') and hasattr(page, 'content'): # Basic check for task-like object
                                 collected_tasks.append(page)

                # Now use the collected list
                logger.info("Attempt %d/%d: Successfully fetched %d tasks for section %s after processing paginator.",
                            attempt + 1, MAX_RETRIES, len(collected_tasks), section_id)

                # Filter the collected list for incomplete tasks due today or overdue
                for task in collected_tasks: # Iterate over the fully collected list
                    if task.is_completed:
                        continue

                    # Check if the task has a due date
                    if task.due and task.due.date:
                        try:
                            # Ensure task.due.date is a date object before comparison
                            if isinstance(task.due.date, datetime.date):
                                due_date = task.due.date
                            elif isinstance(task.due.date, str):
                                logger.warning("Task %s due date was a string ('%s'), attempting parse.", task.id, task.due.date)
                                due_date = datetime.datetime.strptime(task.due.date, "%Y-%m-%d").date()
                            else:
                                logger.error("Unexpected type for task.due.date: %s for task ID %s. Skipping task.",
                                             type(task.due.date), task.id)
                                continue

                            # Compare date objects directly (Bugfix from previous step)
                            if due_date <= today:
                                logger.warning("Found incomplete task due on or before today in section %s: "
                                             "Task ID=%s, Name='%s', Due=%s",
                                             section_id, task.id, task.content, task.due.string)
                                return True # Found relevant incomplete task

                        except ValueError as e_parse:
                            logger.error("Could not parse due date string '%s' for task ID %s in section %s during fallback: %s. Skipping check for this task.",
                                         task.due.date, task.id, section_id, e_parse, exc_info=False)
                            continue
                        except Exception as e_date:
                             logger.error("Unexpected error processing due date for task ID %s in section %s: %s. Skipping check for this task.",
                                          task.id, section_id, e_date, exc_info=True)
                             continue

                # If loop completes without finding relevant incomplete tasks
                logger.info("Attempt %d/%d: No incomplete tasks due on or before today found in section %s.",
                            attempt + 1, MAX_RETRIES, section_id)
                return False # Success, no relevant incomplete tasks found

            # --- Error Handling within Retry Loop ---
            except BASE_API_EXCEPTION as e:
                error_type = type(e).__name__
                logger.warning("Attempt %d/%d: API error (%s) during Todoist call for section %s: %s",
                             attempt + 1, MAX_RETRIES, error_type, section_id, e, exc_info=False)
                if attempt + 1 == MAX_RETRIES:
                    logger.error("Maximum retries reached (%d). Failed to get task status for section %s. Last error: %s",
                                  MAX_RETRIES, section_id, e, exc_info=True)
                    raise TodoistApiError(f"Failed to fetch tasks for section {section_id} after {MAX_RETRIES} attempts due to {error_type}.") from e
                else:
                    logger.info("Retrying after %d seconds...", RETRY_DELAY_SECONDS)
                    time.sleep(RETRY_DELAY_SECONDS)
            except Exception as e:
                 # Catch other unexpected errors during processing (e.g., iterating paginator, date handling)
                 error_type = type(e).__name__
                 logger.exception("Attempt %d/%d: Unexpected error (%s) processing tasks for section %s.",
                                attempt + 1, MAX_RETRIES, error_type, section_id, exc_info=True)
                 if attempt + 1 == MAX_RETRIES:
                      logger.critical("Maximum retries reached (%d) after unexpected error (%s) for section %s.", MAX_RETRIES, error_type, section_id)
                      raise TodoistClientError(f"Unexpected error ({error_type}) processing tasks for section {section_id} after {MAX_RETRIES} attempts.") from e
                 else:
                     logger.info("Retrying after %d seconds following unexpected error...", RETRY_DELAY_SECONDS)
                     time.sleep(RETRY_DELAY_SECONDS)

        # This part should theoretically not be reached
        logger.error("Function execution reached end unexpectedly for section %s.", section_id)
        raise TodoistClientError(f"Task check logic completed unexpectedly for section {section_id}.")