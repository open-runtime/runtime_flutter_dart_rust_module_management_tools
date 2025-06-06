"""
Pytest configuration and shared fixtures for all tests.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import our test helpers
from tooling.tests.test_helpers import (
    fdr_project,
    mock_fdr_project,
    fdr_project_structure
)

# Re-export fixtures so they're available to all tests
__all__ = ['fdr_project', 'mock_fdr_project']


def pytest_configure(config):
    """
    Configure pytest with custom settings.
    """
    # Set environment variable to indicate we're in test mode
    os.environ['PYTEST_CURRENT_TEST'] = '1'
    
    # Disable color output in tests for consistent output
    os.environ['NO_COLOR'] = '1'


def pytest_unconfigure(config):
    """
    Clean up after pytest.
    """
    # Remove test environment variables
    os.environ.pop('PYTEST_CURRENT_TEST', None)
    os.environ.pop('NO_COLOR', None) 