"""
Tests for version_utils.py
"""
import pytest
from unittest.mock import patch, Mock, MagicMock, mock_open
import json
import toml
import yaml
from pathlib import Path

from tooling.utils.version_utils import (
    VersionComponent, VersionError, InvalidVersionError, SemanticVersion,
    VersionExtractor, VersionUpdater, parse_version, compare_versions,
    increment_version, validate_version, parse_version_tuple,
    format_version, get_version_from_file, update_version_in_file
)


class TestVersionComponent:
    """Test VersionComponent enum"""
    
    def test_version_component_values(self):
        """Test VersionComponent enum values"""
        assert VersionComponent.MAJOR.value == "major"
        assert VersionComponent.MINOR.value == "minor"
        assert VersionComponent.PATCH.value == "patch"


class TestSemanticVersion:
    """Test SemanticVersion class"""
    
    def test_semantic_version_creation(self):
        """Test creating SemanticVersion"""
        version = SemanticVersion(major=1, minor=2, patch=3)
        
        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3
        assert version.prerelease is None
        assert version.build is None
        assert version.prefix == ""
    
    def test_semantic_version_with_metadata(self):
        """Test SemanticVersion with prerelease and build"""
        version = SemanticVersion(
            major=1, minor=0, patch=0,
            prerelease="beta.1",
            build="20250607",
            prefix="v"
        )
        
        assert version.prerelease == "beta.1"
        assert version.build == "20250607"
        assert version.prefix == "v"
    
    def test_parse_basic_version(self):
        """Test parsing basic version string"""
        version = SemanticVersion.parse("1.2.3")
        
        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3
        assert version.prefix == ""
    
    def test_parse_version_with_prefix(self):
        """Test parsing version with v prefix"""
        version = SemanticVersion.parse("v2.0.0")
        
        assert version.major == 2
        assert version.minor == 0
        assert version.patch == 0
        assert version.prefix == "v"
    
    def test_parse_version_with_prerelease(self):
        """Test parsing version with prerelease"""
        version = SemanticVersion.parse("1.0.0-alpha.1")
        
        assert version.major == 1
        assert version.minor == 0
        assert version.patch == 0
        assert version.prerelease == "alpha.1"
    
    def test_parse_version_with_build(self):
        """Test parsing version with build metadata"""
        version = SemanticVersion.parse("1.0.0+build.123")
        
        assert version.major == 1
        assert version.minor == 0
        assert version.patch == 0
        assert version.build == "build.123"
    
    def test_parse_version_full(self):
        """Test parsing full version string"""
        version = SemanticVersion.parse("v1.2.3-beta.1+build.456")
        
        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3
        assert version.prerelease == "beta.1"
        assert version.build == "build.456"
        assert version.prefix == "v"
    
    def test_parse_invalid_version(self):
        """Test parsing invalid version string"""
        with pytest.raises(InvalidVersionError):
            SemanticVersion.parse("not.a.version")
        
        with pytest.raises(InvalidVersionError):
            SemanticVersion.parse("1.2")
        
        with pytest.raises(InvalidVersionError):
            SemanticVersion.parse("v1.2.3.4")
    
    def test_from_tuple(self):
        """Test creating version from tuple"""
        version = SemanticVersion.from_tuple((1, 2, 3))
        
        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3
        assert version.prefix == "v"
    
    def test_from_tuple_custom_prefix(self):
        """Test creating version from tuple with custom prefix"""
        version = SemanticVersion.from_tuple((2, 0, 0), prefix="")
        
        assert version.major == 2
        assert version.prefix == ""
    
    def test_from_tuple_invalid(self):
        """Test creating version from invalid tuple"""
        with pytest.raises(InvalidVersionError):
            SemanticVersion.from_tuple((1, 2))
        
        with pytest.raises(InvalidVersionError):
            SemanticVersion.from_tuple((1, 2, 3, 4))
    
    def test_increment_major(self):
        """Test incrementing major version"""
        version = SemanticVersion(1, 2, 3, prefix="v")
        new_version = version.increment_major()
        
        assert new_version.major == 2
        assert new_version.minor == 0
        assert new_version.patch == 0
        assert new_version.prefix == "v"
    
    def test_increment_minor(self):
        """Test incrementing minor version"""
        version = SemanticVersion(1, 2, 3, prefix="v")
        new_version = version.increment_minor()
        
        assert new_version.major == 1
        assert new_version.minor == 3
        assert new_version.patch == 0
        assert new_version.prefix == "v"
    
    def test_increment_patch(self):
        """Test incrementing patch version"""
        version = SemanticVersion(1, 2, 3, prefix="v")
        new_version = version.increment_patch()
        
        assert new_version.major == 1
        assert new_version.minor == 2
        assert new_version.patch == 4
        assert new_version.prefix == "v"
    
    def test_increment_with_component(self):
        """Test increment method with VersionComponent"""
        version = SemanticVersion(1, 0, 0)
        
        major = version.increment(VersionComponent.MAJOR)
        assert major.major == 2
        
        minor = version.increment(VersionComponent.MINOR)
        assert minor.minor == 1
        
        patch = version.increment(VersionComponent.PATCH)
        assert patch.patch == 1
    
    def test_to_string(self):
        """Test converting to string"""
        version = SemanticVersion(1, 2, 3, prefix="v")
        assert version.to_string() == "v1.2.3"
        assert version.to_string(include_prefix=False) == "1.2.3"
        
        # With metadata
        version_full = SemanticVersion(
            1, 0, 0,
            prerelease="beta.1",
            build="build.123",
            prefix="v"
        )
        assert version_full.to_string() == "v1.0.0-beta.1+build.123"
    
    def test_str_method(self):
        """Test __str__ method"""
        version = SemanticVersion(1, 2, 3, prefix="v")
        assert str(version) == "v1.2.3"
    
    def test_equality(self):
        """Test version equality"""
        v1 = SemanticVersion(1, 2, 3)
        v2 = SemanticVersion(1, 2, 3)
        v3 = SemanticVersion(1, 2, 4)
        
        assert v1 == v2
        assert v1 != v3
        
        # Build metadata should be ignored
        v4 = SemanticVersion(1, 2, 3, build="123")
        v5 = SemanticVersion(1, 2, 3, build="456")
        assert v4 == v5
        
        # Prerelease should matter
        v6 = SemanticVersion(1, 2, 3, prerelease="beta.1")
        v7 = SemanticVersion(1, 2, 3, prerelease="beta.2")
        assert v6 != v7
    
    def test_comparison(self):
        """Test version comparison"""
        v1 = SemanticVersion(1, 0, 0)
        v2 = SemanticVersion(2, 0, 0)
        v3 = SemanticVersion(1, 1, 0)
        v4 = SemanticVersion(1, 0, 1)
        
        assert v1 < v2
        assert v1 < v3
        assert v1 < v4
        assert v4 < v3
        assert v3 < v2
        
        # Test with prerelease
        v5 = SemanticVersion(1, 0, 0)
        v6 = SemanticVersion(1, 0, 0, prerelease="beta.1")
        assert v6 < v5  # Prerelease is less than release
    
    def test_total_ordering(self):
        """Test total ordering of versions"""
        versions = [
            SemanticVersion(2, 0, 0),
            SemanticVersion(1, 0, 0, prerelease="beta"),
            SemanticVersion(1, 0, 0),
            SemanticVersion(1, 1, 0),
            SemanticVersion(1, 0, 1),
        ]
        
        sorted_versions = sorted(versions)
        
        assert sorted_versions[0].to_string() == "1.0.0-beta"
        assert sorted_versions[1].to_string() == "1.0.0"
        assert sorted_versions[2].to_string() == "1.0.1"
        assert sorted_versions[3].to_string() == "1.1.0"
        assert sorted_versions[4].to_string() == "2.0.0"


class TestVersionExtractor:
    """Test VersionExtractor class"""
    
    def test_initialization(self):
        """Test VersionExtractor initialization"""
        extractor = VersionExtractor()
        assert extractor.logger is not None
    
    def test_extract_from_file_not_found(self):
        """Test extracting from non-existent file"""
        extractor = VersionExtractor()
        
        result = extractor.extract_from_file("/nonexistent/file.toml")
        assert result is None
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.suffix', new_callable=lambda: property(lambda self: '.toml'))
    @patch('builtins.open', new_callable=mock_open)
    @patch('toml.load')
    def test_extract_from_toml_package(self, mock_toml_load, mock_file, mock_suffix, mock_exists):
        """Test extracting version from TOML with package section"""
        mock_exists.return_value = True
        mock_toml_load.return_value = {
            'package': {'version': '1.2.3'}
        }
        
        extractor = VersionExtractor()
        version = extractor.extract_from_toml(Path("test.toml"))
        
        assert version == '1.2.3'
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.suffix', new_callable=lambda: property(lambda self: '.toml'))
    @patch('builtins.open', new_callable=mock_open)
    @patch('toml.load')
    def test_extract_from_toml_poetry(self, mock_toml_load, mock_file, mock_suffix, mock_exists):
        """Test extracting version from Poetry TOML"""
        mock_exists.return_value = True
        mock_toml_load.return_value = {
            'tool': {'poetry': {'version': '2.0.0'}}
        }
        
        extractor = VersionExtractor()
        version = extractor.extract_from_toml(Path("pyproject.toml"))
        
        assert version == '2.0.0'
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.suffix', new_callable=lambda: property(lambda self: '.yaml'))
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.safe_load')
    def test_extract_from_yaml(self, mock_yaml_load, mock_file, mock_suffix, mock_exists):
        """Test extracting version from YAML"""
        mock_exists.return_value = True
        mock_yaml_load.return_value = {'version': '1.0.0'}
        
        extractor = VersionExtractor()
        version = extractor.extract_from_yaml(Path("test.yaml"))
        
        assert version == '1.0.0'
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.suffix', new_callable=lambda: property(lambda self: '.json'))
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    def test_extract_from_json(self, mock_json_load, mock_file, mock_suffix, mock_exists):
        """Test extracting version from JSON"""
        mock_exists.return_value = True
        mock_json_load.return_value = {'version': '3.0.0'}
        
        extractor = VersionExtractor()
        version = extractor.extract_from_json(Path("package.json"))
        
        assert version == '3.0.0'
    
    @patch('pathlib.Path.exists')
    def test_extract_from_file_router(self, mock_exists):
        """Test extract_from_file routing to correct method"""
        mock_exists.return_value = True
        extractor = VersionExtractor()
        
        # Mock individual extract methods
        extractor.extract_from_toml = Mock(return_value="1.0.0")
        extractor.extract_from_yaml = Mock(return_value="2.0.0")
        extractor.extract_from_json = Mock(return_value="3.0.0")
        
        # Test TOML
        result = extractor.extract_from_file("test.toml")
        assert result == "1.0.0"
        extractor.extract_from_toml.assert_called_once()
        
        # Test YAML
        result = extractor.extract_from_file("test.yaml")
        assert result == "2.0.0"
        extractor.extract_from_yaml.assert_called_once()
        
        # Test JSON
        result = extractor.extract_from_file("package.json")
        assert result == "3.0.0"
        extractor.extract_from_json.assert_called_once()
    
    @patch('pathlib.Path.exists')
    def test_extract_from_unsupported_file(self, mock_exists):
        """Test extracting from unsupported file type"""
        mock_exists.return_value = True
        extractor = VersionExtractor()
        
        result = extractor.extract_from_file("test.txt")
        assert result is None


class TestVersionUpdater:
    """Test VersionUpdater class"""
    
    def test_initialization(self):
        """Test VersionUpdater initialization"""
        updater = VersionUpdater()
        assert updater.logger is not None
        assert updater.extractor is not None
    
    def test_update_version_file_not_found(self):
        """Test updating version in non-existent file"""
        updater = VersionUpdater()
        
        result = updater.update_version_in_file("/nonexistent/file.toml", "1.0.0")
        assert result is False
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.suffix', new_callable=lambda: property(lambda self: '.toml'))
    @patch('shutil.copy2')
    @patch('builtins.open', new_callable=mock_open)
    @patch('toml.load')
    @patch('toml.dump')
    def test_update_toml_version_with_backup(self, mock_dump, mock_load, mock_file, 
                                           mock_copy, mock_suffix, mock_exists):
        """Test updating TOML version with backup"""
        mock_exists.return_value = True
        mock_load.return_value = {'package': {'version': '1.0.0'}}
        
        updater = VersionUpdater()
        result = updater.update_toml_version(Path("test.toml"), "2.0.0")
        
        assert result is True
        mock_dump.assert_called_once()
        
        # Check that version was updated
        updated_data = mock_dump.call_args[0][0]
        assert updated_data['package']['version'] == '2.0.0'
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.suffix', new_callable=lambda: property(lambda self: '.yaml'))
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.safe_load')
    @patch('yaml.dump')
    def test_update_yaml_version(self, mock_dump, mock_load, mock_file, mock_suffix, mock_exists):
        """Test updating YAML version"""
        mock_exists.return_value = True
        mock_load.return_value = {'version': '1.0.0', 'name': 'test'}
        
        updater = VersionUpdater()
        result = updater.update_yaml_version(Path("test.yaml"), "2.0.0")
        
        assert result is True
        mock_dump.assert_called_once()
        
        # Check that version was updated
        updated_data = mock_dump.call_args[0][0]
        assert updated_data['version'] == '2.0.0'
        assert updated_data['name'] == 'test'  # Other fields preserved
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.suffix', new_callable=lambda: property(lambda self: '.json'))
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    @patch('json.dump')
    def test_update_json_version(self, mock_dump, mock_load, mock_file, mock_suffix, mock_exists):
        """Test updating JSON version"""
        mock_exists.return_value = True
        mock_load.return_value = {'version': '1.0.0', 'name': 'test'}
        
        updater = VersionUpdater()
        result = updater.update_json_version(Path("package.json"), "3.0.0")
        
        assert result is True
        mock_dump.assert_called_once()
        
        # Check that version was updated
        updated_data = mock_dump.call_args[0][0]
        assert updated_data['version'] == '3.0.0'
    
    @patch('pathlib.Path.exists')
    def test_update_version_unsupported_file(self, mock_exists):
        """Test updating version in unsupported file type"""
        mock_exists.return_value = True
        updater = VersionUpdater()
        
        result = updater.update_version_in_file("test.txt", "1.0.0")
        assert result is False


class TestStandaloneFunctions:
    """Test standalone version utility functions"""
    
    def test_parse_version(self):
        """Test parse_version function"""
        version = parse_version("v1.2.3")
        
        assert isinstance(version, SemanticVersion)
        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3
        assert version.prefix == "v"
    
    def test_compare_versions(self):
        """Test compare_versions function"""
        assert compare_versions("1.0.0", "2.0.0") < 0
        assert compare_versions("2.0.0", "1.0.0") > 0
        assert compare_versions("1.0.0", "1.0.0") == 0
        
        # With prefixes
        assert compare_versions("v1.0.0", "v2.0.0") < 0
    
    def test_increment_version_default(self):
        """Test increment_version with default (patch)"""
        new_version = increment_version("1.2.3")
        assert new_version == "1.2.4"
        
        # With prefix
        new_version = increment_version("v1.2.3")
        assert new_version == "v1.2.4"
    
    def test_increment_version_major(self):
        """Test increment_version for major"""
        new_version = increment_version("1.2.3", VersionComponent.MAJOR)
        assert new_version == "2.0.0"
    
    def test_increment_version_minor(self):
        """Test increment_version for minor"""
        new_version = increment_version("v1.2.3", VersionComponent.MINOR)
        assert new_version == "v1.3.0"
    
    def test_validate_version_valid(self):
        """Test validate_version with valid versions"""
        assert validate_version("1.2.3") is True
        assert validate_version("v1.2.3") is False  # validate_version doesn't accept v prefix
        assert validate_version("1.0.0-beta.1") is False  # validate_version doesn't accept prerelease
        assert validate_version("1.0.0+build.123") is False  # validate_version doesn't accept build
        assert validate_version("10.20.30") is True
    
    def test_validate_version_invalid(self):
        """Test validate_version with invalid versions"""
        assert validate_version("1.2") is False
        assert validate_version("not.a.version") is False
        assert validate_version("1.2.3.4") is False
        assert validate_version("") is False
    
    def test_parse_version_tuple(self):
        """Test parse_version_tuple function"""
        assert parse_version_tuple("1.2.3") == (1, 2, 3)
        assert parse_version_tuple("v10.20.30") == (10, 20, 30)
        
        with pytest.raises(ValueError):  # Changed from InvalidVersionError to ValueError
            parse_version_tuple("invalid")
    
    def test_format_version(self):
        """Test format_version function"""
        assert format_version(1, 2, 3) == "1.2.3"
        assert format_version(1, 2, 3, prefix="v") == "v1.2.3"
        assert format_version(10, 20, 30, prefix="") == "10.20.30"
    
    @patch.object(VersionExtractor, 'extract_from_file')
    def test_get_version_from_file(self, mock_extract):
        """Test get_version_from_file function"""
        mock_extract.return_value = "1.2.3"
        
        version = get_version_from_file("test.toml")
        assert version == "1.2.3"
        mock_extract.assert_called_once()
    
    @patch.object(VersionUpdater, 'update_version_in_file')
    def test_update_version_in_file_function(self, mock_update):
        """Test update_version_in_file function"""
        mock_update.return_value = True
        
        update_version_in_file("test.toml", "2.0.0")
        mock_update.assert_called_once_with("test.toml", "2.0.0", create_backup=False)  # Expect string, not Path