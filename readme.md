# Kids Chore Monitor
DATETIME of last agent review: 09/11/2025 10:11

## Overview

Kids Chore Monitor is a Python application designed to automate internet access control for children based on their chore completion status in Todoist. It integrates with the Todoist API to monitor task completion within specific project sections and interacts with the Sophos Firewall (XG/SFOS) API to enable or disable corresponding firewall rules.

In addition to chore-based checks, the system enforces a strict bedtime window where internet access is disabled regardless of chore status.

The core logic works as follows:
1.  Determine the current time in the configured `TIMEZONE` and evaluate one of three windows:
    *   Bedtime hours: 20:00 to 06:59. Always set the rule to **enabled** (Internet OFF).
    *   Morning free time: 07:00 to (`CUTOFF_HOUR` - 1). Set the rule to **disabled** (Internet ON), independent of chores.
    *   After cutoff: `current_hour >= CUTOFF_HOUR`.
2.  After cutoff time:
    *   If the child is already marked as done for today in `daily_completion_state.json`, set the rule to **disabled** (Internet ON).
    *   Otherwise, query Todoist for tasks due today or overdue in the child's section.
        - If tasks are incomplete, set the rule to **enabled** (Internet OFF).
        - If all tasks are complete, set the rule to **disabled** (Internet ON) and mark the child as done for today in the state file.

This system relies on API keys, specific IDs from Todoist, and rule names from Sophos, all configured via an `.env` file. Detailed logging is implemented for monitoring and troubleshooting.

## Features

*   Bedtime enforcement: Internet OFF between 20:00 and 07:00.
*   Morning free time window until the configured `CUTOFF_HOUR`.
*   Automated checking of chore completion status in designated Todoist sections after cutoff.
*   Automatic enabling/disabling of specific Sophos Firewall rules.
*   Per-child control for auto-disable behavior (e.g., disable is suppressed for Sophie).
*   Daily state persistence (`daily_completion_state.json`) to avoid redundant API calls and correctly handle checks after the cutoff.
*   Configuration managed via a `.env` file.
*   Logging to console by default; when scheduled via cron, redirect output to `cron.log` as in the example below.
*   Helper script (`get_todoist_ids.py`) to find required Todoist Project/Section IDs.
*   Test script (`test_sophos.py`) for verifying Sophos API connectivity and rule manipulation (use with caution).

### Optional daily manual rule disable
- You can configure a separate manual allow rule for Sophie that is automatically disabled once per day at a fixed time (default 19:30), independent of chore checks. Set `SOPHOS_SOPHIE_MANUAL_ALLOW_RULE_NAME` and optionally `SOPHOS_SOPHIE_MANUAL_ALLOW_DISABLE_TIME` in `.env` to enable this.

## How it Works (Workflow Summary)

1.  **Get Time:** Determine current time, timezone, and whether it's before or after the `CUTOFF_HOUR`.
2.  **Process Each Child:** For every configured child:
    *   **Before Cutoff:** Intend to `DISABLE` the firewall rule (Internet ON).
    *   **After Cutoff:**
        *   Check `state_manager`: Is the child already marked as done for today?
            *   **Yes:** Intend to `DISABLE` rule (Internet ON). Done processing this child.
            *   **No:** Proceed to check Todoist.
        *   Check `todoist_client`: Are there incomplete tasks due today/overdue?
            *   **Yes:** Intend to `ENABLE` rule (Internet OFF).
            *   **No:** Intend to `DISABLE` rule (Internet ON). Plan to update state file.
    *   **Apply Action:** Use `sophos_client` to set the firewall rule to the intended state (Enable/Disable).
    *   **Update State:** If the action was `DISABLE` (Internet ON) *because chores were completed after the cutoff*, update the `state_manager` to mark the child as done for today.
3.  **Save State:** Persist the updated completion status to `daily_completion_state.json`.

## Prerequisites

*   Python 3.x installed.
*   A Todoist account with API access enabled (retrieve your API key from Todoist settings).
*   A Sophos Firewall (XG/SFOS) accessible from the machine running the script.
    *   Web Admin access enabled.
    *   An API user created on Sophos with permissions to read and modify firewall rules.
    *   The IP address of the machine running the script likely needs to be allowed in the Sophos API configuration.
*   Network connectivity between the script host and the Sophos Firewall admin interface (typically port 4444).
*   `git` installed (for cloning the repository).

## Setup & Installation

1.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd kids-Chore-Monitor
    ```

2.  **Create and Activate Virtual Environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Linux/macOS
    # venv\Scripts\activate    # On Windows
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables:**
    *   Copy the example file: `cp .env.example .env`
    *   **Edit the `.env` file** with your actual credentials and settings:
        *   `TODOIST_API_KEY`
        *   `SOPHOS_HOST`
        *   `SOPHOS_API_USER`
        *   `SOPHOS_API_PASSWORD`
        *   Sophos Rule Names (`SOPHOS_DANIEL_RULE_NAME`, `SOPHOS_SOPHIE_RULE_NAME`)
        *   Todoist Section IDs (see step 5)
        *   Optionally adjust `TIMEZONE`, `CUTOFF_HOUR`, `LOG_FILE_PATH`, `STATE_FILE_PATH`.
    *   **IMPORTANT:** Never commit your actual `.env` file to version control. The `.gitignore` file should already prevent this.

5.  **Get Todoist Section IDs:**
    *   Ensure your `TODOIST_API_KEY` is correctly set in `.env`.
    *   Run the helper script:
        ```bash
        python get_todoist_ids.py
        ```
    *   The script will print the Project ID and Section IDs for "Daniel" and "Sophie" (or whatever names are configured in the script/your Todoist).
    *   Copy the `TODOIST_DANIEL_SECTION_ID` and `TODOIST_SOPHIE_SECTION_ID` values into your `.env` file.

6.  **Test Sophos Connection (Recommended but CAUTION):**
    *   Ensure Sophos details are correct in `.env`.
    *   Run the test script:
        ```bash
        python test_sophos.py
        ```
    *   **WARNING:** This script *will attempt to toggle* the configured firewall rules. It's intended to verify connectivity and permissions but modifies state. Run it only if you understand this and can verify/reset the rule status in the Sophos GUI afterwards.

## Configuration (`.env` File)

Configuration is loaded from a `.env` file in the project root. See `.env.example` for all available options and descriptions.

**Required:**
*   `TODOIST_API_KEY`: Your Todoist API token.
*   `SOPHOS_HOST`: Hostname or IP of your Sophos Firewall.
*   `SOPHOS_API_USER`: API username configured on Sophos.
*   `SOPHOS_API_PASSWORD`: Password for the Sophos API user.
*   `TODOIST_DANIEL_SECTION_ID`: Numeric ID of Daniel's chore section in Todoist.
*   `TODOIST_SOPHIE_SECTION_ID`: Numeric ID of Sophie's chore section in Todoist.
*   `SOPHOS_DANIEL_RULE_NAME`: Exact name of the Sophos firewall rule for Daniel.
*   `SOPHOS_SOPHIE_RULE_NAME`: Exact name of the Sophos firewall rule for Sophie.

**Optional (Defaults Provided):**
*   `TODOIST_KIDS_PROJECT_ID`: Parent project ID (optional, mainly for `get_todoist_ids.py`).
*   `TIMEZONE`: Timezone for date calculations (default: `Europe/London`).
*   `CUTOFF_HOUR`: Hour (0-23) after which checks affect rules (default: `14`).
*   `LOG_FILE_PATH`: Path for the application log (default: `chore_monitor.log`).
*   `STATE_FILE_PATH`: Path for the state JSON file (default: `daily_completion_state.json`).

## Usage

### Manual Execution

Ensure your virtual environment is activated (`source venv/bin/activate`) and run:
```bash
python main.py
```
Check the output in the console and the `chore_monitor.log` file.

### Scheduled Execution (Cron)

To run the script automatically (e.g., every 5 minutes), use `cron` (on Linux/macOS).

1.  Edit the crontab for the user who owns the project files:
    ```bash
    crontab -e
    ```
2.  Add the following line, **adjusting the paths** to match your specific setup:
    ```cron
    # Run Kids Chore Monitor every 5 minutes, logging output
    */5 * * * * cd /path/to/your/kids-Chore-Monitor && /path/to/your/kids-Chore-Monitor/venv/bin/python main.py >> /path/to/your/kids-Chore-Monitor/cron.log 2>&1

    # Optional: Clean up the cron log weekly (e.g., Sunday at 00:05)
    5 0 * * 0 rm -f /path/to/your/kids-Chore-Monitor/cron.log
    ```
3.  Save and exit the editor.

Cron will now execute the script, and any standard output or errors generated during the cron execution itself will be appended to `cron.log` in the project root.

## Key Components

*   `main.py`: Main application entry point, orchestrates the checks and actions.
*   `config.py`: Loads and validates configuration from the `.env` file.
*   `todoist_client.py`: Handles interaction with the Todoist API (fetching tasks, checking status).
*   `sophos_client.py`: Handles interaction with the Sophos Firewall API (getting/setting rule status).
*   `state_manager.py`: Manages loading, saving, and checking the daily completion state from `daily_completion_state.json`.
*   `get_todoist_ids.py`: Utility script to find necessary Todoist project/section IDs.
*   `test_sophos.py`: Utility script to test Sophos connection and rule toggling (use cautiously).
*   `tests/`: Unit tests for time windows and auto-disable suppression (`test_time_logic.py`, `test_auto_disable_suppression.py`).
*   `run_tests.py`: Simple runner to execute the test suite.
*   `.env.example`: Template for the required environment variables.
*   `requirements.txt`: List of Python dependencies.

## Logging

*   **Console output:** By default the application logs to stdout with structured messages.
*   **Cron log:** Use shell redirection in your crontab to capture output, e.g. `>> cron.log 2>&1` as shown above.
*   **File logging (optional):** A `LOG_FILE_PATH` is defined in `.env`, but file logging is not enabled by default in `main.py`. You can add a `logging.FileHandler` if you prefer a dedicated application log file.

## State Management

The file `daily_completion_state.json` (or path specified in `.env`) stores the last date (YYYY-MM-DD) each child's chores were confirmed complete *after* the cutoff time. This prevents repeatedly checking Todoist once completion is confirmed for the day and ensures the correct state is maintained across script runs.

Example content:
```json
{
    "daniel": "2023-10-27",
    "sophie": "2023-10-26"
}
```

## Troubleshooting

*   **Check Logs:** Always start by examining `chore_monitor.log` and `cron.log` for specific error messages.
*   **Configuration:** Double-check all values in your `.env` file (API keys, hostnames, IDs, rule names). Ensure there are no typos or extra spaces.
*   **Connectivity:**
    *   Can the machine running the script ping the `SOPHOS_HOST`?
    *   Is the Sophos API accessible on the configured port (usually 4444)? Use `curl https://<SOPHOS_HOST>:4444` (expect a certificate warning if using default self-signed certs, but it should attempt connection).
    *   Run `python test_sophos.py` (carefully!) to verify Sophos API communication.
*   **Permissions:**
    *   Does the user running the script have read access to `.env` and write access to the directories/files specified by `LOG_FILE_PATH` and `STATE_FILE_PATH`?
    *   Are the Todoist API key and Sophos API user credentials correct and have the necessary permissions?
    *   Is the script host's IP address allowed in the Sophos Firewall's API configuration?
*   **Firewall Rules:** Ensure the firewall rules named in `.env` actually exist on the Sophos Firewall.
*   **Dependencies:** Confirm all packages in `requirements.txt` are installed in the active virtual environment.

## License

[Specify License Here - e.g., MIT License]
