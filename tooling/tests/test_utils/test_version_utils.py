"""
Tests for version utility functions.
"""

import unittest
import tempfile
import json
from pathlib import Path

from tooling.utils.version_utils import (
    SemanticVersion, VersionComponent, VersionError, InvalidVersionError,
    VersionExtractor, VersionUpdater,
    parse_version, compare_versions, increment_version
)


class TestSemanticVersion(unittest.TestCase):
    """Test SemanticVersion class."""
    
    def test_parse_basic_version(self):
        """Test parsing basic version strings."""
        # With 'v' prefix
        version = SemanticVersion.parse("v1.2.3")
        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 2)
        self.assertEqual(version.patch, 3)
        self.assertEqual(version.prefix, "v")
        self.assertIsNone(version.prerelease)
        self.assertIsNone(version.build)
        
        # Without prefix
        version = SemanticVersion.parse("1.2.3")
        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 2)
        self.assertEqual(version.patch, 3)
        self.assertEqual(version.prefix, "")
    
    def test_parse_prerelease_version(self):
        """Test parsing version with prerelease."""
        version = SemanticVersion.parse("v1.2.3-beta.1")
        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 2)
        self.assertEqual(version.patch, 3)
        self.assertEqual(version.prerelease, "beta.1")
        self.assertIsNone(version.build)
    
    def test_parse_build_metadata(self):
        """Test parsing version with build metadata."""
        version = SemanticVersion.parse("v1.2.3+build.123")
        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 2)
        self.assertEqual(version.patch, 3)
        self.assertIsNone(version.prerelease)
        self.assertEqual(version.build, "build.123")
    
    def test_parse_full_version(self):
        """Test parsing version with all components."""
        version = SemanticVersion.parse("v1.2.3-rc.1+build.456")
        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 2)
        self.assertEqual(version.patch, 3)
        self.assertEqual(version.prerelease, "rc.1")
        self.assertEqual(version.build, "build.456")
    
    def test_parse_invalid_version(self):
        """Test parsing invalid version strings."""
        invalid_versions = [
            "1.2",  # Missing patch
            "1.2.3.4",  # Too many components
            "a.b.c",  # Non-numeric
            "1.2.3-",  # Empty prerelease
            "1.2.3+",  # Empty build
            ""  # Empty string
        ]
        
        for v in invalid_versions:
            with self.assertRaises(InvalidVersionError):
                SemanticVersion.parse(v)
    
    def test_from_tuple(self):
        """Test creating version from tuple."""
        version = SemanticVersion.from_tuple((1, 2, 3))
        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 2)
        self.assertEqual(version.patch, 3)
        self.assertEqual(version.prefix, "v")
        
        # Invalid tuple
        with self.assertRaises(InvalidVersionError):
            SemanticVersion.from_tuple((1, 2))
    
    def test_increment_operations(self):
        """Test version increment operations."""
        version = SemanticVersion.parse("v1.2.3")
        
        # Increment patch
        new_version = version.increment_patch()
        self.assertEqual(str(new_version), "v1.2.4")
        
        # Increment minor (resets patch)
        new_version = version.increment_minor()
        self.assertEqual(str(new_version), "v1.3.0")
        
        # Increment major (resets minor and patch)
        new_version = version.increment_major()
        self.assertEqual(str(new_version), "v2.0.0")
    
    def test_version_comparison(self):
        """Test version comparison operations."""
        v1 = SemanticVersion.parse("v1.2.3")
        v2 = SemanticVersion.parse("v1.2.4")
        v3 = SemanticVersion.parse("v1.3.0")
        v4 = SemanticVersion.parse("v2.0.0")
        
        # Less than
        self.assertTrue(v1 < v2)
        self.assertTrue(v2 < v3)
        self.assertTrue(v3 < v4)
        
        # Greater than
        self.assertTrue(v4 > v3)
        self.assertTrue(v3 > v2)
        self.assertTrue(v2 > v1)
        
        # Equal
        self.assertEqual(v1, SemanticVersion.parse("v1.2.3"))
        
        # Prerelease versions
        v_stable = SemanticVersion.parse("v1.2.3")
        v_pre = SemanticVersion.parse("v1.2.3-beta.1")
        
        # Stable version > prerelease version
        self.assertTrue(v_stable > v_pre)
        self.assertFalse(v_pre > v_stable)
    
    def test_to_string(self):
        """Test string conversion."""
        version = SemanticVersion(1, 2, 3, prerelease="beta.1", build="123", prefix="v")
        
        # With prefix
        self.assertEqual(version.to_string(include_prefix=True), "v1.2.3-beta.1+123")
        
        # Without prefix
        self.assertEqual(version.to_string(include_prefix=False), "1.2.3-beta.1+123")
        
        # __str__ method
        self.assertEqual(str(version), "v1.2.3-beta.1+123")


class TestVersionExtractor(unittest.TestCase):
    """Test VersionExtractor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.extractor = VersionExtractor()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_extract_from_json(self):
        """Test extracting version from JSON file."""
        json_file = Path(self.temp_dir) / "package.json"
        with open(json_file, 'w') as f:
            json.dump({"name": "test", "version": "1.2.3"}, f)
        
        version = self.extractor.extract_from_file(json_file)
        self.assertEqual(version, "1.2.3")
    
    def test_extract_from_toml(self):
        """Test extracting version from TOML file."""
        toml_file = Path(self.temp_dir) / "pyproject.toml"
        with open(toml_file, 'w') as f:
            f.write('[project]\nname = "test"\nversion = "1.2.3"\n')
        
        version = self.extractor.extract_from_file(toml_file)
        self.assertEqual(version, "1.2.3")
    
    def test_extract_from_yaml(self):
        """Test extracting version from YAML file."""
        yaml_file = Path(self.temp_dir) / "pubspec.yaml"
        with open(yaml_file, 'w') as f:
            f.write('name: test\nversion: 1.2.3\n')
        
        version = self.extractor.extract_from_file(yaml_file)
        self.assertEqual(version, "1.2.3")
    
    def test_extract_from_nonexistent_file(self):
        """Test extracting from non-existent file."""
        version = self.extractor.extract_from_file("nonexistent.json")
        self.assertIsNone(version)
    
    def test_extract_from_unsupported_file(self):
        """Test extracting from unsupported file type."""
        txt_file = Path(self.temp_dir) / "test.txt"
        with open(txt_file, 'w') as f:
            f.write("version: 1.2.3")
        
        version = self.extractor.extract_from_file(txt_file)
        self.assertIsNone(version)


class TestVersionUpdater(unittest.TestCase):
    """Test VersionUpdater class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.updater = VersionUpdater()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_update_json_version(self):
        """Test updating version in JSON file."""
        json_file = Path(self.temp_dir) / "package.json"
        with open(json_file, 'w') as f:
            json.dump({"name": "test", "version": "1.2.3"}, f)
        
        success = self.updater.update_version_in_file(json_file, "2.0.0", create_backup=False)
        self.assertTrue(success)
        
        # Verify update
        with open(json_file, 'r') as f:
            data = json.load(f)
            self.assertEqual(data['version'], "2.0.0")
    
    def test_update_with_backup(self):
        """Test updating version with backup creation."""
        json_file = Path(self.temp_dir) / "package.json"
        with open(json_file, 'w') as f:
            json.dump({"name": "test", "version": "1.2.3"}, f)
        
        success = self.updater.update_version_in_file(json_file, "2.0.0", create_backup=True)
        self.assertTrue(success)
        
        # Check backup exists
        backup_file = json_file.with_suffix('.json.bak')
        self.assertTrue(backup_file.exists())
        
        # Verify backup content
        with open(backup_file, 'r') as f:
            data = json.load(f)
            self.assertEqual(data['version'], "1.2.3")
    
    def test_update_nonexistent_file(self):
        """Test updating non-existent file."""
        success = self.updater.update_version_in_file("nonexistent.json", "2.0.0")
        self.assertFalse(success)


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions."""
    
    def test_parse_version(self):
        """Test parse_version function."""
        version = parse_version("v1.2.3")
        self.assertIsInstance(version, SemanticVersion)
        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 2)
        self.assertEqual(version.patch, 3)
    
    def test_compare_versions(self):
        """Test compare_versions function."""
        self.assertEqual(compare_versions("v1.2.3", "v1.2.3"), 0)
        self.assertEqual(compare_versions("v1.2.3", "v1.2.4"), -1)
        self.assertEqual(compare_versions("v1.2.4", "v1.2.3"), 1)
    
    def test_increment_version(self):
        """Test increment_version function."""
        # Default (patch)
        self.assertEqual(increment_version("v1.2.3"), "v1.2.4")
        
        # Minor
        self.assertEqual(
            increment_version("v1.2.3", VersionComponent.MINOR),
            "v1.3.0"
        )
        
        # Major
        self.assertEqual(
            increment_version("v1.2.3", VersionComponent.MAJOR),
            "v2.0.0"
        )


if __name__ == '__main__':
    unittest.main()