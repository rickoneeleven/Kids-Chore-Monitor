# Kids Chore Monitor - Test Suite
DATETIME of last agent review: 09/11/2025 10:11

## Overview
This test suite validates the time-based logic, bedtime enforcement, per-child auto-disable suppression, and the daily scheduled disable of a manual allow rule for Sophie.

## Running Tests

### Quick Start
From the project root directory:
```bash
./venv/bin/python run_tests.py
```

### Alternative Methods
```bash
# Run from project root
python -m unittest discover tests

# Run specific test file
./venv/bin/python -m unittest tests.test_time_logic
./venv/bin/python -m unittest tests.test_auto_disable_suppression
./venv/bin/python -m unittest tests.test_scheduled_actions

# Run with verbose output
./venv/bin/python -m unittest discover tests -v
```

## Test Coverage

### TestTimeBedtimeLogic
Validates core time-window behavior:
- Bedtime hours (20:00-06:59): Internet OFF enforcement.
- Morning hours (07:00-13:59): Internet ON (free time).
- Chore checking (14:00-19:59): Internet depends on chore completion.
- Critical transitions: 06:59->07:00, 13:59->14:00, 19:59->20:00.
- Bedtime override: Bedtime trumps completed chores.

### TestCompleteTimeFlow
- 24-hour cycle: Validates behavior for every critical hour of the day.

### TestAutoDisableSuppression
Validates per-child auto-disable suppression behavior (e.g., suppress DISABLE for specific children):
- Before cutoff: DISABLE actions can be suppressed.
- After cutoff with incomplete chores: ENABLE remains enforced.
- Bedtime window: ENABLE enforcement regardless of suppression.

### TestScheduledActions
Validates daily scheduled disable of a manual allow rule:
- No-op before the scheduled time.
- Disables once after the scheduled time and records completion for the day.
- Does not run again the same day; retries on failure; runs again next day.

## Test Results
All 14 tests currently validate the time-window logic and suppression rules:
- Bedtime enforcement (20:00-07:00)
- Morning free time (07:00-14:00)
- Chore checking (14:00-20:00)
- Smooth transitions between time periods
- Bedtime priority over chore completion
- Auto-disable suppression behavior

## Files
- `test_time_logic.py`: Time-window and transition tests
- `test_auto_disable_suppression.py`: Per-child auto-disable suppression tests
- `test_scheduled_actions.py`: Daily manual rule disable scheduler tests
- `__init__.py`: Package initialization file

## Requirements
Tests use Python's built-in `unittest` framework with:
- `pytz`: Timezone handling
- `unittest.mock`: Mocking external dependencies

No additional test dependencies required beyond the main application requirements.
