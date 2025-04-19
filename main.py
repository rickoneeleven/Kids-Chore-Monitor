# File: main.py
"""
Main application script for Kids Chore Monitor.

Coordinates chore checks against Todoist and (eventually) updates Sophos Firewall rules.
"""

import logging
import sys
import datetime
import pytz
from typing import Tuple, Dict, Any, Optional

# --- Configuration Loading ---
try:
    import config
except ValueError as e:
    print(f"FATAL: Configuration Error - {e}", file=sys.stderr)
    sys.exit(1)
except ImportError:
    print("FATAL: config.py not found or cannot be imported.", file=sys.stderr)
    sys.exit(1)

# --- Service/Client Imports ---
# We place imports inside functions that need them or keep them top-level
# if widely used (like logging, sys, datetime). For clients, importing
# within initialize_services is reasonable.
# from todoist_client import TodoistClient, TodoistClientError, TodoistApiError, TodoistConfigurationError
# from sophos_client import SophosClient, ... # Placeholder
# from state_manager import StateManager, ... # Placeholder


# --- Child Configuration ---
# Structure mapping names to config values for processing loop
# Kept top-level as it's static configuration data used by the main loop.
CHILDREN_CONFIG = [
    {
        "name": "Daniel",
        "todoist_section_id": config.TODOIST_DANIEL_SECTION_ID,
        "sophos_rule_name": config.SOPHOS_DANIEL_RULE_NAME,
    },
    {
        "name": "Sophie",
        "todoist_section_id": config.TODOIST_SOPHIE_SECTION_ID,
        "sophos_rule_name": config.SOPHOS_SOPHIE_RULE_NAME,
    },
]

# --- Logging Setup Function ---
# Encapsulate logger setup.
def setup_logging() -> logging.Logger:
    """Configures and returns the root logger."""
    log_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(module)s.%(funcName)s] - %(message)s'
    )
    logger = logging.getLogger() # Get root logger
    logger.setLevel(logging.INFO) # Set default level for root

    # Clear existing handlers to avoid duplicates if script is re-run in some contexts
    if logger.hasHandlers():
        logger.handlers.clear()

    # Console Handler - Set level based on needs (e.g., DEBUG for dev, INFO for prod)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.DEBUG) # Show detailed logs during development/testing
    logger.addHandler(console_handler)

    # --- Placeholder for File Logging ---
    # file_handler = logging.FileHandler(config.LOG_FILE_PATH)
    # file_handler.setFormatter(log_formatter)
    # file_handler.setLevel(logging.INFO) # Log info and above to file
    # logger.addHandler(file_handler)
    # --- End Placeholder ---

    return logger

# --- Initialization Function ---
def initialize_services() -> Tuple[Optional[Any], Optional[Any], Optional[Any]]:
    """
    Initializes required service clients (Todoist, Sophos, StateManager).

    Returns:
        A tuple containing initialized clients (todoist, sophos, state_manager).
        Returns None for a client if initialization fails.
    """
    # Import clients here to keep scope tight
    from todoist_client import (
        TodoistClient, TodoistConfigurationError, TodoistClientError
    )
    # from sophos_client import SophosClient, SophosConfigurationError, SophosConnectionError # Placeholder
    # from state_manager import StateManager, StateManagerError # Placeholder

    logger = logging.getLogger(__name__) # Use module-specific logger if desired, or root
    todoist_client = None
    # sophos_client = None # Placeholder
    # state_manager = None # Placeholder

    # Initialize Todoist Client
    try:
        logger.debug("Initializing TodoistClient...")
        todoist_client = TodoistClient(
            api_key=config.TODOIST_API_KEY,
            timezone_str=config.TIMEZONE
        )
        logger.info("TodoistClient initialized.")
        # Optional: Add connection test call here if needed for immediate feedback
        # todoist_client._test_connection()
    except (TodoistConfigurationError, RuntimeError, ConnectionError) as e:
        logger.critical("Failed to initialize TodoistClient: %s", e, exc_info=True)
    except Exception as e: # Catch any other unexpected init errors
        logger.critical("Unexpected error initializing TodoistClient: %s", e, exc_info=True)

    # --- Placeholder for Sophos Client Initialization ---
    # try:
    #     logger.debug("Initializing SophosClient...")
    #     sophos_client = SophosClient(
    #         host=config.SOPHOS_HOST,
    #         api_user=config.SOPHOS_API_USER,
    #         api_password=config.SOPHOS_API_PASSWORD
    #     )
    #     logger.info("SophosClient initialized.")
    # except (SophosConfigurationError, SophosConnectionError) as e:
    #     logger.critical("Failed to initialize SophosClient: %s", e, exc_info=True)
    # except Exception as e:
    #     logger.critical("Unexpected error initializing SophosClient: %s", e, exc_info=True)
    # --- End Placeholder ---

    # --- Placeholder for State Manager Initialization ---
    # try:
    #     logger.debug("Initializing StateManager...")
    #     state_manager = StateManager(config.STATE_FILE_PATH)
    #     state_manager.load_state() # Load initial state
    #     logger.info("StateManager initialized and state loaded.")
    # except StateManagerError as e:
    #     logger.critical("Failed to initialize or load state with StateManager: %s", e, exc_info=True)
    # except Exception as e:
    #     logger.critical("Unexpected error initializing StateManager: %s", e, exc_info=True)
    # --- End Placeholder ---


    # Return initialized clients (or None if failed)
    # Adjust tuple elements as clients are implemented
    return todoist_client, None, None # (todoist_client, sophos_client, state_manager)


# --- Time Status Function ---
def get_time_status() -> Dict[str, Any]:
    """
    Determines the current time, cutoff status, and today's date string.

    Returns:
        A dictionary containing: 'now', 'today_str', 'current_hour', 'is_after_cutoff'.

    Raises:
        ValueError: If the timezone configuration is invalid.
        Exception: For other unexpected errors during time calculation.
    """
    logger = logging.getLogger(__name__)
    logger.debug("Determining current time and cutoff status...")
    try:
        timezone = pytz.timezone(config.TIMEZONE)
        now = datetime.datetime.now(timezone)
        today_str = now.strftime('%Y-%m-%d')
        current_hour = now.hour
        cutoff_hour = config.CUTOFF_HOUR # Assumes valid integer from config.py
        is_after_cutoff = current_hour >= cutoff_hour

        time_status = {
            "now": now,
            "today_str": today_str,
            "current_hour": current_hour,
            "cutoff_hour": cutoff_hour,
            "is_after_cutoff": is_after_cutoff,
        }
        logger.info("Current time: %s %s (Hour: %d). Cutoff hour: %d. Is after cutoff: %s",
                    now.strftime('%Y-%m-%d %H:%M:%S'), config.TIMEZONE, current_hour,
                    cutoff_hour, is_after_cutoff)
        return time_status
    except pytz.exceptions.UnknownTimeZoneError as e:
        logger.critical("Invalid timezone configured: %s", config.TIMEZONE, exc_info=True)
        raise ValueError(f"Invalid timezone: {config.TIMEZONE}") from e
    except Exception as e:
        logger.critical("Failed to determine current time or timezone: %s", e, exc_info=True)
        raise # Re-raise unexpected errors


# --- Child Processing Function ---
def process_child(child_config: Dict[str, Any], time_status: Dict[str, Any], services: Dict[str, Any]):
    """
    Processes chore status and determines firewall action for a single child.

    Args:
        child_config: Dictionary containing the child's configuration ('name', 'todoist_section_id', 'sophos_rule_name').
        time_status: Dictionary containing time information from get_time_status().
        services: Dictionary containing initialized service clients ('todoist', 'sophos', 'state_manager').
    """
    logger = logging.getLogger(__name__)
    child_name = child_config["name"]
    section_id = child_config["todoist_section_id"]
    rule_name = child_config["sophos_rule_name"]
    is_after_cutoff = time_status["is_after_cutoff"]
    current_hour = time_status["current_hour"]
    cutoff_hour = time_status["cutoff_hour"]
    today_str = time_status["today_str"] # Needed for state manager later

    todoist_client = services.get('todoist')
    # sophos_client = services.get('sophos') # Placeholder
    # state_manager = services.get('state_manager') # Placeholder

    logger.info("--- Processing Child: %s ---", child_name)

    if not section_id or not rule_name:
        logger.error("Child '%s' is missing required configuration (section ID or rule name). Skipping.", child_name)
        return

    # --- Logic Branch: Before vs After Cutoff ---
    if not is_after_cutoff:
        # Rule: Before cutoff time -> Ensure internet is ON (Rule Disabled)
        intended_action = "DISABLE"
        reason = f"Time ({current_hour}:00) is before cutoff ({cutoff_hour}:00)."
        logger.info("Intended Firewall Action for '%s': %s rule '%s'. Reason: %s",
                    child_name, intended_action, rule_name, reason)
        # Placeholder: sophos_client.set_rule_status(rule_name, enabled=False)
    else:
        # Rule: After cutoff time -> Check chores to determine internet status
        logger.info("Time is on/after cutoff. Checking '%s' chores in Todoist section %s.", child_name, section_id)
        intended_action = "N/A" # Determine below
        reason = "N/A"

        # --- Placeholder: Check state manager first ---
        # if state_manager and state_manager.check_if_done_today(child_name, today_str):
        #     intended_action = "DISABLE"
        #     reason = "Already marked as completed today in state file."
        #     logger.info("Child '%s' already completed chores today. Intended Action: %s rule '%s'. Reason: %s",
        #                 child_name, intended_action, rule_name, reason)
        #     # No Sophos action needed if state matches reality, but log intent
        #     # Placeholder: sophos_client.set_rule_status(rule_name, enabled=False) # Ensure it stays disabled
        #     return # Skip further checks if already done
        # --- End Placeholder ---


        # --- Check Todoist ---
        if not todoist_client:
             logger.error("Todoist client not available for '%s'. Applying fail-safe (ENABLE rule).", child_name)
             intended_action = "ENABLE"
             reason = "Todoist client failed to initialize."
        else:
            # Import specific errors needed here
            from todoist_client import TodoistApiError, TodoistClientError
            try:
                tasks_incomplete = todoist_client.are_child_tasks_incomplete(section_id)
                logger.info("Todoist check result for '%s': Incomplete tasks due today/overdue = %s", child_name, tasks_incomplete)

                if tasks_incomplete:
                    # Rule: Incomplete tasks -> Internet OFF (Rule Enabled)
                    intended_action = "ENABLE"
                    reason = "Incomplete/overdue tasks found in Todoist."
                else:
                    # Rule: All tasks complete -> Internet ON (Rule Disabled)
                    intended_action = "DISABLE"
                    reason = "All tasks due today/overdue are complete in Todoist."
                    # Placeholder: If Sophos action successful: state_manager.mark_done_today(child_name, today_str)

            except TodoistApiError as e:
                # Fail-Safe Rule: API error -> Assume incomplete -> Internet OFF (Rule Enabled)
                intended_action = "ENABLE"
                reason = f"Could not confirm chore status due to Todoist API error after retries: {e}"
                logger.error("Failed to check Todoist status for '%s'. Applying fail-safe. Error: %s", child_name, e, exc_info=False)
            except (TodoistClientError, ValueError) as e:
                # Fail-Safe Rule: Client error -> Assume incomplete -> Internet OFF (Rule Enabled)
                intended_action = "ENABLE"
                reason = f"Could not confirm chore status due to internal client error: {e}"
                logger.error("Failed to check Todoist status for '%s' due to client error. Applying fail-safe.", child_name, exc_info=True)
            except Exception as e:
                # Fail-Safe Rule: Unexpected error -> Assume incomplete -> Internet OFF (Rule Enabled)
                intended_action = "ENABLE"
                reason = f"Could not confirm chore status due to unexpected error: {e}"
                logger.exception("Unexpected error processing child '%s'. Applying fail-safe.", child_name, exc_info=True)

        # --- Log Final Intended Action (After Cutoff) ---
        log_level = logging.WARNING if intended_action == "ENABLE" else logging.INFO
        fail_safe_tag = "(Fail-Safe)" if reason != "Incomplete/overdue tasks found in Todoist." and reason != "All tasks due today/overdue are complete in Todoist." else ""
        logger.log(log_level, "Intended Firewall Action for '%s' %s: %s rule '%s'. Reason: %s",
                   child_name, fail_safe_tag, intended_action, rule_name, reason)

        # --- Placeholder: Call Sophos Client ---
        # if sophos_client and intended_action != "N/A":
        #     target_enabled = (intended_action == "ENABLE")
        #     success = sophos_client.set_rule_status(rule_name, target_enabled_state=target_enabled)
        #     if success and not target_enabled and state_manager: # If rule disabled successfully and tasks were complete
        #           logger.info("Marking child '%s' as done for today (%s) in state.", child_name, today_str)
        #           state_manager.mark_done_today(child_name, today_str)
        # elif not sophos_client:
        #      logger.error("Sophos client not available for '%s'. Cannot apply intended action %s.", child_name, intended_action)
        # --- End Placeholder ---


# --- Main Execution Logic ---
def run_chore_check(logger: logging.Logger):
    """
    Orchestrates the chore check run.
    """
    logger.info("="*20 + " Starting Chore Check Run " + "="*20)

    # --- Initialize Services ---
    # This needs to happen first to ensure logging/clients are ready.
    todoist_client, sophos_client, state_manager = initialize_services()
    services = {
        "todoist": todoist_client,
        "sophos": sophos_client,
        "state_manager": state_manager
    }

    # Exit early if critical services failed (e.g., Todoist essential)
    # Add checks for sophos/state_manager if they become critical failures.
    if not todoist_client:
        logger.critical("Cannot proceed without initialized Todoist Client.")
        logger.info("="*20 + " Chore Check Run Failed (Initialization) " + "="*20)
        return

    # --- Time Check ---
    try:
        time_status = get_time_status()
    except (ValueError, Exception):
        # Error already logged in get_time_status
        logger.info("="*20 + " Chore Check Run Failed (Time Check) " + "="*20)
        return # Cannot proceed without valid time info

    # --- Process Each Child ---
    logger.info("Processing children configurations...")
    for child_config in CHILDREN_CONFIG:
        try:
            process_child(child_config, time_status, services)
        except Exception as e:
            # Catch unexpected errors during a specific child's processing
            child_name = child_config.get("name", "Unknown")
            logger.exception("Unexpected critical error processing child '%s'. Continuing to next child if possible.",
                             child_name, exc_info=True)

    # --- Placeholder: Save State ---
    # if state_manager:
    #     try:
    #         logger.info("Attempting to save application state...")
    #         state_manager.save_state()
    #         logger.info("Application state saved successfully.")
    #     except Exception as e:
    #         logger.error("Failed to save application state.", exc_info=True)
    # --- End Placeholder ---

    logger.info("="*20 + " Chore Check Run Finished " + "="*20)


if __name__ == "__main__":
    # Setup logging ONCE at the start
    logger = setup_logging()
    try:
        # Uncomment to verify loaded config during testing:
        # logger.info("Printing configuration summary (excluding secrets)...")
        # config.print_config_summary() # Assumes config.py has this function

        run_chore_check(logger)

    except Exception as e:
        # Catch truly unexpected errors outside the main run function
        fallback_message = f"CRITICAL UNHANDLED ERROR in __main__: {e}"
        print(fallback_message, file=sys.stderr)
        try:
            # Attempt to log, might fail if logging setup failed
            logger.critical(fallback_message, exc_info=True)
        except NameError:
            pass # logger not defined
        sys.exit(1)