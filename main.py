# File: main.py
"""
Main application script for Kids Chore Monitor.

Coordinates chore checks against Todoist and updates Sophos Firewall rules based
on completion status and time, managing daily state persistence.
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
# Moved specific client imports into initialize_services for tighter scope
# and to handle potential import errors there if modules are missing.
# Import specific exceptions needed for error handling within functions below
try:
    from todoist_client import TodoistApiError, TodoistClientError
except ImportError:
    # Define dummy exceptions if import fails to prevent NameErrors later
    TodoistApiError = TodoistClientError = Exception

try:
    from sophos_client import SophosApiError, SophosConnectionError, SophosRuleNotFoundError
except ImportError:
    # Define dummy exceptions if import fails
    SophosApiError = SophosConnectionError = SophosRuleNotFoundError = Exception

# --- Child Configuration ---
# Structure mapping names to config values for processing loop
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
def setup_logging() -> logging.Logger:
    """Configures and returns the root logger."""
    log_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(module)s.%(funcName)s] - %(message)s'
    )
    logger = logging.getLogger() # Get root logger
    logger.setLevel(logging.INFO) # Default level for root

    if logger.hasHandlers():
        logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.DEBUG) # Show detailed logs during development
    logger.addHandler(console_handler)

    # --- Placeholder for File Logging (Phase 5) ---
    # try:
    #     file_handler = logging.FileHandler(config.LOG_FILE_PATH)
    #     file_handler.setFormatter(log_formatter)
    #     file_handler.setLevel(logging.INFO) # Log info and above to file
    #     logger.addHandler(file_handler)
    # except Exception as e:
    #     logger.error("Failed to configure file logging to %s: %s", config.LOG_FILE_PATH, e, exc_info=True)
    # --- End Placeholder ---

    return logger

# --- Initialization Function ---
def initialize_services() -> Dict[str, Optional[Any]]:
    """
    Initializes required service clients (Todoist, Sophos, StateManager).

    Returns:
        A dictionary containing initialized clients keyed by name
        ('todoist', 'sophos', 'state_manager'). Value is None if initialization failed.
    """
    # Import clients here to keep scope tight and handle import errors gracefully
    try:
        from todoist_client import (
            TodoistClient, TodoistConfigurationError, TodoistClientError, TodoistApiError
        )
    except ImportError:
        logging.critical("Failed to import TodoistClient. Ensure todoist_client.py exists and dependencies are installed.", exc_info=True)
        TodoistClient = None # Define as None to prevent NameError below
        TodoistConfigurationError = TodoistClientError = TodoistApiError = Exception # Dummy exceptions

    try:
        from sophos_client import (
            SophosClient, SophosConfigurationError, SophosConnectionError,
            SophosApiError, SophosRuleNotFoundError
        )
    except ImportError:
        logging.critical("Failed to import SophosClient. Ensure sophos_client.py exists and dependencies are installed.", exc_info=True)
        SophosClient = None
        SophosConfigurationError = SophosConnectionError = SophosApiError = SophosRuleNotFoundError = Exception

    try:
        from state_manager import StateManager, StateFileError, StateManagerError
    except ImportError:
        logging.critical("Failed to import StateManager. Ensure state_manager.py exists.", exc_info=True)
        StateManager = None
        StateFileError = StateManagerError = Exception

    logger = logging.getLogger(__name__) # Use module-specific logger
    services: Dict[str, Optional[Any]] = {
        "todoist": None,
        "sophos": None,
        "state_manager": None
    }

    # Initialize Todoist Client
    if TodoistClient:
        try:
            logger.debug("Initializing TodoistClient...")
            todoist_client = TodoistClient(
                api_key=config.TODOIST_API_KEY,
                timezone_str=config.TIMEZONE
            )
            logger.info("TodoistClient initialized.")
            services["todoist"] = todoist_client
        except (TodoistConfigurationError, RuntimeError, ConnectionError) as e:
            logger.critical("Failed to initialize TodoistClient: %s", e, exc_info=False)
            logger.debug("TodoistClient initialization error details:", exc_info=True)
        except Exception as e:
            logger.critical("Unexpected error initializing TodoistClient: %s", e, exc_info=True)
    else:
        logger.critical("TodoistClient class not available due to import failure.")


    # Initialize Sophos Client
    if SophosClient:
        try:
            logger.debug("Initializing SophosClient...")
            sophos_client = SophosClient(
                host=config.SOPHOS_HOST,
                api_user=config.SOPHOS_API_USER,
                api_password=config.SOPHOS_API_PASSWORD
            )
            logger.info("SophosClient initialized.")
            services["sophos"] = sophos_client
        except (SophosConfigurationError, SophosConnectionError) as e:
            logger.critical("Failed to initialize SophosClient: %s", e, exc_info=False)
            logger.debug("SophosClient initialization error details:", exc_info=True)
        except Exception as e:
            logger.critical("Unexpected error initializing SophosClient: %s", e, exc_info=True)
    else:
        logger.critical("SophosClient class not available due to import failure.")


    # Initialize State Manager
    if StateManager:
        try:
            logger.debug("Initializing StateManager...")
            state_manager = StateManager(config.STATE_FILE_PATH)
            state_manager.load_state() # Load initial state immediately
            logger.info("StateManager initialized and state loaded.")
            services["state_manager"] = state_manager
        except (StateFileError, StateManagerError, ValueError) as e: # Catch init errors too
            logger.critical("Failed to initialize or load state with StateManager: %s", e, exc_info=True)
        except Exception as e:
            logger.critical("Unexpected error initializing StateManager: %s", e, exc_info=True)
    else:
        logger.critical("StateManager class not available due to import failure.")


    return services


# --- Time Status Function ---
def get_time_status() -> Dict[str, Any]:
    """
    Determines the current time, cutoff status, and today's date string.
    """
    logger = logging.getLogger(__name__)
    logger.debug("Determining current time and cutoff status...")
    try:
        timezone = pytz.timezone(config.TIMEZONE)
        now = datetime.datetime.now(timezone)
        today_str = now.strftime('%Y-%m-%d')
        current_hour = now.hour
        cutoff_hour = config.CUTOFF_HOUR
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
        raise


# --- Child Processing Function ---
def process_child(child_config: Dict[str, Any], time_status: Dict[str, Any], services: Dict[str, Any]):
    """
    Determines intended firewall action based on time, state, and chores,
    applies the action via Sophos client, and updates state if needed.
    """
    logger = logging.getLogger(__name__)
    child_name = child_config["name"]
    section_id = child_config["todoist_section_id"]
    rule_name = child_config["sophos_rule_name"]
    is_after_cutoff = time_status["is_after_cutoff"]
    current_hour = time_status["current_hour"]
    cutoff_hour = time_status["cutoff_hour"]
    today_str = time_status["today_str"]

    todoist_client = services.get('todoist')
    sophos_client = services.get('sophos')
    state_manager = services.get('state_manager')

    logger.info("--- Processing Child: %s ---", child_name)

    if not section_id or not rule_name:
        logger.error("Child '%s' is missing required configuration (section ID or rule name). Skipping.", child_name)
        return
    if not sophos_client:
         logger.error("Sophos client is not available for '%s'. Cannot manage firewall rule. Skipping.", child_name)
         return

    # --- Determine Intended Action, Reason, and if State Update is Needed ---
    intended_action = "ENABLE" # Default: Internet OFF (Rule Enabled)
    reason = "Default state before checks"
    should_update_state_on_success = False # Flag to track if state update is needed upon successful DISABLE

    if not is_after_cutoff:
        # Rule: Before cutoff time -> Ensure internet is ON (Rule Disabled)
        intended_action = "DISABLE"
        reason = f"Time ({current_hour}:00) is before cutoff ({cutoff_hour}:00)."
        # State update is NOT needed when disabling before cutoff
    else:
        # Rule: After cutoff time -> Check state, then chores
        logger.info("Time is on/after cutoff for '%s'. Checking state and/or chores.", child_name)

        if state_manager and state_manager.check_if_done_today(child_name, today_str):
            intended_action = "DISABLE"
            reason = f"Already marked as completed today ({today_str}) in state file."
            # State update is NOT needed if already marked done
        else:
            # Not done in state (or state_manager unavailable), proceed to check Todoist
            logger.info("Child '%s' not marked as done today in state. Proceeding to check Todoist.", child_name)

            if not todoist_client:
                 # Fail-Safe: Cannot check chores -> Keep internet OFF (Rule Enabled)
                 reason = "Todoist client not available. Applying fail-safe (ENABLE rule)."
                 # State update not needed
            else:
                # Attempt to check Todoist tasks
                try:
                    tasks_incomplete = todoist_client.are_child_tasks_incomplete(section_id)
                    logger.info("Todoist check result for '%s' (section %s): Incomplete tasks due today/overdue = %s",
                                child_name, section_id, tasks_incomplete)

                    if tasks_incomplete:
                        # Keep internet OFF (Rule Enabled)
                        reason = "Incomplete/overdue tasks found in Todoist."
                        # State update not needed
                    else:
                        # Chores complete! Turn internet ON (Rule Disabled)
                        intended_action = "DISABLE"
                        reason = "All tasks due today/overdue are complete in Todoist."
                        # **** Mark that state update IS needed upon success ****
                        should_update_state_on_success = True

                except TodoistApiError as e:
                    # Fail-Safe on API error -> Keep internet OFF (Rule Enabled)
                    reason = f"Fail-safe due to Todoist API error after retries: {e}"
                    logger.error("Error checking Todoist for '%s': %s", child_name, reason)
                    # State update not needed
                except (TodoistClientError, ValueError) as e:
                     # Fail-Safe on client error -> Keep internet OFF (Rule Enabled)
                    reason = f"Fail-safe due to internal Todoist client error: {e}"
                    logger.error("Error checking Todoist for '%s': %s", child_name, reason)
                    # State update not needed
                except Exception as e:
                    # Fail-Safe on unexpected error -> Keep internet OFF (Rule Enabled)
                    reason = f"Fail-safe due to unexpected error checking Todoist: {e}"
                    logger.exception("Unexpected error during Todoist check for '%s'. Reason: %s", child_name, reason, exc_info=True)
                    # State update not needed


    # Log the final intention before attempting the action
    log_level = logging.WARNING if intended_action == "ENABLE" else logging.INFO
    logger.log(log_level, "Final Intention for '%s': %s rule '%s'. Reason: %s",
               child_name, intended_action, rule_name, reason)

    # --- Apply the Determined Firewall Action ---
    # Pass the reason to apply_firewall_action purely for consolidated logging context there.
    # The decision to update state is handled *after* this call returns.
    action_successful = apply_firewall_action(
        sophos_client=sophos_client,
        child_name=child_name,
        rule_name=rule_name,
        intended_action=intended_action,
        reason_for_action=reason # Pass reason for richer logging within the function
    )

    # --- Update State Manager (Only if Applicable) ---
    # Conditions: Sophos action succeeded, AND the action was DISABLE, AND the reason was chore completion
    if action_successful and intended_action == "DISABLE" and should_update_state_on_success:
        if state_manager:
            logger.info("Marking child '%s' as done for today (%s) in state (post-Sophos action).", child_name, today_str)
            # Perform the state update *only* under these specific conditions
            state_manager.mark_done_today(child_name, today_str)
        else:
             # Log if state manager is missing, even though update was warranted
             logger.warning("StateManager not available. Cannot mark '%s' as done today after successful rule disable for chore completion.", child_name)
    elif action_successful and intended_action == "DISABLE" and not should_update_state_on_success:
         # Log for clarity when rule is disabled but state isn't updated (e.g., before cutoff)
         logger.debug("Rule for '%s' was disabled, but state update was not required (Reason: %s).", child_name, reason)
    elif not action_successful:
         logger.error("Skipping potential state update for '%s' because the Sophos action failed.", child_name)


def apply_firewall_action(
    sophos_client: Any, # Using Any to avoid SophosClient potentially being None type hint issue
    child_name: str,
    rule_name: str,
    intended_action: str, # "ENABLE" or "DISABLE"
    reason_for_action: str # Included for comprehensive logging context
) -> bool:
    """
    Applies the intended firewall rule state using the Sophos client.

    Args:
        sophos_client: The initialized SophosClient instance.
        child_name: Name of the child (for logging).
        rule_name: The exact name of the Sophos firewall rule.
        intended_action: "ENABLE" or "DISABLE".
        reason_for_action: The reason why this action is being taken (for logging).

    Returns:
        True if the action was successfully applied (or rule was already in target state).
        False if the Sophos client is missing or if the API call failed.
    """
    logger = logging.getLogger(__name__)

    if not sophos_client:
         # This check should ideally be done before calling, but double-check
         logger.error("Sophos client not available for '%s'. Cannot apply intended action %s.", child_name, intended_action)
         return False

    target_enabled_state = (intended_action == "ENABLE")
    action_desc = "ENABLE (Internet OFF)" if target_enabled_state else "DISABLE (Internet ON)"

    logger.info("Applying action for '%s': Set rule '%s' to %s. (Triggering Reason: %s)",
                child_name, rule_name, action_desc, reason_for_action)

    try:
        # Call the Sophos client to set the rule status
        success = sophos_client.set_rule_status(rule_name, target_enabled_state=target_enabled_state)

        if success:
            # The client logs success internally if needed, confirm outcome here
            logger.info("Sophos client reported success applying state %s for rule '%s' (%s).",
                        action_desc, rule_name, child_name)
            return True
        else:
            # The client should have logged the specific error (e.g., rule not found, API error)
            logger.error("Sophos client reported failure attempting to set rule '%s' (%s) to state %s. Check previous SophosClient logs for details.",
                         rule_name, child_name, action_desc)
            return False

    # Catch exceptions that might occur *during* the set_rule_status call itself
    except SophosRuleNotFoundError:
         # Should be handled by set_rule_status returning False, but catch defensively
         logger.error("Rule '%s' (%s) was not found during the set operation (exception caught).", rule_name, child_name)
         return False
    except (SophosApiError, SophosConnectionError) as e:
        logger.error("Failed to set rule '%s' (%s) to state %s due to Sophos API/Connection error: %s",
                     rule_name, child_name, action_desc, e, exc_info=False) # Log specific error concisely
        logger.debug("Sophos set_rule_status error details:", exc_info=True) # Full trace at debug
        return False
    except Exception as e:
        # Catch any other unexpected errors during the Sophos interaction
        logger.exception("Unexpected error setting Sophos rule '%s' (%s) state: %s",
                         rule_name, child_name, e, exc_info=True)
        return False


# --- Main Execution Logic ---
def run_chore_check(logger: logging.Logger):
    """
    Orchestrates the chore check run.
    """
    logger.info("="*20 + " Starting Chore Check Run " + "="*20)

    # --- Initialize Services ---
    services = initialize_services()
    todoist_client = services["todoist"]
    sophos_client = services["sophos"]
    state_manager = services["state_manager"]

    # --- Critical Service Checks ---
    critical_services_ok = True
    if not todoist_client:
        logger.critical("Todoist Client failed to initialize. Chore checks will be based on state/time only.")
        # Decide if this is fatal or just degraded functionality
        # critical_services_ok = False # Uncomment if Todoist is essential
    if not sophos_client:
        logger.critical("Sophos Client failed to initialize. Cannot manage firewall rules.")
        critical_services_ok = False # Sophos is essential
    if not state_manager:
        logger.critical("State Manager failed to initialize. Cannot manage completion state.")
        critical_services_ok = False # State manager is essential for correct after-cutoff logic

    if not critical_services_ok:
        logger.error("One or more critical services failed to initialize. Aborting chore check run.")
        logger.info("="*20 + " Chore Check Run Failed (Initialization) " + "="*20)
        return

    # --- Time Check ---
    try:
        time_status = get_time_status()
    except (ValueError, Exception):
        logger.error("Failed to determine time status. Aborting chore check run.")
        logger.info("="*20 + " Chore Check Run Failed (Time Check) " + "="*20)
        return

    # --- Process Each Child ---
    logger.info("Processing children configurations...")
    for child_config in CHILDREN_CONFIG:
        try:
            process_child(child_config, time_status, services)
        except Exception as e:
            # Catch unexpected errors during a specific child's processing
            child_name = child_config.get("name", "Unknown")
            logger.exception("Unexpected critical error processing child '%s'. Continuing to next child.",
                             child_name, exc_info=True)

    # --- Save State ---
    if state_manager:
        try:
            logger.info("Attempting to save application state...")
            state_manager.save_state()
            logger.info("Application state saved successfully.")
        except Exception as e:
            logger.error("Failed to save application state at the end of the run.", exc_info=True)
    else:
        # Should not happen if critical check passed, but log defensively
        logger.warning("StateManager was not available at the end of the run. Cannot save state.")


    logger.info("="*20 + " Chore Check Run Finished " + "="*20)


if __name__ == "__main__":
    logger = setup_logging()
    try:
        # Optional: Print config summary if needed for debugging
        # if hasattr(config, 'print_config_summary'):
        #     logger.info("Printing configuration summary (excluding secrets)...")
        #     config.print_config_summary()

        run_chore_check(logger)

    except Exception as e:
        fallback_message = f"CRITICAL UNHANDLED ERROR in __main__: {e}"
        print(fallback_message, file=sys.stderr)
        try:
            # Use logger if available, otherwise print again
            if 'logger' in locals() and logger:
                logger.critical(fallback_message, exc_info=True)
        except Exception:
            print(f"Logger unavailable: {fallback_message}", file=sys.stderr)
        sys.exit(1)