"""
Tests for file_utils.py
"""
import pytest
from unittest.mock import patch, mock_open, Mock, MagicMock, call
import os
import tempfile
from pathlib import Path
import shutil

from tooling.utils.file_utils import (
    extract_yaml_value, extract_toml_value, update_version_in_file,
    extract_changelog_section, cleanup_temp_files, ensure_executable,
    update_all_versions, update_yaml_version, find_files_by_pattern
)


class TestFileUtils:
    """Test file utility functions"""
    
    def test_extract_yaml_value_found(self, tmp_path):
        """Test extracting value from YAML file"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("""
name: test-package
version: 1.2.3
description: A test package
""")
        
        assert extract_yaml_value(str(yaml_file), "version") == "1.2.3"
        assert extract_yaml_value(str(yaml_file), "name") == "test-package"
    
    def test_extract_yaml_value_with_quotes(self, tmp_path):
        """Test extracting quoted value from YAML"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text('version: "1.2.3"\nname: \'test\'')
        
        assert extract_yaml_value(str(yaml_file), "version") == "1.2.3"
        assert extract_yaml_value(str(yaml_file), "name") == "test"
    
    def test_extract_yaml_value_not_found(self, tmp_path):
        """Test extracting non-existent key from YAML"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("name: test")
        
        assert extract_yaml_value(str(yaml_file), "version") is None
    
    def test_extract_yaml_value_file_not_found(self):
        """Test extracting from non-existent YAML file"""
        assert extract_yaml_value("/nonexistent/file.yaml", "version") is None
    
    def test_extract_yaml_value_empty_value(self, tmp_path):
        """Test extracting empty value from YAML"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("version:\nname: test")
        
        assert extract_yaml_value(str(yaml_file), "version") is None
    
    def test_extract_toml_value_found(self, tmp_path):
        """Test extracting value from TOML file"""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text('''
[package]
name = "test-package"
version = "1.2.3"
''')
        
        assert extract_toml_value(str(toml_file), "version") == "1.2.3"
        assert extract_toml_value(str(toml_file), "name") == "test-package"
    
    def test_extract_toml_value_not_found(self, tmp_path):
        """Test extracting non-existent key from TOML"""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text('[package]\nname = "test"')
        
        assert extract_toml_value(str(toml_file), "version") is None
    
    def test_extract_toml_value_file_not_found(self):
        """Test extracting from non-existent TOML file"""
        assert extract_toml_value("/nonexistent/file.toml", "version") is None
    
    def test_update_version_in_yaml_file(self, tmp_path):
        """Test updating version in YAML file"""
        yaml_file = tmp_path / "pubspec.yaml"
        yaml_file.write_text("name: test\nversion: 1.0.0\ndescription: test")
        
        assert update_version_in_file(str(yaml_file), "2.0.0", "yaml") is True
        
        # Verify update
        content = yaml_file.read_text()
        assert "version: 2.0.0" in content
        assert "version: 1.0.0" not in content
    
    def test_update_version_in_toml_file(self, tmp_path):
        """Test updating version in TOML file"""
        toml_file = tmp_path / "Cargo.toml"
        toml_file.write_text('[package]\nname = "test"\nversion = "1.0.0"')
        
        assert update_version_in_file(str(toml_file), "2.0.0", "toml") is True
        
        # Verify update
        content = toml_file.read_text()
        assert 'version = "2.0.0"' in content
        assert 'version = "1.0.0"' not in content
    
    def test_update_version_in_dart_file(self, tmp_path):
        """Test updating version in Dart file"""
        dart_file = tmp_path / "cargo.dart"
        dart_file.write_text("const String CARGO_VERSION = '1.0.0';")
        
        assert update_version_in_file(str(dart_file), "2.0.0", "dart") is True
        
        # Verify update
        content = dart_file.read_text()
        assert "const String CARGO_VERSION = '2.0.0'" in content
        assert "const String CARGO_VERSION = '1.0.0'" not in content
    
    def test_update_version_file_not_found(self):
        """Test updating version in non-existent file"""
        assert update_version_in_file("/nonexistent/file.yaml", "1.0.0", "yaml") is False
    
    def test_update_version_invalid_type(self, tmp_path):
        """Test updating version with invalid file type"""
        file_path = tmp_path / "test.txt"
        file_path.write_text("version: 1.0.0")
        
        assert update_version_in_file(str(file_path), "2.0.0", "invalid") is False
    
    @patch('shutil.move')
    def test_update_version_rollback_on_error(self, mock_move, tmp_path):
        """Test rollback on update error"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("version: 1.0.0")
        
        # Mock extract_yaml_value to return wrong version after update
        with patch('tooling.utils.file_utils.extract_yaml_value', return_value="1.0.0"):
            assert update_version_in_file(str(yaml_file), "2.0.0", "yaml") is False
            
        # Should have tried to restore backup
        mock_move.assert_called_once()
    
    def test_extract_changelog_section_found(self, tmp_path):
        """Test extracting changelog section"""
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text("""# Changelog

## [v1.2.0] - 2025-06-07

### Added
- New feature

### Fixed
- Bug fix

## [v1.1.0] - 2025-06-06

### Changed
- Something changed
""")
        
        section = extract_changelog_section(str(changelog), "1.2.0")
        assert "### Added" in section
        assert "New feature" in section
        assert "### Fixed" in section
        assert "Bug fix" in section
        assert "Something changed" not in section
    
    def test_extract_changelog_section_with_v_prefix(self, tmp_path):
        """Test extracting changelog section with v prefix"""
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text("## [v1.0.0]\n\nContent")
        
        # Should work with or without v prefix
        assert extract_changelog_section(str(changelog), "v1.0.0") == "Content"
        assert extract_changelog_section(str(changelog), "1.0.0") == "Content"
    
    def test_extract_changelog_section_not_found(self, tmp_path):
        """Test extracting non-existent changelog section"""
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text("## [v1.0.0]\n\nContent")
        
        assert extract_changelog_section(str(changelog), "2.0.0") == ""
    
    def test_extract_changelog_section_file_not_found(self):
        """Test extracting from non-existent changelog"""
        assert extract_changelog_section("/nonexistent/CHANGELOG.md", "1.0.0") == ""
    
    def test_cleanup_temp_files(self, tmp_path):
        """Test cleaning up temp files"""
        with patch('tempfile.gettempdir', return_value=str(tmp_path)):
            # Create test temp files
            (tmp_path / "smart_commit_test.tmp").touch()
            (tmp_path / "sync_changelog_test.tmp").touch()
            (tmp_path / "prepare_patch_test.tmp").touch()
            (tmp_path / "other_file.tmp").touch()
            
            cleanup_temp_files()
            
            # Check that pattern files were deleted
            assert not (tmp_path / "smart_commit_test.tmp").exists()
            assert not (tmp_path / "sync_changelog_test.tmp").exists()
            assert not (tmp_path / "prepare_patch_test.tmp").exists()
            # Other files should remain
            assert (tmp_path / "other_file.tmp").exists()
    
    def test_cleanup_temp_files_error_handling(self, tmp_path):
        """Test cleanup handles errors gracefully"""
        with patch('tempfile.gettempdir', return_value=str(tmp_path)):
            # Create a file and make it unremovable
            temp_file = tmp_path / "smart_commit_test.tmp"
            temp_file.touch()
            
            with patch.object(Path, 'unlink', side_effect=PermissionError):
                # Should not raise exception
                cleanup_temp_files()
    
    def test_ensure_executable_makes_executable(self, tmp_path):
        """Test making file executable"""
        script = tmp_path / "script.sh"
        script.write_text("#!/bin/bash\necho test")
        script.chmod(0o644)  # Not executable
        
        ensure_executable(str(script))
        
        # Check it's now executable
        assert os.access(script, os.X_OK)
    
    def test_ensure_executable_already_executable(self, tmp_path):
        """Test ensure_executable on already executable file"""
        script = tmp_path / "script.sh"
        script.write_text("#!/bin/bash\necho test")
        script.chmod(0o755)  # Already executable
        
        # Should not raise error
        ensure_executable(str(script))
        assert os.access(script, os.X_OK)
    
    def test_ensure_executable_nonexistent_file(self):
        """Test ensure_executable on non-existent file"""
        # Should not raise error
        ensure_executable("/nonexistent/script.sh")
    
    @patch('tooling.utils.file_utils.update_version_in_file')
    @patch('builtins.print')
    def test_update_all_versions_success(self, mock_print, mock_update):
        """Test updating all versions successfully"""
        mock_update.return_value = True
        
        assert update_all_versions("2.0.0") is True
        
        # Should have updated dart, flutter, and rust
        assert mock_update.call_count >= 3
        
        # Check success messages printed
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any("✓" in call for call in print_calls)
    
    @patch('tooling.utils.file_utils.update_version_in_file')
    @patch('builtins.print')
    def test_update_all_versions_partial_failure(self, mock_print, mock_update):
        """Test updating versions with some failures"""
        # First succeeds, second fails, rest succeed
        mock_update.side_effect = [True, False, True, True]
        
        assert update_all_versions("2.0.0") is False
        
        # Check failure message printed
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any("✗" in call for call in print_calls)
    
    @patch('tooling.utils.file_utils.update_version_in_file')
    def test_update_all_versions_with_cargo_dart(self, mock_update):
        """Test updating versions including cargo.dart when both exist"""
        mock_update.return_value = True
        
        # Mock Path.exists to return True for cargo.dart check
        with patch('pathlib.Path.exists', return_value=True):
            update_all_versions("2.0.0")
        
        # Should update cargo.dart as well (4 calls total)
        assert mock_update.call_count == 4
    
    def test_update_yaml_version(self, tmp_path):
        """Test update_yaml_version wrapper function"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("version: 1.0.0")
        
        assert update_yaml_version(str(yaml_file), "2.0.0") is True
        assert "version: 2.0.0" in yaml_file.read_text()
    
    def test_find_files_by_pattern_simple(self, tmp_path):
        """Test finding files with simple pattern"""
        # Create test files
        (tmp_path / "test1.py").touch()
        (tmp_path / "test2.py").touch()
        (tmp_path / "test.txt").touch()
        
        files = find_files_by_pattern("*.py", tmp_path)
        assert len(files) == 2
        assert all(f.endswith(".py") for f in files)
    
    def test_find_files_by_pattern_recursive(self, tmp_path):
        """Test finding files with recursive pattern"""
        # Create nested structure
        (tmp_path / "dir1").mkdir()
        (tmp_path / "dir1" / "CHANGELOG.md").touch()
        (tmp_path / "dir2").mkdir()
        (tmp_path / "dir2" / "CHANGELOG.md").touch()
        (tmp_path / "CHANGELOG.md").touch()
        
        files = find_files_by_pattern("**/CHANGELOG.md", tmp_path)
        assert len(files) == 3
    
    def test_find_files_by_pattern_excludes_hidden(self, tmp_path):
        """Test finding files excludes hidden files"""
        (tmp_path / "test.py").touch()
        (tmp_path / ".hidden.py").touch()
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "test.py").touch()
        
        files = find_files_by_pattern("*.py", tmp_path)
        assert len(files) == 1
        assert files[0].endswith("test.py")
    
    def test_find_files_by_pattern_excludes_ignored_dirs(self, tmp_path):
        """Test finding files excludes ignored directories"""
        (tmp_path / "test.py").touch()
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "test.py").touch()
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "test.py").touch()
        
        files = find_files_by_pattern("**/*.py", tmp_path)
        assert len(files) == 1
        assert "node_modules" not in files[0]
        assert "__pycache__" not in files[0]
    
    def test_find_files_by_pattern_default_root(self):
        """Test finding files with default root directory"""
        with patch('pathlib.Path.cwd') as mock_cwd:
            mock_path = Mock()
            mock_path.glob.return_value = []
            mock_cwd.return_value = mock_path
            
            find_files_by_pattern("*.py")
            mock_path.glob.assert_called_once_with("*.py") 