# File: main.py (Temporary Test Harness)
"""
Main application script for Kids Chore Monitor.
This version acts as a test harness to verify time logic and Todoist integration.
"""

import logging
import sys
import datetime
import pytz

# --- Configuration Loading ---
try:
    import config
    # Uncomment to verify loaded config during testing:
    # config.print_config_summary()
except ValueError as e:
    # Use basic print since logging might not be configured yet
    print(f"FATAL: Configuration Error - {e}", file=sys.stderr)
    sys.exit(1)
except ImportError:
    print("FATAL: config.py not found or cannot be imported.", file=sys.stderr)
    sys.exit(1)

# --- Service/Client Imports ---
try:
    from todoist_client import TodoistClient, TodoistClientError, TodoistApiError, TodoistConfigurationError
except ImportError:
    print("FATAL: todoist_client.py not found or cannot be imported.", file=sys.stderr)
    sys.exit(1)

# --- Basic Logging Setup (Console for this test) ---
# Final version will configure file logging based on config.LOG_FILE_PATH
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(module)s.%(funcName)s] - %(message)s')
logger = logging.getLogger() # Get root logger
logger.setLevel(logging.INFO) # Set default level

# Console Handler - Set to DEBUG to see detailed logs from clients
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.DEBUG)
logger.addHandler(console_handler)

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

# --- Main Execution Logic ---
def run_chore_check():
    """
    Performs the chore check logic:
    - Determines current time vs cutoff.
    - Checks Todoist status if after cutoff.
    - Logs the intended firewall action based on the rules.
    """
    logger.info("="*20 + " Starting Chore Check Run " + "="*20)

    # --- Initialize Services ---
    try:
        logger.debug("Initializing TodoistClient...")
        todoist = TodoistClient(api_key=config.TODOIST_API_KEY, timezone_str=config.TIMEZONE)
        logger.info("TodoistClient initialized.")
        # Optional: Add connection test call here for immediate feedback if needed
        # todoist._test_connection()
    except (TodoistConfigurationError, RuntimeError, ConnectionError) as e:
        logger.critical("Failed to initialize TodoistClient: %s", e, exc_info=True)
        logger.info("="*20 + " Chore Check Run Failed (Initialization) " + "="*20)
        return # Cannot proceed
    except Exception as e: # Catch any other unexpected init errors
        logger.critical("Unexpected error initializing TodoistClient: %s", e, exc_info=True)
        logger.info("="*20 + " Chore Check Run Failed (Initialization) " + "="*20)
        return

    # --- Time Check ---
    try:
        logger.debug("Determining current time and cutoff status...")
        timezone = pytz.timezone(config.TIMEZONE)
        now = datetime.datetime.now(timezone)
        today_str = now.strftime('%Y-%m-%d') # Useful for state management later
        current_hour = now.hour
        cutoff_hour = config.CUTOFF_HOUR
        is_after_cutoff = current_hour >= cutoff_hour

        logger.info("Current time: %s %s (Hour: %d). Cutoff hour: %d. Is after cutoff: %s",
                    now.strftime('%Y-%m-%d %H:%M:%S'), config.TIMEZONE, current_hour, cutoff_hour, is_after_cutoff)

    except Exception as e:
        logger.critical("Failed to determine current time or timezone: %s", e, exc_info=True)
        logger.info("="*20 + " Chore Check Run Failed (Time Check) " + "="*20)
        return # Cannot proceed

    # --- Process Each Child ---
    logger.info("Processing children configurations...")
    for child in CHILDREN_CONFIG:
        child_name = child["name"]
        section_id = child["todoist_section_id"]
        rule_name = child["sophos_rule_name"] # For logging intent

        logger.info("--- Processing Child: %s ---", child_name)

        if not section_id or not rule_name:
            logger.error("Child '%s' is missing required configuration (section ID or rule name). Skipping.", child_name)
            continue

        if not is_after_cutoff:
            # Rule: Before cutoff time -> Ensure internet is ON (Rule Disabled)
            intended_action = "DISABLE"
            reason = f"Time ({current_hour}:00) is before cutoff ({cutoff_hour}:00)."
            logger.info("Intended Firewall Action for '%s': %s rule '%s'. Reason: %s",
                        child_name, intended_action, rule_name, reason)
            # Placeholder: SophosClient.set_rule_status(rule_name, enabled=False)
        else:
            # Rule: After cutoff time -> Check chores to determine internet status
            logger.info("Time is on/after cutoff. Checking '%s' chores in Todoist section %s.", child_name, section_id)
            intended_action = "N/A" # Determine below
            reason = "N/A"

            try:
                tasks_incomplete = todoist.are_child_tasks_incomplete(section_id)
                logger.info("Todoist check result for '%s': Incomplete tasks due today/overdue = %s", child_name, tasks_incomplete)

                if tasks_incomplete:
                    # Rule: Incomplete tasks -> Internet OFF (Rule Enabled)
                    intended_action = "ENABLE"
                    reason = "Incomplete/overdue tasks found in Todoist."
                    logger.warning("Intended Firewall Action for '%s': %s rule '%s'. Reason: %s",
                                 child_name, intended_action, rule_name, reason)
                    # Placeholder: SophosClient.set_rule_status(rule_name, enabled=True)
                else:
                    # Rule: All tasks complete -> Internet ON (Rule Disabled)
                    intended_action = "DISABLE"
                    reason = "All tasks due today/overdue are complete in Todoist."
                    logger.info("Intended Firewall Action for '%s': %s rule '%s'. Reason: %s",
                                child_name, intended_action, rule_name, reason)
                    # Placeholder: SophosClient.set_rule_status(rule_name, enabled=False)
                    # Placeholder: StateManager.mark_done_today(child_name, today_str)

            except TodoistApiError as e:
                # Fail-Safe Rule: Cannot verify chores -> Assume incomplete -> Internet OFF (Rule Enabled)
                intended_action = "ENABLE"
                reason = f"Could not confirm chore status due to Todoist API error after retries: {e}"
                logger.error("Failed to check Todoist status for '%s'. Applying fail-safe.", child_name, exc_info=False)
                logger.warning("Intended Firewall Action for '%s' (Fail-Safe): %s rule '%s'. Reason: %s",
                             child_name, intended_action, rule_name, reason)
                # Placeholder: SophosClient.set_rule_status(rule_name, enabled=True)

            except (TodoistClientError, ValueError) as e:
                # Fail-Safe Rule: Client error -> Assume incomplete -> Internet OFF (Rule Enabled)
                intended_action = "ENABLE"
                reason = f"Could not confirm chore status due to internal client error: {e}"
                logger.error("Failed to check Todoist status for '%s' due to client error. Applying fail-safe.",
                             child_name, exc_info=True)
                logger.warning("Intended Firewall Action for '%s' (Fail-Safe): %s rule '%s'. Reason: %s",
                             child_name, intended_action, rule_name, reason)
                # Placeholder: SophosClient.set_rule_status(rule_name, enabled=True)

            except Exception as e:
                # Fail-Safe Rule: Unexpected error -> Assume incomplete -> Internet OFF (Rule Enabled)
                intended_action = "ENABLE"
                reason = f"Could not confirm chore status due to unexpected error: {e}"
                logger.exception("Unexpected error processing child '%s'. Applying fail-safe.", child_name, exc_info=True)
                logger.warning("Intended Firewall Action for '%s' (Fail-Safe): %s rule '%s'. Reason: %s",
                             child_name, intended_action, rule_name, reason)
                # Placeholder: SophosClient.set_rule_status(rule_name, enabled=True)

    # Placeholder: StateManager.save_state() if needed
    logger.info("="*20 + " Chore Check Run Finished " + "="*20)


if __name__ == "__main__":
    try:
        run_chore_check()
    except Exception as e:
        # Catch errors outside the main function (e.g., initial setup)
        fallback_message = f"CRITICAL UNHANDLED ERROR in __main__: {e}"
        print(fallback_message, file=sys.stderr)
        try:
            # Attempt to log, might fail if logging setup failed
            logger.critical(fallback_message, exc_info=True)
        except NameError:
            pass # logger not defined
        sys.exit(1)