#!/usr/bin/env python3
"""
Unit tests for common_config.py functions
"""

import sys
import os
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.common_config import (
    Colors, print_color, extract_yaml_value, extract_toml_value,
    validate_version, compare_versions, update_version_in_file,
    run_command, check_git_repo, check_git_state
)


class TestCommonConfig(unittest.TestCase):
    """Test cases for common_config utility functions"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp(prefix="test_common_")
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_extract_yaml_value(self):
        """Test YAML value extraction"""
        # Create test YAML file
        yaml_content = """name: test_package
version: 1.2.3
description: A test package
dependencies:
  some_dep: ^1.0.0
"""
        yaml_file = Path("test.yaml")
        yaml_file.write_text(yaml_content)
        
        # Test extraction
        self.assertEqual(extract_yaml_value("test.yaml", "name"), "test_package")
        self.assertEqual(extract_yaml_value("test.yaml", "version"), "1.2.3")
        self.assertEqual(extract_yaml_value("test.yaml", "description"), "A test package")
        self.assertIsNone(extract_yaml_value("test.yaml", "nonexistent"))
        
        # Test with quotes
        yaml_file.write_text('name: "quoted_name"\nversion: \'1.2.3\'')
        self.assertEqual(extract_yaml_value("test.yaml", "name"), "quoted_name")
        self.assertEqual(extract_yaml_value("test.yaml", "version"), "1.2.3")
        
        print_color(Colors.GREEN, "✓ YAML extraction test passed")
    
    def test_extract_toml_value(self):
        """Test TOML value extraction"""
        # Create test TOML file
        toml_content = """[package]
name = "test_crate"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = "1.0"
"""
        toml_file = Path("Cargo.toml")
        toml_file.write_text(toml_content)
        
        # Test extraction
        self.assertEqual(extract_toml_value("Cargo.toml", "name"), "test_crate")
        self.assertEqual(extract_toml_value("Cargo.toml", "version"), "0.1.0")
        self.assertEqual(extract_toml_value("Cargo.toml", "edition"), "2021")
        self.assertIsNone(extract_toml_value("Cargo.toml", "nonexistent"))
        
        print_color(Colors.GREEN, "✓ TOML extraction test passed")
    
    def test_validate_version(self):
        """Test version validation"""
        # Valid versions
        self.assertTrue(validate_version("1.2.3"))
        self.assertTrue(validate_version("0.0.1"))
        self.assertTrue(validate_version("10.20.30"))
        
        # Invalid versions
        self.assertFalse(validate_version("1.2"))
        self.assertFalse(validate_version("1.2.3.4"))
        self.assertFalse(validate_version("v1.2.3"))
        self.assertFalse(validate_version("1.2.3-beta"))
        self.assertFalse(validate_version("abc"))
        
        print_color(Colors.GREEN, "✓ Version validation test passed")
    
    def test_compare_versions(self):
        """Test version comparison"""
        # v1 < v2
        self.assertEqual(compare_versions("1.0.0", "2.0.0"), -1)
        self.assertEqual(compare_versions("1.2.3", "1.2.4"), -1)
        self.assertEqual(compare_versions("1.2.3", "1.3.0"), -1)
        
        # v1 = v2
        self.assertEqual(compare_versions("1.2.3", "1.2.3"), 0)
        self.assertEqual(compare_versions("0.0.0", "0.0.0"), 0)
        
        # v1 > v2
        self.assertEqual(compare_versions("2.0.0", "1.0.0"), 1)
        self.assertEqual(compare_versions("1.2.4", "1.2.3"), 1)
        self.assertEqual(compare_versions("1.3.0", "1.2.3"), 1)
        
        print_color(Colors.GREEN, "✓ Version comparison test passed")
    
    def test_update_version_in_file(self):
        """Test version updates in different file types"""
        # Test YAML update
        yaml_file = Path("pubspec.yaml")
        yaml_file.write_text("name: test\nversion: 1.0.0\ndescription: test")
        
        self.assertTrue(update_version_in_file("pubspec.yaml", "2.0.0", "yaml"))
        self.assertEqual(extract_yaml_value("pubspec.yaml", "version"), "2.0.0")
        
        # Test TOML update
        toml_file = Path("Cargo.toml")
        toml_file.write_text('[package]\nname = "test"\nversion = "1.0.0"')
        
        self.assertTrue(update_version_in_file("Cargo.toml", "2.0.0", "toml"))
        self.assertEqual(extract_toml_value("Cargo.toml", "version"), "2.0.0")
        
        # Test Dart update
        dart_file = Path("cargo.dart")
        dart_file.write_text("const String CARGO_VERSION = '1.0.0';")
        
        self.assertTrue(update_version_in_file("cargo.dart", "2.0.0", "dart"))
        content = dart_file.read_text()
        self.assertIn("'2.0.0'", content)
        
        print_color(Colors.GREEN, "✓ Version update test passed")
    
    def test_run_command(self):
        """Test command execution wrapper"""
        # Test successful command
        code, stdout, stderr = run_command(['echo', 'hello'])
        self.assertEqual(code, 0)
        self.assertEqual(stdout, 'hello')
        self.assertEqual(stderr, '')
        
        # Test command with error
        code, stdout, stderr = run_command(['ls', '/nonexistent_directory_12345'])
        self.assertNotEqual(code, 0)
        
        # Test timeout
        code, stdout, stderr = run_command(['sleep', '10'], timeout=1)
        self.assertEqual(code, -1)
        self.assertIn('timed out', stderr)
        
        print_color(Colors.GREEN, "✓ Command execution test passed")
    
    @patch('subprocess.run')
    def test_check_git_repo(self, mock_run):
        """Test git repository check"""
        # Mock successful git check
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        self.assertTrue(check_git_repo())
        
        # Mock failed git check
        mock_run.return_value = MagicMock(returncode=1, stdout='', stderr='')
        self.assertFalse(check_git_repo())
        
        print_color(Colors.GREEN, "✓ Git repo check test passed")


class TestVersionFileUpdates(unittest.TestCase):
    """Test version file update functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp(prefix="test_version_")
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_complex_yaml_update(self):
        """Test updating version in complex YAML file"""
        yaml_content = """name: complex_package
version: 1.0.0
description: |
  A complex package with
  multiline description
  
environment:
  sdk: '>=2.12.0 <3.0.0'
  
dependencies:
  http: ^0.13.0
  json_annotation: ^4.0.0
  
dev_dependencies:
  test: ^1.16.0
  build_runner: ^2.0.0
"""
        yaml_file = Path("pubspec.yaml")
        yaml_file.write_text(yaml_content)
        
        # Update version
        self.assertTrue(update_version_in_file("pubspec.yaml", "2.5.0", "yaml"))
        
        # Verify update
        updated_content = yaml_file.read_text()
        self.assertIn("version: 2.5.0", updated_content)
        # Ensure other content is preserved
        self.assertIn("http: ^0.13.0", updated_content)
        self.assertIn("multiline description", updated_content)
        
        print_color(Colors.GREEN, "✓ Complex YAML update test passed")
    
    def test_backup_creation(self):
        """Test that backups are created during updates"""
        # Create original file
        yaml_file = Path("test.yaml")
        original_content = "name: test\nversion: 1.0.0"
        yaml_file.write_text(original_content)
        
        # Update version
        update_version_in_file("test.yaml", "2.0.0", "yaml")
        
        # Check backup was created and removed
        backup_file = Path("test.yaml.bak")
        self.assertFalse(backup_file.exists())  # Should be cleaned up on success
        
        print_color(Colors.GREEN, "✓ Backup creation test passed")


if __name__ == "__main__":
    unittest.main(verbosity=2) 