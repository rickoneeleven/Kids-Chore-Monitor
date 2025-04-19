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
            # Optional: todoist_client._test_connection() # Consider if needed
        except (TodoistConfigurationError, RuntimeError, ConnectionError) as e:
            logger.critical("Failed to initialize TodoistClient: %s", e, exc_info=False) # Log concise critical error
            logger.debug("TodoistClient initialization error details:", exc_info=True) # Log full trace at debug level
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
                # Add port=, verify_ssl= if needed from config
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
    (No changes needed for Phase 4 integration)
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
        raise


# --- Child Processing Function ---
def process_child(child_config: Dict[str, Any], time_status: Dict[str, Any], services: Dict[str, Any]):
    """
    Processes chore status and determines/applies firewall action for a single child.
    """
    logger = logging.getLogger(__name__)
    child_name = child_config["name"]
    section_id = child_config["todoist_section_id"]
    rule_name = child_config["sophos_rule_name"]
    is_after_cutoff = time_status["is_after_cutoff"]
    current_hour = time_status["current_hour"]
    cutoff_hour = time_status["cutoff_hour"]
    today_str = time_status["today_str"]

    # Retrieve clients from services dictionary
    todoist_client = services.get('todoist')
    sophos_client = services.get('sophos') # May be None if init failed
    state_manager = services.get('state_manager') # May be None if init failed

    logger.info("--- Processing Child: %s ---", child_name)

    if not section_id or not rule_name:
        logger.error("Child '%s' is missing required configuration (section ID or rule name). Skipping.", child_name)
        return
    if not sophos_client:
         logger.error("Sophos client is not available for '%s'. Cannot manage firewall rule. Skipping.", child_name)
         return # Cannot proceed without Sophos client

    # --- Default Assumption: Firewall rule should be ENABLED (Internet OFF) ---
    # This is the fail-safe state if checks cannot be completed.
    intended_action = "ENABLE" # ENABLE = Internet OFF
    reason = "Default state before checks"

    # --- Logic Branch: Before vs After Cutoff ---
    if not is_after_cutoff:
        # Rule: Before cutoff time -> Ensure internet is ON (Rule Disabled)
        intended_action = "DISABLE"
        reason = f"Time ({current_hour}:00) is before cutoff ({cutoff_hour}:00)."
        logger.info("Intention for '%s': %s rule '%s'. Reason: %s",
                    child_name, intended_action, rule_name, reason)
    else:
        # Rule: After cutoff time -> Check state, then chores
        logger.info("Time is on/after cutoff for '%s'. Checking state and/or chores.", child_name)

        # Check state manager first
        if state_manager:
            if state_manager.check_if_done_today(child_name, today_str):
                intended_action = "DISABLE"
                reason = f"Already marked as completed today ({today_str}) in state file."
                logger.info("Intention for '%s': %s rule '%s'. Reason: %s",
                            child_name, intended_action, rule_name, reason)
                # Skip Todoist check if already marked done
                apply_firewall_action(sophos_client, child_name, rule_name, intended_action, reason, state_manager, today_str)
                return # Finished processing this child
            else:
                 logger.info("Child '%s' not marked as done today in state. Proceeding to check Todoist.", child_name)
        else:
             logger.warning("StateManager not available for '%s'. Cannot check/update completion state. Proceeding to check Todoist.", child_name)


        # --- Check Todoist ---
        if not todoist_client:
             # Fail-Safe: Cannot check chores -> Keep internet OFF
             intended_action = "ENABLE"
             reason = "Todoist client not available. Applying fail-safe (ENABLE rule)."
             logger.error("Intention for '%s': %s rule '%s'. Reason: %s", child_name, intended_action, rule_name, reason)
        else:
            # Import specific errors needed here - already imported at top level now
            from todoist_client import TodoistApiError, TodoistClientError # Keep for clarity maybe
            try:
                tasks_incomplete = todoist_client.are_child_tasks_incomplete(section_id)
                logger.info("Todoist check result for '%s' (section %s): Incomplete tasks due today/overdue = %s",
                            child_name, section_id, tasks_incomplete)

                if tasks_incomplete:
                    intended_action = "ENABLE"
                    reason = "Incomplete/overdue tasks found in Todoist."
                else:
                    intended_action = "DISABLE"
                    reason = "All tasks due today/overdue are complete in Todoist."

                log_level = logging.WARNING if intended_action == "ENABLE" else logging.INFO
                logger.log(log_level, "Intention for '%s': %s rule '%s'. Reason: %s",
                           child_name, intended_action, rule_name, reason)

            except TodoistApiError as e:
                intended_action = "ENABLE"
                reason = f"Fail-safe due to Todoist API error after retries: {e}"
                logger.error("Intention for '%s': %s rule '%s'. Reason: %s", child_name, intended_action, rule_name, reason)
            except (TodoistClientError, ValueError) as e:
                intended_action = "ENABLE"
                reason = f"Fail-safe due to internal Todoist client error: {e}"
                logger.error("Intention for '%s': %s rule '%s'. Reason: %s", child_name, intended_action, rule_name, reason)
            except Exception as e:
                intended_action = "ENABLE"
                reason = f"Fail-safe due to unexpected error checking Todoist: {e}"
                logger.exception("Intention for '%s': %s rule '%s'. Reason: %s", child_name, intended_action, rule_name, reason, exc_info=True)


    # --- Apply the Determined Firewall Action ---
    # This section is reached if not returned early (e.g., from state check)
    apply_firewall_action(sophos_client, child_name, rule_name, intended_action, reason, state_manager, today_str)


def apply_firewall_action(
    sophos_client: Any, # Using Any to avoid SophosClient potentially being None type hint issue
    child_name: str,
    rule_name: str,
    intended_action: str, # "ENABLE" or "DISABLE"
    reason: str,
    state_manager: Any, # Using Any to avoid StateManager potentially being None type hint issue
    today_str: str
):
    """
    Applies the intended firewall rule state and updates state manager if needed.
    """
    logger = logging.getLogger(__name__)

    if not sophos_client:
         logger.error("Sophos client not available for '%s'. Cannot apply intended action %s.", child_name, intended_action)
         return # Should have been caught earlier, but double-check

    target_enabled_state = (intended_action == "ENABLE")
    action_desc = "ENABLE (Internet OFF)" if target_enabled_state else "DISABLE (Internet ON)"

    logger.info("Applying final decision for '%s': Set rule '%s' to %s. Reason: %s",
                child_name, rule_name, action_desc, reason)

    try:
        # Import specific Sophos errors here if needed for finer-grained handling,
        # otherwise rely on base exceptions caught.
        from sophos_client import SophosApiError, SophosConnectionError, SophosRuleNotFoundError

        success = sophos_client.set_rule_status(rule_name, target_enabled_state=target_enabled_state)

        if success:
            logger.info("Successfully applied state %s for rule '%s' (%s).",
                        action_desc, rule_name, child_name)
            # If we successfully DISABLED the rule (Internet ON) because chores are done...
            if not target_enabled_state:
                if state_manager:
                    # ...mark the child as done for today in the state manager.
                    logger.info("Marking child '%s' as done for today (%s) in state.", child_name, today_str)
                    state_manager.mark_done_today(child_name, today_str)
                    # State will be saved later by run_chore_check
                else:
                     logger.warning("StateManager not available. Cannot mark '%s' as done today after disabling rule.", child_name)
        else:
            # set_rule_status returning False usually means rule not found or API error logged within the client
            logger.error("Sophos client reported failure attempting to set rule '%s' (%s) to state %s. Check previous logs.",
                         rule_name, child_name, action_desc)

    except SophosRuleNotFoundError:
         # This shouldn't happen if set_rule_status handles it, but catch defensively
         logger.error("Rule '%s' (%s) was not found during the set operation.", rule_name, child_name)
    except (SophosApiError, SophosConnectionError) as e:
        logger.error("Failed to set rule '%s' (%s) to state %s due to Sophos API/Connection error: %s",
                     rule_name, child_name, action_desc, e, exc_info=False) # Log specific error concisely
        logger.debug("Sophos set_rule_status error details:", exc_info=True) # Full trace at debug
    except Exception as e:
        logger.exception("Unexpected error setting Sophos rule '%s' (%s) state: %s",
                         rule_name, child_name, e, exc_info=True)


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
    # Decide which services are absolutely essential for a run to even attempt processing
    # For now, assume all three are required for full functionality.
    critical_services_ok = True
    if not todoist_client:
        logger.critical("Todoist Client failed to initialize. Cannot check chores.")
        critical_services_ok = False
    if not sophos_client:
        logger.critical("Sophos Client failed to initialize. Cannot manage firewall rules.")
        critical_services_ok = False
    if not state_manager:
        logger.critical("State Manager failed to initialize. Cannot manage completion state.")
        critical_services_ok = False

    if not critical_services_ok:
        logger.error("One or more critical services failed to initialize. Aborting chore check run.")
        logger.info("="*20 + " Chore Check Run Failed (Initialization) " + "="*20)
        return

    # --- Time Check ---
    try:
        time_status = get_time_status()
    except (ValueError, Exception):
        # Error already logged in get_time_status
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
            # Error already logged by save_state, but log context here too
            logger.error("Failed to save application state at the end of the run.", exc_info=True)
    else:
        # Should not happen if critical check passed, but log defensively
        logger.warning("StateManager was not available at the end of the run. Cannot save state.")


    logger.info("="*20 + " Chore Check Run Finished " + "="*20)


if __name__ == "__main__":
    logger = setup_logging()
    try:
        # logger.info("Printing configuration summary (excluding secrets)...")
        # config.print_config_summary() # Assumes config.py has this function

        run_chore_check(logger)

    except Exception as e:
        fallback_message = f"CRITICAL UNHANDLED ERROR in __main__: {e}"
        print(fallback_message, file=sys.stderr)
        try:
            logger.critical(fallback_message, exc_info=True)
        except NameError:
            pass # logger might not be defined if setup_logging failed catastrophically
        sys.exit(1)