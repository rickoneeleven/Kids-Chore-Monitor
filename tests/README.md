# Kids Chore Monitor - Test Suite

## Overview
This test suite validates the time-based logic and bedtime control features of the Kids Chore Monitor application.

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

# Run with verbose output
./venv/bin/python -m unittest discover tests -v
```

## Test Coverage

### TestTimeBedtimeLogic
Tests the core time-based firewall rule logic:
- **Bedtime hours (20:00-06:59)**: Internet OFF enforcement
- **Morning hours (07:00-13:59)**: Internet ON (free time)
- **Chore checking (14:00-19:59)**: Internet depends on chore completion
- **Critical transitions**: 06:59→07:00, 13:59→14:00, 19:59→20:00
- **Bedtime override**: Ensures bedtime trumps completed chores

### TestCompleteTimeFlow
- **24-hour cycle**: Validates behavior for every critical hour of the day

## Test Results
All 9 tests validate the enhanced bedtime control logic:
- ✅ Bedtime enforcement (20:00-07:00)
- ✅ Morning free time (07:00-14:00)
- ✅ Chore checking (14:00-20:00)
- ✅ Smooth transitions between time periods
- ✅ Bedtime priority over chore completion

## Files
- `test_time_logic.py`: Main test module with all time-based logic tests
- `__init__.py`: Package initialization file

## Requirements
Tests use Python's built-in `unittest` framework with the following dependencies:
- `pytz`: Timezone handling
- `unittest.mock`: Mocking external dependencies

No additional test dependencies required beyond the main application requirements.