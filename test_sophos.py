# File: test_sophos.py
"""
Manual test script for verifying SophosClient functionality.

WARNING: Running tests involving set_rule_status WILL modify your firewall rules.
Proceed with caution and ensure you understand the impact.
"""

import logging
import sys

# --- Configuration Loading ---
# Ensure correct path if test_sophos.py is not in the root directory
try:
    import config
    # Optional: Print config summary (excluding secrets)
    # config.print_config_summary()
except ValueError as e:
    print(f"FATAL: Configuration Error - {e}", file=sys.stderr)
    sys.exit(1)
except ImportError:
    print("FATAL: config.py not found or cannot be imported.", file=sys.stderr)
    sys.exit(1)

# --- Client Import ---
# This will fail until sophos_client.py is created
try:
    from sophos_client import (
        SophosClient, SophosClientError, SophosApiError,
        SophosConfigurationError, SophosRuleNotFoundError
    )
except ImportError:
    print("FATAL: sophos_client.py not found or cannot be imported.", file=sys.stderr)
    print("Please implement the SophosClient first.")
    sys.exit(1)


# --- Basic Logging Setup (Console) ---
# Replicate or simplify logging setup from main.py for test output
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(module)s.%(funcName)s] - %(message)s')
logger = logging.getLogger("SophosTest")
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)


def run_sophos_tests():
    """Executes a series of tests against the SophosClient."""
    logger.info("--- Starting SophosClient Manual Tests ---")

    # --- Initialization ---
    sophos_client: SophosClient | None = None
    try:
        logger.info("Initializing SophosClient...")
        sophos_client = SophosClient(
            host=config.SOPHOS_HOST,
            api_user=config.SOPHOS_API_USER,
            api_password=config.SOPHOS_API_PASSWORD
        )
        logger.info("SophosClient initialized successfully.")
        # Optional: Call internal connection test if implemented
        # logger.info("Testing connection...")
        # sophos_client._test_connection() # Assuming this method exists and raises on error
        # logger.info("Connection test successful.")

    except SophosConfigurationError as e:
        logger.critical("Configuration error during SophosClient initialization: %s", e)
        sys.exit(1)
    except SophosClientError as e: # Catch connection/auth errors from init
        logger.critical("Failed to initialize SophosClient: %s", e, exc_info=True)
        sys.exit(1)
    except Exception as e:
        logger.critical("Unexpected error during SophosClient initialization: %s", e, exc_info=True)
        sys.exit(1)

    # --- Test get_rule_status ---
    rule_names_to_test = [
        config.SOPHOS_DANIEL_RULE_NAME,
        config.SOPHOS_SOPHIE_RULE_NAME,
        "NonExistentRuleNameToTestNotFound" # Add a fake name
    ]

    logger.info("\n--- Testing get_rule_status ---")
    for rule_name in rule_names_to_test:
        if not rule_name:
            logger.warning("Skipping test for empty rule name in config.")
            continue
        try:
            logger.debug("Querying status for rule: '%s'", rule_name)
            status = sophos_client.get_rule_status(rule_name)
            if status is None:
                # This case depends on get_rule_status implementation choice
                logger.info("Rule '%s': Status could not be determined (check client logic if rule exists).", rule_name)
            elif status is True:
                logger.info("Rule '%s': Found - Status: Enabled", rule_name)
            else: # status is False
                logger.info("Rule '%s': Found - Status: Disabled", rule_name)

        except SophosRuleNotFoundError:
            logger.warning("Rule '%s': Not Found (as expected for test or indicates config issue).", rule_name)
        except SophosApiError as e:
            logger.error("Rule '%s': Failed to get status due to API error: %s", rule_name, e)
        except Exception as e:
            logger.exception("Rule '%s': Unexpected error during get_rule_status: %s", rule_name, e)


    # --- Test set_rule_status (Use with EXTREME CAUTION) ---
    logger.info("\n--- Testing set_rule_status (Idempotency & Optional Change) ---")
    logger.warning("!!! WARNING: set_rule_status tests can modify firewall state !!!")

    # Example: Test idempotency for Daniel's rule (set to current state)
    rule_to_modify = config.SOPHOS_DANIEL_RULE_NAME
    if rule_to_modify:
        try:
            current_status = sophos_client.get_rule_status(rule_to_modify)
            if current_status is not None:
                logger.info("Attempting idempotency test for rule '%s' (setting to current state: %s)",
                            rule_to_modify, "Enabled" if current_status else "Disabled")
                success = sophos_client.set_rule_status(rule_to_modify, target_enabled_state=current_status)
                if success:
                    logger.info("Idempotency test for rule '%s' successful (or no change needed).", rule_to_modify)
                else:
                    logger.error("Idempotency test for rule '%s' failed.", rule_to_modify)
            else:
                 logger.warning("Cannot perform idempotency test for rule '%s' as current status is unknown.", rule_to_modify)

        except SophosRuleNotFoundError:
             logger.error("Cannot perform set_rule_status test: Rule '%s' not found.", rule_to_modify)
        except SophosApiError as e:
             logger.error("API error during set_rule_status test for '%s': %s", rule_to_modify, e)
        except Exception as e:
             logger.exception("Unexpected error during set_rule_status test for '%s': %s", rule_to_modify, e)
    else:
        logger.warning("Skipping set_rule_status test as Daniel's rule name is not configured.")


    # --- Optional: Test Actual State Change (Commented Out By Default) ---
    # logger.info("\n--- Optional: Testing Actual State Change ---")
    # enable_state_change_test = False # <<<< SET TO TRUE ONLY IF YOU WANT TO MODIFY RULES >>>>
    #
    # if enable_state_change_test and rule_to_modify:
    #     try:
    #         initial_status = sophos_client.get_rule_status(rule_to_modify)
    #         if initial_status is not None:
    #             target_state = not initial_status # Flip the state
    #             logger.warning("Attempting to change rule '%s' state to: %s", rule_to_modify, "Enabled" if target_state else "Disabled")
    #             success_change = sophos_client.set_rule_status(rule_to_modify, target_enabled_state=target_state)
    #
    #             if success_change:
    #                 logger.info("Successfully changed rule '%s' state to %s.", rule_to_modify, "Enabled" if target_state else "Disabled")
    #                 # Verify change (optional but recommended)
    #                 time.sleep(2) # Give API time to settle if needed
    #                 new_status = sophos_client.get_rule_status(rule_to_modify)
    #                 logger.info("Verification: Rule '%s' current status: %s", rule_to_modify, "Enabled" if new_status else "Disabled")
    #
    #                 # Change it back
    #                 logger.warning("Attempting to revert rule '%s' state to: %s", rule_to_modify, "Enabled" if initial_status else "Disabled")
    #                 success_revert = sophos_client.set_rule_status(rule_to_modify, target_enabled_state=initial_status)
    #                 if success_revert:
    #                      logger.info("Successfully reverted rule '%s' state.", rule_to_modify)
    #                 else:
    #                      logger.error("!!! FAILED TO REVERT rule '%s' state. MANUAL INTERVENTION MAY BE NEEDED !!!", rule_to_modify)
    #             else:
    #                 logger.error("Failed to change rule '%s' state.", rule_to_modify)
    #         else:
    #             logger.error("Cannot perform state change test for rule '%s' as initial state is unknown.", rule_to_modify)
    #
    #     except SophosRuleNotFoundError:
    #          logger.error("Cannot perform state change test: Rule '%s' not found.", rule_to_modify)
    #     except SophosApiError as e:
    #          logger.error("API error during state change test for '%s': %s", rule_to_modify, e)
    #     except Exception as e:
    #          logger.exception("Unexpected error during state change test for '%s': %s", rule_to_modify, e)
    # else:
    #      logger.info("Actual state change test is disabled or rule name is missing.")

    logger.info("\n--- SophosClient Manual Tests Finished ---")


if __name__ == "__main__":
    # Basic check for essential config needed by the test script itself
    if not config.SOPHOS_HOST or not config.SOPHOS_API_USER or not config.SOPHOS_API_PASSWORD:
         logger.critical("Essential Sophos connection details (HOST, API_USER, API_PASSWORD) missing in config.")
         sys.exit(1)
    # Rule names aren't strictly needed to run *some* tests, but the core tests depend on them.

    run_sophos_tests()