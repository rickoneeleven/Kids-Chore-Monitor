#!/usr/bin/env python3
"""
Test runner for Kids Chore Monitor
Discovers and runs all tests in the tests directory
"""

import sys
import unittest
import os

def run_tests():
    """Discover and run all tests"""
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create test loader
    loader = unittest.TestLoader()
    
    # Discover tests in the tests directory
    test_dir = os.path.join(script_dir, 'tests')
    suite = loader.discover(test_dir, pattern='test_*.py')
    
    # Create test runner with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    
    # Run tests
    print("="*70)
    print("Running Kids Chore Monitor Test Suite")
    print("="*70)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
    print("="*70)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    sys.exit(run_tests())