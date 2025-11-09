"""
Configuration Module

Loads application configuration and secrets from environment variables
(typically via a .env file) and validates required settings.
"""

import os
from dotenv import load_dotenv

# Load environment variables from a .env file if it exists
# This should be called early, before accessing os.getenv below.
# It safely handles the case where .env doesn't exist.
load_dotenv()

# --- Core Secrets & Connection Details ---
TODOIST_API_KEY = os.getenv("TODOIST_API_KEY")  # Required: Your Todoist API key obtained from Todoist settings.
SOPHOS_HOST = os.getenv("SOPHOS_HOST")          # Required: Hostname or IP address of your Sophos Firewall web admin interface.
SOPHOS_API_USER = os.getenv("SOPHOS_API_USER")  # Required: Username created on Sophos Firewall with API access permissions.
SOPHOS_API_PASSWORD = os.getenv("SOPHOS_API_PASSWORD") # Required: Password for the Sophos API user.

# --- Todoist Configuration ---
# Optional: ID of the parent "Kids Chores" project. Filtering by section is primary,
# but this could be used for additional validation if needed later.
TODOIST_KIDS_PROJECT_ID = os.getenv("TODOIST_KIDS_PROJECT_ID")
# Required: The numeric Section ID from Todoist for Daniel's chores.
# Find this in the URL when viewing the section in Todoist web.
TODOIST_DANIEL_SECTION_ID = os.getenv("TODOIST_DANIEL_SECTION_ID")
# Required: The numeric Section ID from Todoist for Sophie's chores.
TODOIST_SOPHIE_SECTION_ID = os.getenv("TODOIST_SOPHIE_SECTION_ID")

# --- Sophos Configuration ---
# Required: The exact name of the Sophos Firewall rule controlling Daniel's internet access.
SOPHOS_DANIEL_RULE_NAME = os.getenv("SOPHOS_DANIEL_RULE_NAME")
# Required: The exact name of the Sophos Firewall rule controlling Sophie's internet access.
SOPHOS_SOPHIE_RULE_NAME = os.getenv("SOPHOS_SOPHIE_RULE_NAME")

# Optional: Name of Sophie's manual allow rule that should be disabled daily at a fixed time
SOPHOS_SOPHIE_MANUAL_ALLOW_RULE_NAME = os.getenv("SOPHOS_SOPHIE_MANUAL_ALLOW_RULE_NAME")

# Optional: Time of day to disable Sophie's manual allow rule, format HH:MM (24-hour)
# Default: 19:30
_sophie_manual_disable_time = os.getenv("SOPHOS_SOPHIE_MANUAL_ALLOW_DISABLE_TIME", "19:30")
# Expose canonical string value
SOPHOS_SOPHIE_MANUAL_ALLOW_DISABLE_TIME = _sophie_manual_disable_time

# --- Operational Parameters (with defaults) ---
# Timezone for determining "today" and the cutoff time. Uses pytz database names.
# Default: 'Europe/London'
TIMEZONE = os.getenv("TIMEZONE", "Europe/London")

# The hour (in 24-hour format, 0-23) after which chore completion determines firewall rule state.
# E.g., 14 means the check applies from 2 PM onwards in the specified TIMEZONE.
# Default: 14 (2 PM)
_cutoff_hour_str = os.getenv("CUTOFF_HOUR", "14") # Loaded as string first for validation

# Path where the application log file will be written.
# Default: 'chore_monitor.log' in the script's directory.
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "chore_monitor.log")

# Path where the JSON file storing daily completion state is kept.
# Default: 'daily_completion_state.json' in the script's directory.
STATE_FILE_PATH = os.getenv("STATE_FILE_PATH", "daily_completion_state.json")


# --- Validation and Type Conversion ---

# Validate and convert CUTOFF_HOUR
try:
    CUTOFF_HOUR = int(_cutoff_hour_str)
    if not 0 <= CUTOFF_HOUR <= 23:
        raise ValueError("CUTOFF_HOUR must be an integer between 0 and 23.")
except ValueError as e:
    # Raise a more specific error indicating the source of the problem
    raise ValueError(f"Invalid configuration for CUTOFF_HOUR ('{_cutoff_hour_str}'): {e}") from e


# Check for missing required variables
_required_variables = {
    "TODOIST_API_KEY": TODOIST_API_KEY,
    "SOPHOS_HOST": SOPHOS_HOST,
    "SOPHOS_API_USER": SOPHOS_API_USER,
    "SOPHOS_API_PASSWORD": SOPHOS_API_PASSWORD,
    "TODOIST_DANIEL_SECTION_ID": TODOIST_DANIEL_SECTION_ID,
    "TODOIST_SOPHIE_SECTION_ID": TODOIST_SOPHIE_SECTION_ID,
    "SOPHOS_DANIEL_RULE_NAME": SOPHOS_DANIEL_RULE_NAME,
    "SOPHOS_SOPHIE_RULE_NAME": SOPHOS_SOPHIE_RULE_NAME,
}

_missing_vars = [name for name, value in _required_variables.items() if not value] # Checks for None or empty strings

if _missing_vars:
    raise ValueError(f"Missing required environment variables in .env file or environment: {', '.join(_missing_vars)}")

# --- Optional: Function to print loaded config (for debugging, excludes secrets) ---
def print_config_summary():
    """Prints a summary of the loaded configuration settings (excluding secrets)."""
    print("--- Configuration Summary ---")
    print(f"  SOPHOS_HOST: {SOPHOS_HOST}")
    # print(f"  SOPHOS_API_USER: {SOPHOS_API_USER}") # Exclude sensitive
    print(f"  TODOIST_KIDS_PROJECT_ID: {TODOIST_KIDS_PROJECT_ID if TODOIST_KIDS_PROJECT_ID else 'Not Set'}")
    print(f"  TODOIST_DANIEL_SECTION_ID: {TODOIST_DANIEL_SECTION_ID}")
    print(f"  TODOIST_SOPHIE_SECTION_ID: {TODOIST_SOPHIE_SECTION_ID}")
    print(f"  SOPHOS_DANIEL_RULE_NAME: {SOPHOS_DANIEL_RULE_NAME}")
    print(f"  SOPHOS_SOPHIE_RULE_NAME: {SOPHOS_SOPHIE_RULE_NAME}")
    print(f"  SOPHOS_SOPHIE_MANUAL_ALLOW_RULE_NAME: {SOPHOS_SOPHIE_MANUAL_ALLOW_RULE_NAME if SOPHOS_SOPHIE_MANUAL_ALLOW_RULE_NAME else 'Not Set'}")
    print(f"  SOPHOS_SOPHIE_MANUAL_ALLOW_DISABLE_TIME: {_sophie_manual_disable_time}")
    print(f"  TIMEZONE: {TIMEZONE}")
    print(f"  CUTOFF_HOUR: {CUTOFF_HOUR}")
    print(f"  LOG_FILE_PATH: {LOG_FILE_PATH}")
    print(f"  STATE_FILE_PATH: {STATE_FILE_PATH}")
    print("--------------------------")

# Example of how to potentially run the print function during development
# if __name__ == "__main__":
#     try:
#         print_config_summary()
#         print("\nConfiguration loaded successfully.")
#     except ValueError as e:
#         print(f"\nConfiguration Error: {e}")
