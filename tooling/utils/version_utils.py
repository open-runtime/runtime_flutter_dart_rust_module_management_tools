"""
Version handling utilities for semantic versioning.

This module provides functions for parsing, comparing, and manipulating
version strings, as well as extracting and updating versions in various
file formats.

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved
"""

import re
import json
import toml
import yaml
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, Union
from dataclasses import dataclass
from functools import total_ordering
from enum import Enum

from tooling.core.logging import get_logger


class VersionComponent(Enum):
    """Version component to increment."""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


class VersionError(Exception):
    """Base exception for version operations."""
    pass


class InvalidVersionError(VersionError):
    """Raised when a version string is invalid."""
    pass


@dataclass
@total_ordering
class SemanticVersion:
    """
    Represents a semantic version with comparison support.
    
    Follows Semantic Versioning 2.0.0 specification.
    """
    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None
    build: Optional[str] = None
    prefix: str = ""
    
    # Regex pattern for semantic version
    PATTERN = re.compile(
        r'^(v)?'  # Optional 'v' prefix
        r'(\d+)\.(\d+)\.(\d+)'  # Major.Minor.Patch
        r'(?:-([0-9A-Za-z\-\.]+))?'  # Optional prerelease
        r'(?:\+([0-9A-Za-z\-\.]+))?$'  # Optional build metadata
    )
    
    @classmethod
    def parse(cls, version_str: str) -> 'SemanticVersion':
        """
        Parse a version string into SemanticVersion object.
        
        Args:
            version_str: Version string (e.g., "v1.2.3", "1.2.3-beta.1+build.123")
            
        Returns:
            SemanticVersion object
            
        Raises:
            InvalidVersionError: If version string is invalid
        """
        version_str = version_str.strip()
        match = cls.PATTERN.match(version_str)
        
        if not match:
            raise InvalidVersionError(f"Invalid semantic version: {version_str}")
            
        prefix = match.group(1) or ""
        major = int(match.group(2))
        minor = int(match.group(3))
        patch = int(match.group(4))
        prerelease = match.group(5)
        build = match.group(6)
        
        return cls(
            major=major,
            minor=minor,
            patch=patch,
            prerelease=prerelease,
            build=build,
            prefix=prefix
        )
    
    @classmethod
    def from_tuple(cls, version_tuple: Tuple[int, int, int], prefix: str = "v") -> 'SemanticVersion':
        """
        Create SemanticVersion from tuple.
        
        Args:
            version_tuple: (major, minor, patch) tuple
            prefix: Version prefix (default: "v")
            
        Returns:
            SemanticVersion object
        """
        if len(version_tuple) != 3:
            raise InvalidVersionError("Version tuple must have exactly 3 components")
            
        return cls(
            major=version_tuple[0],
            minor=version_tuple[1],
            patch=version_tuple[2],
            prefix=prefix
        )
    
    def increment(self, component: VersionComponent) -> 'SemanticVersion':
        """
        Return a new version with specified component incremented.
        
        Args:
            component: Which component to increment
            
        Returns:
            New SemanticVersion object
        """
        if component == VersionComponent.MAJOR:
            return SemanticVersion(
                major=self.major + 1,
                minor=0,
                patch=0,
                prefix=self.prefix
            )
        elif component == VersionComponent.MINOR:
            return SemanticVersion(
                major=self.major,
                minor=self.minor + 1,
                patch=0,
                prefix=self.prefix
            )
        elif component == VersionComponent.PATCH:
            return SemanticVersion(
                major=self.major,
                minor=self.minor,
                patch=self.patch + 1,
                prefix=self.prefix
            )
        else:
            raise ValueError(f"Invalid version component: {component}")
    
    def increment_major(self) -> 'SemanticVersion':
        """Return a new version with incremented major number."""
        return self.increment(VersionComponent.MAJOR)
    
    def increment_minor(self) -> 'SemanticVersion':
        """Return a new version with incremented minor number."""
        return self.increment(VersionComponent.MINOR)
    
    def increment_patch(self) -> 'SemanticVersion':
        """Return a new version with incremented patch number."""
        return self.increment(VersionComponent.PATCH)
    
    def to_string(self, include_prefix: bool = True) -> str:
        """
        Convert to string representation.
        
        Args:
            include_prefix: Whether to include the prefix (e.g., 'v')
            
        Returns:
            Version string
        """
        prefix = self.prefix if include_prefix else ""
        version = f"{prefix}{self.major}.{self.minor}.{self.patch}"
        
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.build:
            version += f"+{self.build}"
            
        return version
    
    def __str__(self) -> str:
        """String representation of the version."""
        return self.to_string()
    
    def __eq__(self, other) -> bool:
        """Equality comparison (ignores build metadata)."""
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        return (
            self.major == other.major and
            self.minor == other.minor and
            self.patch == other.patch and
            self.prerelease == other.prerelease
        )
    
    def __lt__(self, other) -> bool:
        """Less than comparison for sorting."""
        if not isinstance(other, SemanticVersion):
            return NotImplemented
            
        # Compare major, minor, patch
        if (self.major, self.minor, self.patch) != (other.major, other.minor, other.patch):
            return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
        
        # Handle prerelease versions
        # Version without prerelease > version with prerelease
        if self.prerelease is None and other.prerelease is not None:
            return False
        if self.prerelease is not None and other.prerelease is None:
            return True
        
        # Compare prerelease versions lexically
        if self.prerelease and other.prerelease:
            return self.prerelease < other.prerelease
            
        return False


class VersionExtractor:
    """Extracts version information from various file formats."""
    
    def __init__(self, logger=None):
        """Initialize VersionExtractor."""
        self.logger = logger or get_logger("version_utils")
    
    def extract_from_file(self, filepath: Union[str, Path]) -> Optional[str]:
        """
        Extract version from a file based on its type.
        
        Args:
            filepath: Path to the file
            
        Returns:
            Version string or None if not found
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            self.logger.warning("File not found", filepath=str(filepath))
            return None
            
        suffix = filepath.suffix.lower()
        
        if suffix == '.toml':
            return self.extract_from_toml(filepath)
        elif suffix in ['.yaml', '.yml']:
            return self.extract_from_yaml(filepath)
        elif suffix == '.json':
            return self.extract_from_json(filepath)
        elif filepath.name == 'pubspec.yaml':
            return self.extract_from_pubspec(filepath)
        elif filepath.name == 'Cargo.toml':
            return self.extract_from_cargo_toml(filepath)
        elif filepath.name == 'package.json':
            return self.extract_from_package_json(filepath)
        else:
            self.logger.warning("Unsupported file type", filepath=str(filepath))
            return None
    
    def extract_from_toml(self, filepath: Path) -> Optional[str]:
        """Extract version from TOML file."""
        try:
            with open(filepath, 'r') as f:
                data = toml.load(f)
                
            # Check common locations
            if 'package' in data and 'version' in data['package']:
                return data['package']['version']
            if 'tool' in data and 'poetry' in data['tool'] and 'version' in data['tool']['poetry']:
                return data['tool']['poetry']['version']
            if 'project' in data and 'version' in data['project']:
                return data['project']['version']
            if 'version' in data:
                return data['version']
                
            self.logger.debug("No version found in TOML", filepath=str(filepath))
            return None
            
        except Exception as e:
            self.logger.error("Error reading TOML file", filepath=str(filepath), error=str(e))
            return None
    
    def extract_from_yaml(self, filepath: Path) -> Optional[str]:
        """Extract version from YAML file."""
        try:
            with open(filepath, 'r') as f:
                data = yaml.safe_load(f)
                
            if data and 'version' in data:
                return str(data['version'])
                
            self.logger.debug("No version found in YAML", filepath=str(filepath))
            return None
            
        except Exception as e:
            self.logger.error("Error reading YAML file", filepath=str(filepath), error=str(e))
            return None
    
    def extract_from_json(self, filepath: Path) -> Optional[str]:
        """Extract version from JSON file."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                
            if 'version' in data:
                return data['version']
                
            self.logger.debug("No version found in JSON", filepath=str(filepath))
            return None
            
        except Exception as e:
            self.logger.error("Error reading JSON file", filepath=str(filepath), error=str(e))
            return None
    
    def extract_from_pubspec(self, filepath: Path) -> Optional[str]:
        """Extract version from pubspec.yaml."""
        return self.extract_from_yaml(filepath)
    
    def extract_from_cargo_toml(self, filepath: Path) -> Optional[str]:
        """Extract version from Cargo.toml."""
        try:
            with open(filepath, 'r') as f:
                data = toml.load(f)
                
            if 'package' in data and 'version' in data['package']:
                return data['package']['version']
                
            return None
            
        except Exception as e:
            self.logger.error("Error reading Cargo.toml", filepath=str(filepath), error=str(e))
            return None
    
    def extract_from_package_json(self, filepath: Path) -> Optional[str]:
        """Extract version from package.json."""
        return self.extract_from_json(filepath)


class VersionUpdater:
    """Updates version information in various file formats."""
    
    def __init__(self, logger=None):
        """Initialize VersionUpdater."""
        self.logger = logger or get_logger("version_utils")
        self.extractor = VersionExtractor(logger)
    
    def update_version_in_file(
        self,
        filepath: Union[str, Path],
        new_version: str,
        create_backup: bool = True
    ) -> bool:
        """
        Update version in a file.
        
        Args:
            filepath: Path to the file
            new_version: New version string
            create_backup: Whether to create a backup file
            
        Returns:
            True if successful, False otherwise
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            self.logger.error("File not found", filepath=str(filepath))
            return False
            
        # Create backup if requested
        if create_backup:
            backup_path = filepath.with_suffix(filepath.suffix + '.bak')
            try:
                import shutil
                shutil.copy2(filepath, backup_path)
                self.logger.debug("Created backup", backup=str(backup_path))
            except Exception as e:
                self.logger.warning("Failed to create backup", error=str(e))
        
        suffix = filepath.suffix.lower()
        
        if suffix == '.toml':
            return self.update_toml_version(filepath, new_version)
        elif suffix in ['.yaml', '.yml']:
            return self.update_yaml_version(filepath, new_version)
        elif suffix == '.json':
            return self.update_json_version(filepath, new_version)
        elif filepath.name == 'pubspec.yaml':
            return self.update_yaml_version(filepath, new_version)
        elif filepath.name == 'Cargo.toml':
            return self.update_cargo_toml_version(filepath, new_version)
        elif filepath.name == 'package.json':
            return self.update_json_version(filepath, new_version)
        else:
            self.logger.error("Unsupported file type", filepath=str(filepath))
            return False
    
    def update_toml_version(self, filepath: Path, new_version: str) -> bool:
        """Update version in TOML file."""
        try:
            with open(filepath, 'r') as f:
                data = toml.load(f)
            
            # Update version in common locations
            updated = False
            if 'package' in data and 'version' in data['package']:
                data['package']['version'] = new_version
                updated = True
            elif 'tool' in data and 'poetry' in data['tool'] and 'version' in data['tool']['poetry']:
                data['tool']['poetry']['version'] = new_version
                updated = True
            elif 'project' in data and 'version' in data['project']:
                data['project']['version'] = new_version
                updated = True
            elif 'version' in data:
                data['version'] = new_version
                updated = True
            
            if not updated:
                self.logger.error("No version field found in TOML", filepath=str(filepath))
                return False
                
            with open(filepath, 'w') as f:
                toml.dump(data, f)
                
            self.logger.info("Updated TOML version", filepath=str(filepath), version=new_version)
            return True
            
        except Exception as e:
            self.logger.error("Error updating TOML file", filepath=str(filepath), error=str(e))
            return False
    
    def update_yaml_version(self, filepath: Path, new_version: str) -> bool:
        """Update version in YAML file."""
        try:
            with open(filepath, 'r') as f:
                data = yaml.safe_load(f)
            
            if data is None:
                data = {}
                
            data['version'] = new_version
            
            with open(filepath, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
                
            self.logger.info("Updated YAML version", filepath=str(filepath), version=new_version)
            return True
            
        except Exception as e:
            self.logger.error("Error updating YAML file", filepath=str(filepath), error=str(e))
            return False
    
    def update_json_version(self, filepath: Path, new_version: str) -> bool:
        """Update version in JSON file."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                
            data['version'] = new_version
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
                f.write('\n')  # Add trailing newline
                
            self.logger.info("Updated JSON version", filepath=str(filepath), version=new_version)
            return True
            
        except Exception as e:
            self.logger.error("Error updating JSON file", filepath=str(filepath), error=str(e))
            return False
    
    def update_cargo_toml_version(self, filepath: Path, new_version: str) -> bool:
        """Update version in Cargo.toml."""
        try:
            with open(filepath, 'r') as f:
                data = toml.load(f)
                
            if 'package' not in data:
                self.logger.error("No [package] section in Cargo.toml", filepath=str(filepath))
                return False
                
            data['package']['version'] = new_version
            
            with open(filepath, 'w') as f:
                toml.dump(data, f)
                
            self.logger.info("Updated Cargo.toml version", filepath=str(filepath), version=new_version)
            return True
            
        except Exception as e:
            self.logger.error("Error updating Cargo.toml", filepath=str(filepath), error=str(e))
            return False


# Convenience functions
def parse_version(version_str: str) -> SemanticVersion:
    """Parse a version string into SemanticVersion object."""
    return SemanticVersion.parse(version_str)


def compare_versions(version1: str, version2: str) -> int:
    """
    Compare two version strings.
    
    Returns:
        -1 if version1 < version2
         0 if version1 == version2
         1 if version1 > version2
    """
    v1 = SemanticVersion.parse(version1)
    v2 = SemanticVersion.parse(version2)
    
    if v1 < v2:
        return -1
    elif v1 > v2:
        return 1
    else:
        return 0


def increment_version(
    version_str: str,
    component: VersionComponent = VersionComponent.PATCH
) -> str:
    """
    Increment a version string.
    
    Args:
        version_str: Current version string
        component: Which component to increment
        
    Returns:
        New version string
    """
    version = SemanticVersion.parse(version_str)
    new_version = version.increment(component)
    return str(new_version)


def validate_version(version: str) -> bool:
    """Validate semantic version format"""
    return bool(re.match(r'^\d+\.\d+\.\d+$', version))


def parse_version_tuple(version: str) -> Tuple[int, int, int]:
    """Parse version string into tuple of (major, minor, patch)"""
    # Strip 'v' prefix if present
    version = version.lstrip('v')
    parts = version.split('.')
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {version}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def format_version(major: int, minor: int, patch: int, prefix: str = '') -> str:
    """Format version components into string"""
    return f"{prefix}{major}.{minor}.{patch}"


def get_version_from_file(filepath: str) -> Optional[str]:
    """Extract version from a file"""
    extractor = VersionExtractor()
    return extractor.extract_from_file(filepath)


def update_version_in_file(filepath: str, new_version: str) -> None:
    """Update version in a file"""
    updater = VersionUpdater()
    if not updater.update_version_in_file(filepath, new_version, create_backup=False):
        raise ValueError(f"Failed to update version in {filepath}")