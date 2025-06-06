# Tooling Tests Documentation

## Overview

This directory contains comprehensive tests for the runtime tooling CLI tools. The tests are organized into categories and use pytest as the testing framework.

## Test Structure

```
tests/
├── test_core/              # Core component tests
│   ├── test_version_operations.py
│   └── test_cli_utils.py
├── test_cli/               # CLI tool tests
│   ├── test_commit_tools.py
│   └── test_release_tools.py
├── test_integration/       # Integration tests
├── test_mocks/            # Mock objects and fixtures
├── test_performance/      # Performance tests
├── test_errors/           # Error handling tests
├── test_e2e/              # End-to-end tests
└── run_all_tests.py       # Test runner
```

## Running Tests

### Run All Tests
```bash
# Basic run
python tooling/tests/run_all_tests.py

# With verbose output
python tooling/tests/run_all_tests.py -v

# With coverage report
python tooling/tests/run_all_tests.py -c

# Save results to JSON
python tooling/tests/run_all_tests.py -o test_results.json
```

### Run Specific Test Files
```bash
# Run a single test file
pytest tooling/tests/test_core/test_version_operations.py

# Run with verbose output
pytest -v tooling/tests/test_cli/test_commit_tools.py

# Run specific test class
pytest tooling/tests/test_cli/test_release_tools.py::TestReleaseCommand

# Run specific test method
pytest tooling/tests/test_cli/test_release_tools.py::TestReleaseCommand::test_release_full_flow
```

### Run Test Groups
```bash
# Run only core tests
python tooling/tests/run_all_tests.py --group test_core

# Run only CLI tests
python tooling/tests/run_all_tests.py --group test_cli
```

## Test Categories

### 1. Core Component Tests (`test_core/`)

#### test_version_operations.py
- Version validation and comparison
- YAML/TOML value extraction
- Version update operations
- Multi-file version synchronization

#### test_cli_utils.py
- CLI logging setup
- Common argument parsing
- Colored output functions
- Progress logging
- User confirmation prompts

### 2. CLI Tool Tests (`test_cli/`)

#### test_commit_tools.py
- Smart commit functionality
- AI commit message generation
- Git integration
- Pre-commit hooks
- Commit validation

#### test_release_tools.py
- Release orchestration
- Pre-release checks
- Version updates
- Patch management
- Release notes generation
- Tag management

### 3. Integration Tests (`test_integration/`)
- Multi-tool workflows
- End-to-end scenarios
- Cross-component interactions

### 4. Mock Tests (`test_mocks/`)
- Reusable mock objects
- Test fixtures
- Fake implementations

### 5. Performance Tests (`test_performance/`)
- Command execution speed
- Memory usage
- Large file handling
- Concurrent operations

### 6. Error Handling Tests (`test_errors/`)
- Exception handling
- Error recovery
- Rollback mechanisms
- User error scenarios

### 7. End-to-End Tests (`test_e2e/`)
- Complete workflow tests
- Real repository operations
- Full release cycles

## Writing New Tests

### Test File Template
```python
#!/usr/bin/env python3
"""
Test description
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from module_to_test import function_to_test


class TestFeatureName:
    """Test feature description"""
    
    def test_basic_functionality(self):
        """Test basic feature behavior"""
        result = function_to_test()
        assert result == expected_value
    
    @patch('module.external_dependency')
    def test_with_mock(self, mock_dep):
        """Test with mocked dependencies"""
        mock_dep.return_value = "mocked"
        result = function_to_test()
        assert result == "expected"
        mock_dep.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

### Best Practices

1. **Test Isolation**: Each test should be independent
2. **Mock External Dependencies**: Use mocks for subprocess calls, file I/O, network requests
3. **Test Edge Cases**: Include tests for error conditions and boundary values
4. **Descriptive Names**: Use clear, descriptive test names that explain what is being tested
5. **Arrange-Act-Assert**: Follow the AAA pattern in test structure
6. **Fixtures**: Use pytest fixtures for common setup/teardown
7. **Parametrized Tests**: Use `@pytest.mark.parametrize` for testing multiple inputs

### Coverage Goals

- Aim for >80% code coverage
- Focus on critical paths and error handling
- Don't just chase coverage numbers - ensure meaningful tests

## Continuous Integration

### GitHub Actions Workflow
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    - name: Run tests
      run: python tooling/tests/run_all_tests.py -c
    - name: Upload coverage
      uses: codecov/codecov-action@v1
```

## Debugging Tests

### Run with pytest debugging
```bash
# Drop into debugger on failure
pytest --pdb tooling/tests/test_file.py

# Show local variables on failure
pytest -l tooling/tests/test_file.py

# Capture print statements
pytest -s tooling/tests/test_file.py
```

### VS Code Configuration
```json
{
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": [
        "tooling/tests"
    ]
}
```

## Test Data

Test data files should be placed in `tests/fixtures/` and loaded using:

```python
def get_fixture_path(filename):
    """Get path to test fixture file"""
    return Path(__file__).parent / "fixtures" / filename
```

## Performance Benchmarks

Track performance over time:

```bash
# Run performance tests
pytest tooling/tests/test_performance/ --benchmark-only

# Compare with previous results
pytest tooling/tests/test_performance/ --benchmark-compare
```

## Future Improvements

1. **Parallel Test Execution**: Implement parallel test running for faster CI
2. **Property-Based Testing**: Add hypothesis tests for complex scenarios
3. **Mutation Testing**: Use mutmut to verify test effectiveness
4. **Integration Test Environment**: Docker-based test environment
5. **Visual Regression Tests**: For CLI output formatting
6. **Load Testing**: For concurrent operations
7. **Security Testing**: Input validation and injection prevention 