# CLAUDE.md - Kids Chore Monitor Project Context

## Project Overview
Kids Chore Monitor is a Python application that manages children's internet access through Sophos Firewall rules based on:
1. **Chore completion** (tracked via Todoist API)
2. **Time of day** (bedtime enforcement and morning free time)
3. **Daily state persistence** (to avoid redundant API calls)

## Core Business Logic

### Time-Based Internet Control Schedule
```
00:00-06:59: Internet OFF (bedtime - ALWAYS enforced)
07:00-13:59: Internet ON  (morning free time - no chore checking)
14:00-19:59: Internet depends on chore completion (checks Todoist)
20:00-23:59: Internet OFF (bedtime - ALWAYS enforced)
```

### Key Decision Points
- **Bedtime (20:00-07:00)**: ALWAYS blocks internet, overrides everything
- **Morning (07:00-14:00)**: ALWAYS allows internet, no chore checking
- **Afternoon (14:00-20:00)**: Checks chores → incomplete = blocked, complete = allowed

## Architecture

### Main Components
1. **main.py**: Orchestrates the entire flow
   - `process_child()`: Core logic with bedtime check FIRST (lines 257-268)
   - Constants: `BEDTIME_HOUR = 20`, `MORNING_HOUR = 7` (lines 42-43)
   
2. **todoist_client.py**: Checks if children have incomplete chores
3. **sophos_client.py**: Controls firewall rules (Enable = Internet OFF, Disable = Internet ON)
4. **state_manager.py**: Tracks daily completion to avoid redundant checks
5. **config.py**: Loads environment variables (API keys, rule names, timezone)

### Critical Files
- `.env`: Contains secrets (API keys, Sophos credentials, rule names)
- `daily_completion_state.json`: Persists who completed chores today
- `chore_monitor.log`: Application logs
- `cron.log`: Cron execution logs

## Current Configuration
- **Cron**: Runs every 5 minutes (`*/5 * * * *`)
- **Timezone**: Europe/London
- **Cutoff Hour**: 14:00 (2 PM) - when chore checking starts
- **Children**: Daniel and Sophie (each with separate Todoist sections and Sophos rules)

## Testing
- **Test Suite**: `./venv/bin/python run_tests.py`
- **Coverage**: 9 tests covering all time periods and transitions
- **Location**: `/tests/` folder with unittest framework

## Common Tasks

### Check Current Behavior
```bash
# See what the script would do right now
./venv/bin/python main.py

# Check logs
tail -f chore_monitor.log
tail -f cron.log
```

### Modify Time Windows
- Edit `BEDTIME_HOUR` and `MORNING_HOUR` constants in main.py (lines 42-43)
- The cutoff hour (14:00) is in config.py/`.env` as `CUTOFF_HOUR`

### Test Changes
```bash
# Run full test suite
./venv/bin/python run_tests.py

# Test specific scenarios
./venv/bin/python -m unittest tests.test_time_logic.TestTimeBedtimeLogic.test_bedtime_overrides_completed_chores
```

### Debug Issues
1. Check `chore_monitor.log` for application errors
2. Check `cron.log` for cron execution issues
3. Verify `.env` has all required variables
4. Test Sophos connectivity: `./venv/bin/python test_sophos.py`
5. Check Todoist IDs: `./venv/bin/python get_todoist_ids.py`

## Important Notes
- **Firewall Rule Logic**: Enable = Internet OFF, Disable = Internet ON (counterintuitive!)
- **State File**: Resets daily, marks children "done" when chores complete
- **Fail-Safe**: If APIs fail, defaults to Internet OFF (rule enabled)
- **Bedtime Priority**: Bedtime ALWAYS overrides chore completion

## Recent Changes (2025-08-08)
Added bedtime enforcement (20:00-07:00) to prevent late-night internet access even when chores are complete. The logic now checks bedtime FIRST before any other conditions.