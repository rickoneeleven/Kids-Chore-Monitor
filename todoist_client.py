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

# --- Custom Exception ---
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
            logger.error("Todoist API key was not provided during client initialization.")
            raise TodoistConfigurationError("Todoist API key is required.")
        self._api_key = api_key

        if not timezone_str:
             logger.error("Timezone string was not provided during client initialization.")
             raise TodoistConfigurationError("Timezone string is required.")

        try:
            self._timezone = pytz.timezone(timezone_str)
            logger.info("Timezone '%s' loaded successfully.", timezone_str)
        except pytz.exceptions.UnknownTimeZoneError:
            logger.error("Invalid timezone string provided: '%s'", timezone_str)
            raise TodoistConfigurationError(f"Invalid timezone string: {timezone_str}")

        try:
            # Initialize the official Todoist API client instance
            self._api = TodoistAPI(api_key)
            logger.info("Todoist API client initialized successfully.")
        except Exception as e:
            logger.exception("Failed to initialize TodoistAPI instance.", exc_info=True)
            raise RuntimeError(f"Could not initialize underlying Todoist API: {e}") from e

    def _test_connection(self):
        """
        Optional: Performs a basic API call to verify connectivity and authentication.
        Not directly used in the main flow but can be called manually if needed.
        """
        try:
            user = self._api.get_user()
            logger.info("Successfully tested connection to Todoist API. User ID: %s", user.id)
        except BASE_API_EXCEPTION as e:
            logger.error("Failed to connect or authenticate with Todoist API during initial test.", exc_info=True)
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
            # Determine 'today' in the configured timezone ONCE before the loop/retries
            today = datetime.datetime.now(self._timezone).date()
            logger.debug("Determined 'today' as: %s (Timezone: %s)", today, self._timezone)
        except Exception as e:
            # Handle potential errors getting current time/date
            logger.exception("Failed to determine current date/time for timezone %s", self._timezone, exc_info=True)
            raise TodoistClientError(f"Failed to get current date for timezone {self._timezone}") from e


        for attempt in range(MAX_RETRIES):
            try:
                logger.debug("Attempt %d/%d: Fetching tasks from Todoist API for section %s...",
                             attempt + 1, MAX_RETRIES, section_id)

                # Fetch the paginator object
                tasks_paginator = self._api.get_tasks(section_id=section_id)

                # --- Iterate through the paginator to collect all tasks ---
                all_tasks = []
                # Paginators often yield pages (lists), so handle that structure.
                # Safely iterate in case it yields something unexpected.
                if tasks_paginator: # Check if paginator itself is not None/empty
                    for page_or_task in tasks_paginator:
                        if isinstance(page_or_task, list):
                            # If it yields lists (pages), extend the main list
                            all_tasks.extend(page_or_task)
                        else:
                            # If it yields individual tasks (less common for REST APIs but possible)
                            # Check if it looks like a task object before adding
                            if hasattr(page_or_task, 'id') and hasattr(page_or_task, 'content'):
                                all_tasks.append(page_or_task)
                            else:
                                logger.warning("Paginator yielded unexpected item type: %s", type(page_or_task))
                # --- End of Paginator Handling ---


                # Now use the collected list 'all_tasks'
                logger.info("Attempt %d/%d: Successfully fetched %d tasks for section %s.",
                            attempt + 1, MAX_RETRIES, len(all_tasks), section_id)

                # Filter the collected list for incomplete tasks due today or overdue
                for task in all_tasks:
                    if task.is_completed:
                        continue

                    if task.due and task.due.date:
                        try:
                            # Todoist due date is 'YYYY-MM-DD' string
                            due_date = datetime.datetime.strptime(task.due.date, "%Y-%m-%d").date()

                            if due_date <= today:
                                logger.warning("Found incomplete task due on or before today in section %s: "
                                             "Task ID=%s, Name='%s', Due=%s",
                                             section_id, task.id, task.content, task.due.string)
                                return True # Found relevant incomplete task

                        except ValueError:
                            logger.error("Could not parse due date string '%s' for task ID %s in section %s. Skipping check for this task.",
                                         task.due.date, task.id, section_id, exc_info=True)
                            continue # Move to the next task


                # If loop completes without finding relevant incomplete tasks
                logger.info("Attempt %d/%d: No incomplete tasks due on or before today found in section %s.",
                            attempt + 1, MAX_RETRIES, section_id)
                return False # Success, no relevant incomplete tasks found

            except BASE_API_EXCEPTION as e:
                # Capture the specific error type for logging
                error_type = type(e).__name__
                logger.warning("Attempt %d/%d: API error (%s) during Todoist call for section %s: %s",
                             attempt + 1, MAX_RETRIES, error_type, section_id, e, exc_info=False) # Keep exc_info False here unless debugging network layer
                if attempt + 1 == MAX_RETRIES:
                    logger.exception("Maximum retries reached (%d). Failed to get task status for section %s. Last error: %s",
                                  MAX_RETRIES, section_id, e, exc_info=True) # Log full trace here
                    raise TodoistApiError(f"Failed to fetch tasks for section {section_id} after {MAX_RETRIES} attempts due to {error_type}.") from e
                else:
                    logger.info("Retrying after %d seconds...", RETRY_DELAY_SECONDS)
                    time.sleep(RETRY_DELAY_SECONDS)
            except Exception as e:
                 # Catch other unexpected errors during processing (like the previous TypeError if paginator handling was wrong)
                 logger.exception("Attempt %d/%d: Unexpected error processing tasks for section %s.",
                                attempt + 1, MAX_RETRIES, section_id, exc_info=True)
                 if attempt + 1 == MAX_RETRIES:
                      logger.critical("Maximum retries reached (%d) after unexpected error for section %s.", MAX_RETRIES, section_id)
                      raise TodoistClientError(f"Unexpected error processing tasks for section {section_id} after {MAX_RETRIES} attempts.") from e
                 else:
                     logger.info("Retrying after %d seconds following unexpected error...", RETRY_DELAY_SECONDS)
                     time.sleep(RETRY_DELAY_SECONDS)

        # Should not be reached due to return/raise within the loop
        logger.error("Reached end of are_child_tasks_incomplete function unexpectedly for section %s.", section_id)
        raise TodoistClientError(f"Task check logic completed unexpectedly for section {section_id}.")