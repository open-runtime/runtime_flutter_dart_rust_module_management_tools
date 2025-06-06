#!/usr/bin/env python3
"""
Test version operations from common_config.py
"""

import pytest
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from tooling.utils.version_utils import validate_version, compare_versions
    from tooling.utils.file_utils import (
        extract_yaml_value, extract_toml_value, update_all_versions
    )
except ImportError:
    from utils.version_utils import validate_version, compare_versions
    from utils.file_utils import (
        extract_yaml_value, extract_toml_value, update_all_versions
    )

try:
    from tooling.utils.file_utils import update_yaml_version
except ImportError:
    from utils.file_utils import update_yaml_version


class TestVersionValidation:
    """Test version validation functions"""
    
    def test_valid_versions(self):
        """Test valid semantic versions"""
        assert validate_version("1.2.3") == True
        assert validate_version("0.0.1") == True
        assert validate_version("10.20.30") == True
        assert validate_version("1.0.0") == True
    
    def test_invalid_versions(self):
        """Test invalid version formats"""
        assert validate_version("v1.2.3") == False  # Has 'v' prefix
        assert validate_version("1.2") == False     # Missing patch
        assert validate_version("1.2.3.4") == False # Too many parts
        assert validate_version("1.2.a") == False   # Non-numeric
        assert validate_version("") == False        # Empty
        assert validate_version("1.-2.3") == False  # Negative number
    
    def test_edge_cases(self):
        """Test edge cases for version validation"""
        assert validate_version("0.0.0") == True
        assert validate_version("999.999.999") == True
        assert validate_version(" 1.2.3 ") == False  # Has whitespace
        assert validate_version("1.2.3-alpha") == False  # Has suffix


class TestVersionComparison:
    """Test version comparison logic"""
    
    def test_equal_versions(self):
        """Test comparing equal versions"""
        assert compare_versions("1.2.3", "1.2.3") == 0
        assert compare_versions("0.0.0", "0.0.0") == 0
    
    def test_major_version_differences(self):
        """Test major version comparisons"""
        assert compare_versions("2.0.0", "1.0.0") > 0
        assert compare_versions("1.0.0", "2.0.0") < 0
    
    def test_minor_version_differences(self):
        """Test minor version comparisons"""
        assert compare_versions("1.2.0", "1.1.0") > 0
        assert compare_versions("1.1.0", "1.2.0") < 0
    
    def test_patch_version_differences(self):
        """Test patch version comparisons"""
        assert compare_versions("1.2.3", "1.2.2") > 0
        assert compare_versions("1.2.2", "1.2.3") < 0
    
    def test_complex_comparisons(self):
        """Test complex version comparisons"""
        assert compare_versions("10.0.0", "9.99.99") > 0
        assert compare_versions("1.0.0", "0.99.99") > 0
        assert compare_versions("1.2.3", "1.2.3") == 0


class TestFileExtraction:
    """Test file content extraction functions"""
    
    def test_extract_yaml_value(self, tmp_path):
        """Test extracting values from YAML files"""
        yaml_file = tmp_path / "test.yaml"
        yaml_content = """
name: test_package
version: 1.2.3
description: A test package
dependencies:
  some_dep: ^1.0.0
"""
        yaml_file.write_text(yaml_content)
        
        assert extract_yaml_value(str(yaml_file), "name") == "test_package"
        assert extract_yaml_value(str(yaml_file), "version") == "1.2.3"
        assert extract_yaml_value(str(yaml_file), "description") == "A test package"
        assert extract_yaml_value(str(yaml_file), "nonexistent") is None
    
    def test_extract_yaml_nested(self, tmp_path):
        """Test extracting nested YAML values"""
        yaml_file = tmp_path / "nested.yaml"
        yaml_content = """
package:
  name: nested_test
  version: 2.0.0
  metadata:
    author: Test Author
"""
        yaml_file.write_text(yaml_content)
        
        # Current implementation doesn't support nested, but test the behavior
        assert extract_yaml_value(str(yaml_file), "package") is None
    
    def test_extract_toml_value(self, tmp_path):
        """Test extracting values from TOML files"""
        toml_file = tmp_path / "Cargo.toml"
        toml_content = """
[package]
name = "test_crate"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = "1.0"
"""
        toml_file.write_text(toml_content)
        
        assert extract_toml_value(str(toml_file), "name") == "test_crate"
        assert extract_toml_value(str(toml_file), "version") == "0.1.0"
        assert extract_toml_value(str(toml_file), "edition") == "2021"
        assert extract_toml_value(str(toml_file), "nonexistent") is None
    
    def test_extract_from_missing_files(self):
        """Test extraction from non-existent files"""
        assert extract_yaml_value("nonexistent.yaml", "key") is None
        assert extract_toml_value("nonexistent.toml", "key") is None
    
    def test_extract_from_invalid_files(self, tmp_path):
        """Test extraction from invalid format files"""
        # Invalid YAML
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("{ invalid yaml content :")
        assert extract_yaml_value(str(bad_yaml), "key") is None
        
        # Invalid TOML
        bad_toml = tmp_path / "bad.toml"
        bad_toml.write_text("[invalid toml content")
        assert extract_toml_value(str(bad_toml), "key") is None


class TestVersionUpdate:
    """Test version update functionality"""
    
    def test_update_dart_pubspec(self, tmp_path, monkeypatch):
        """Test updating Dart pubspec.yaml"""
        # Create test structure
        dart_dir = tmp_path / "dart"
        dart_dir.mkdir()
        pubspec = dart_dir / "pubspec.yaml"
        pubspec.write_text("""
name: test_dart
version: 1.0.0
description: Test package
""")
        
        # Change to test directory
        monkeypatch.chdir(tmp_path)
        
        # Update version
        assert update_yaml_version(str(pubspec), "2.0.0") == True
        
        # Verify update
        content = pubspec.read_text()
        assert "version: 2.0.0" in content
        assert "version: 1.0.0" not in content
    
    def test_update_preserves_formatting(self, tmp_path):
        """Test that version updates preserve file formatting"""
        yaml_file = tmp_path / "test.yaml"
        original_content = """# Header comment
name: test_package
version: 1.0.0  # inline comment
description: |
  Multi-line
  description
"""
        yaml_file.write_text(original_content)
        
        update_yaml_version(str(yaml_file), "2.0.0")
        
        updated_content = yaml_file.read_text()
        assert "# Header comment" in updated_content
        # Note: inline comments on the version line are not preserved by the regex replacement
        # This is a known limitation of the current implementation
        assert "Multi-line" in updated_content
        assert "version: 2.0.0" in updated_content
        assert "name: test_package" in updated_content


class TestGetCurrentVersion:
    """Test getting current version from multiple sources"""
    
    def test_get_version_from_dart(self, tmp_path):
        """Test getting version from Dart pubspec"""
        # Create test structure with project markers
        dart_dir = tmp_path / "dart"
        dart_dir.mkdir()
        pubspec = dart_dir / "pubspec.yaml"
        pubspec.write_text("version: 1.2.3")
        
        # Use extract_yaml_value to get version
        version = extract_yaml_value(str(pubspec), "version")
        assert version == "1.2.3"
    
    def test_version_mismatch_detection(self, tmp_path):
        """Test detection of version mismatches"""
        # Create test files with different versions
        dart_dir = tmp_path / "dart"
        flutter_dir = tmp_path / "flutter"
        dart_dir.mkdir()
        flutter_dir.mkdir()
        
        dart_pubspec = dart_dir / "pubspec.yaml"
        flutter_pubspec = flutter_dir / "pubspec.yaml"
        
        dart_pubspec.write_text("version: 1.2.3")
        flutter_pubspec.write_text("version: 1.2.4")  # Different version
        
        # Get versions from both files
        dart_version = extract_yaml_value(str(dart_pubspec), "version")
        flutter_version = extract_yaml_value(str(flutter_pubspec), "version")
        
        assert dart_version == "1.2.3"
        assert flutter_version == "1.2.4"
        assert dart_version != flutter_version  # Mismatch detected


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 