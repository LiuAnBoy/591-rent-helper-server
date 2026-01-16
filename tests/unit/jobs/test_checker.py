"""
Unit tests for src/jobs/checker.py

Note: Matching logic tests moved to tests/unit/matching/test_matcher.py
"""

import pytest

from src.jobs.checker import Checker

# Import fixtures
pytest_plugins = ["tests.fixtures.checker"]


# ============================================================
# Checker instance for testing
# ============================================================


@pytest.fixture
def checker():
    """Create a Checker instance for testing."""
    return Checker(enable_broadcast=False)


# ============================================================
# Checker flow tests (if any)
# ============================================================

# Note: Matching logic tests (TestMatchObjectToSubscription, TestMatchFloor,
# TestExtractFloorNumber) have been moved to tests/unit/matching/test_matcher.py
# as part of the refactoring to extract matching logic to src/matching/matcher.py
