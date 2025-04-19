# File: test_sophos.py
"""
Manual test script for SophosClient.

Verifies connection, rule status retrieval, and **ALWAYS** attempts to
toggle the status of specified rules (Daniel's and Sophie's) and leaves them toggled.

!! WARNING !!
************************************************************************
* THIS SCRIPT WILL MODIFY YOUR FIREWALL CONFIGURATION EVERY TIME IT RUNS *
* by toggling the status of the specified rules. Use with extreme      *
* caution. Verify the final rule states manually after running.        *
************************************************************************
"""

import logging
import sys
import time
from typing import Optional, Dict # Added Dict

# --- Configuration Loading ---
try:
    import config # Load configuration from .env
except ValueError as e:
    print(f"FATAL: Configuration Error - {e}", file=sys.stderr)
    sys.exit(1)
except ImportError:
    print("FATAL: config.py not found. Ensure it exists and .env is populated.", file=sys.stderr)
    sys.exit(1)

# --- Import the Client and Exceptions ---
try:
    from sophos_client import (
        SophosClient,
        SophosConfigurationError,
        SophosConnectionError,
        SophosApiError,
        SophosRuleNotFoundError
    )
except ImportError:
     print("FATAL: sophos_client.py not found or cannot be imported.", file=sys.stderr)
     sys.exit(1)

# --- Basic Logging Setup for the Test Script ---
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SophosTest')
logger.setLevel(logging.INFO) # Set to DEBUG for more client details

# Console Handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)

# Prevent adding handler multiple times if script is re-run in interactive mode
if not logger.hasHandlers():
    logger.addHandler(console_handler)


# --- Main Test Function ---
def run_tests():
    """Executes the SophosClient tests, including rule status toggle."""
    logger.warning("--- Starting Sophos Client Test ---")
    logger.warning("Ensure your .env file is correctly configured with Sophos details.")

    sophos_client: Optional[SophosClient] = None

    # --- 1. Initialize Client ---
    try:
        logger.info("Attempting to initialize SophosClient...")
        sophos_client = SophosClient(
            host=config.SOPHOS_HOST,
            api_user=config.SOPHOS_API_USER,
            api_password=config.SOPHOS_API_PASSWORD,
        )
        logger.info("SophosClient initialized successfully.")
    except (SophosConfigurationError, SophosConnectionError) as e:
        logger.critical("Failed to initialize SophosClient: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.critical("Unexpected error during SophosClient initialization: %s", e, exc_info=True)
        sys.exit(1)

    # --- Rules to Process ---
    rules_to_process: Dict[str, Dict[str, Optional[bool]]] = {
        "Daniel": {"name": config.SOPHOS_DANIEL_RULE_NAME, "original_status": None, "target_status": None},
        "Sophie": {"name": config.SOPHOS_SOPHIE_RULE_NAME, "original_status": None, "target_status": None},
    }

    # --- 2. Get Initial Statuses ---
    logger.info("\n--- Getting Initial Rule Statuses ---")
    found_all_rules = True
    for child, data in rules_to_process.items():
        rule_name = data["name"]
        if not rule_name:
            logger.error("Rule name for '%s' is not configured in .env. Cannot process this rule.", child)
            found_all_rules = False # Mark that we can't process everything
            continue
        try:
            status = sophos_client.get_rule_status(rule_name)
            data["original_status"] = status
            if status is None:
                logger.info("Rule '%s' (%s): Found - Status is ambiguous.", rule_name, child)
                found_all_rules = False # Treat ambiguous as unable to process reliably
            elif status:
                logger.info("Rule '%s' (%s): Found - Status: Enabled", rule_name, child)
                data["target_status"] = False # Target is opposite
            else:
                logger.info("Rule '%s' (%s): Found - Status: Disabled", rule_name, child)
                data["target_status"] = True # Target is opposite
        except SophosRuleNotFoundError:
            logger.warning("Rule '%s' (%s): Not Found.", rule_name, child)
            found_all_rules = False
        except (SophosApiError, SophosConnectionError) as e:
            logger.error("Rule '%s' (%s): Failed to get status - %s", rule_name, child, e)
            found_all_rules = False
        except Exception as e:
            logger.error("Rule '%s' (%s): Unexpected error during get_rule_status - %s", rule_name, child, e, exc_info=True)
            found_all_rules = False

    # --- 3. Attempt to Toggle Rule Statuses ---
    logger.warning("\n" + "="*60)
    logger.warning("!! CAUTION: Preparing to MODIFY Firewall Rule Statuses !!")
    logger.warning("Script will attempt to toggle the state of configured rules.")
    logger.warning("The original states WILL NOT be restored automatically.")
    logger.warning("Verify the final states manually in the firewall GUI.")

    if not found_all_rules:
         logger.error("One or more rules were not found or status could not be determined.")
         logger.error("Skipping modification attempts. Please check configuration and firewall.")
         logger.warning("--- Sophos Client Test Finished (Modification Skipped) ---")
         sys.exit(1)

    logger.warning("Proceeding with modifications in 5 seconds...")
    logger.warning("="*60)
    time.sleep(5)

    logger.info("\n--- Setting Rules to Opposite States ---")
    all_toggles_successful = True
    for child, data in rules_to_process.items():
         rule_name = data["name"]
         original_status_bool = data["original_status"]
         target_status_bool = data["target_status"]
         target_status_str = "Enabled" if target_status_bool else "Disabled"

         # Double-check we have valid data before proceeding
         if rule_name is None or original_status_bool is None or target_status_bool is None:
             logger.error("Skipping modification for '%s' due to missing name or status info.", child)
             all_toggles_successful = False
             continue

         logger.info("Attempting to set rule '%s' (%s) to target state: %s", rule_name, child, target_status_str)
         try:
             success = sophos_client.set_rule_status(rule_name, target_enabled_state=target_status_bool)
             if success:
                 logger.info(" ---> Rule '%s' (%s) status set to %s successfully.", rule_name, child, target_status_str)
             else:
                 logger.error(" ---> FAILED to set rule '%s' (%s) status to %s.", rule_name, child, target_status_str)
                 all_toggles_successful = False

         except (SophosApiError, SophosConnectionError) as e:
            logger.error(" ---> FAILED to set rule '%s' (%s) due to API/Connection error: %s", rule_name, child, e)
            all_toggles_successful = False
         except Exception as e:
            logger.error(" ---> FAILED to set rule '%s' (%s) due to unexpected error: %s", rule_name, child, e, exc_info=True)
            all_toggles_successful = False


    # --- Final Report ---
    logger.warning("\n--- Modifications Attempted ---")
    if all_toggles_successful:
        logger.info("All rule toggles attempted successfully according to API responses.")
    else:
        logger.error("One or more rule toggle attempts failed. Check logs above.")
    logger.warning("!! Please verify the final status of the rules in the Sophos GUI. !!")
    logger.warning("--- Sophos Client Test Finished ---")


# --- Script Execution ---
if __name__ == "__main__":
    try:
        run_tests()
    except Exception as e:
        # Catch-all for any unexpected error during test execution
        logger.critical("An critical unhandled error occurred during the test run: %s", e, exc_info=True)
        sys.exit(1)