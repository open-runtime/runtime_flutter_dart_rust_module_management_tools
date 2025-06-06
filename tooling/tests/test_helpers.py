#!/usr/bin/env python3
"""
Test helpers for FDR (Flutter, Dart, Rust) project structure.
"""

import os
import tempfile
from pathlib import Path
from contextlib import contextmanager
from typing import Generator
import pytest


@contextmanager
def fdr_project_structure(root: Path = None) -> Generator[Path, None, None]:
    """
    Create a minimal FDR project structure for testing.
    
    Creates:
    - root/
        - dart/
            - pubspec.yaml
            - rust/
                - Cargo.toml
        - flutter/
            - pubspec.yaml
    """
    if root is None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _create_fdr_structure(root)
            yield root
    else:
        _create_fdr_structure(root)
        yield root


def _create_fdr_structure(root: Path):
    """Create the FDR directory structure"""
    # Create directories
    (root / 'dart').mkdir(exist_ok=True)
    (root / 'flutter').mkdir(exist_ok=True)
    (root / 'dart' / 'rust').mkdir(exist_ok=True)
    
    # Create pubspec files
    (root / 'dart' / 'pubspec.yaml').write_text("""
name: runtime
version: 1.0.0
description: Runtime Dart package
""")
    
    (root / 'flutter' / 'pubspec.yaml').write_text("""
name: runtime_flutter
version: 1.0.0
description: Runtime Flutter package
""")
    
    # Create Cargo.toml
    (root / 'dart' / 'rust' / 'Cargo.toml').write_text("""
[package]
name = "runtime"
version = "1.0.0"
edition = "2021"
""")


@pytest.fixture
def fdr_project(tmp_path):
    """Pytest fixture that provides FDR project structure"""
    _create_fdr_structure(tmp_path)
    
    # Save current directory
    original_cwd = Path.cwd()
    
    # Change to project root
    os.chdir(tmp_path)
    
    yield tmp_path
    
    # Restore directory
    os.chdir(original_cwd)


@pytest.fixture
def mock_fdr_project(monkeypatch, tmp_path):
    """
    Pytest fixture that mocks the FDR project structure.
    Sets up environment and patches config to use test directory.
    """
    _create_fdr_structure(tmp_path)
    
    # Set environment variable to indicate test mode
    monkeypatch.setenv('PYTEST_CURRENT_TEST', 'true')
    
    # Patch get_project_root to return our test directory
    def mock_get_project_root():
        return tmp_path
    
    # Try to patch different locations where get_project_root might be
    try:
        # Import the module first, then patch the class method
        from tooling.core import base_config
        monkeypatch.setattr(base_config.RuntimeConfig, 'get_project_root', lambda self: tmp_path)
    except (AttributeError, ImportError):
        pass
    
    try:
        from tooling.core import simple_config
        monkeypatch.setattr(simple_config.Config, 'get_project_root', lambda: tmp_path)
    except (AttributeError, ImportError):
        pass
    
    # Also patch Path.cwd() if needed
    original_cwd = Path.cwd()
    monkeypatch.chdir(tmp_path)
    
    yield tmp_path


def setup_fdr_test_env(test_func):
    """
    Decorator that sets up FDR project structure for a test.
    
    Usage:
        @setup_fdr_test_env
        def test_something():
            # Test will run with FDR project structure available
            pass
    """
    def wrapper(*args, **kwargs):
        with fdr_project_structure() as project_root:
            original_cwd = Path.cwd()
            os.chdir(project_root)
            try:
                return test_func(*args, **kwargs)
            finally:
                os.chdir(original_cwd)
    
    return wrapper 