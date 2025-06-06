"""
Changelog manipulation utilities.

This module provides functions for parsing, generating, and validating
changelog files following the Keep a Changelog format.

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved
"""

from __future__ import annotations

import re
import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from collections import defaultdict, OrderedDict
from enum import Enum

from tooling.core.logging import get_logger
from tooling.utils.version_utils import SemanticVersion, compare_versions


class ChangelogSection(Enum):
    """Standard changelog sections according to Keep a Changelog."""
    ADDED = "Added"
    CHANGED = "Changed"
    DEPRECATED = "Deprecated"
    REMOVED = "Removed"
    FIXED = "Fixed"
    SECURITY = "Security"
    
    # Additional sections commonly used
    BREAKING = "Breaking Changes"
    PERFORMANCE = "Performance"
    DEPENDENCIES = "Dependencies"
    
    @classmethod
    def from_string(cls, section: str) -> Optional['ChangelogSection']:
        """Convert string to ChangelogSection enum."""
        section_lower = section.lower().replace(' ', '_')
        
        # Handle variations
        if section_lower in ['breaking', 'breaking_changes', 'breaking_change']:
            return cls.BREAKING
            
        for member in cls:
            if member.value.lower() == section.lower():
                return member
                
        return None
    
    @classmethod
    def all_sections(cls) -> List[str]:
        """Get all section names in order."""
        return [member.value for member in cls]


class ChangelogError(Exception):
    """Base exception for changelog operations."""
    pass


class InvalidChangelogError(ChangelogError):
    """Raised when changelog format is invalid."""
    pass


@dataclass
class ChangelogEntry:
    """Represents a single changelog entry."""
    text: str
    section: ChangelogSection
    pr_number: Optional[int] = None
    commit_hash: Optional[str] = None
    author: Optional[str] = None
    
    def format(self, include_metadata: bool = True) -> str:
        """Format the entry for output."""
        result = f"- {self.text}"
        
        if include_metadata:
            metadata = []
            if self.pr_number:
                metadata.append(f"#{self.pr_number}")
            if self.author:
                metadata.append(f"@{self.author}")
            if metadata:
                result += f" ({', '.join(metadata)})"
                
        return result


@dataclass
class ChangelogVersion:
    """Represents a version section in a changelog."""
    version: str
    date: Optional[datetime.date] = None
    sections: Dict[ChangelogSection, List[ChangelogEntry]] = field(default_factory=dict)
    raw_text: Optional[str] = None
    
    def add_entry(self, entry: ChangelogEntry) -> None:
        """Add an entry to the appropriate section."""
        if entry.section not in self.sections:
            self.sections[entry.section] = []
        self.sections[entry.section].append(entry)
    
    def format(self, include_metadata: bool = True) -> str:
        """Format the version section for output."""
        lines = []
        
        # Version header
        header = f"## [{self.version}]"
        if self.date:
            header += f" - {self.date.strftime('%Y-%m-%d')}"
        lines.append(header)
        lines.append("")
        
        # Add sections in order
        for section in ChangelogSection:
            if section in self.sections and self.sections[section]:
                lines.append(f"### {section.value}")
                for entry in self.sections[section]:
                    lines.append(entry.format(include_metadata))
                lines.append("")
        
        return "\n".join(lines)
    
    def is_empty(self) -> bool:
        """Check if version has no entries."""
        return not any(self.sections.values())


@dataclass
class Changelog:
    """Represents a complete changelog file."""
    header: Optional[str] = None
    versions: List[ChangelogVersion] = field(default_factory=list)
    footer: Optional[str] = None
    filepath: Optional[Path] = None
    
    def get_version(self, version: str) -> Optional[ChangelogVersion]:
        """Get a specific version section."""
        # Normalize version (remove 'v' prefix if present)
        version = version.lstrip('v')
        
        for v in self.versions:
            if v.version.lstrip('v') == version:
                return v
        return None
    
    def add_version(self, version: ChangelogVersion) -> None:
        """Add a version section, maintaining order."""
        self.versions.append(version)
        self._sort_versions()
    
    def _sort_versions(self) -> None:
        """Sort versions in descending order (newest first)."""
        # Separate 'Unreleased' if present
        unreleased = None
        regular_versions = []
        
        for v in self.versions:
            if v.version.lower() == 'unreleased':
                unreleased = v
            else:
                regular_versions.append(v)
        
        # Sort regular versions
        try:
            regular_versions.sort(
                key=lambda v: SemanticVersion.parse(v.version),
                reverse=True
            )
        except:
            # Fallback to string sorting if semantic version parsing fails
            regular_versions.sort(key=lambda v: v.version, reverse=True)
        
        # Rebuild versions list
        self.versions = []
        if unreleased:
            self.versions.append(unreleased)
        self.versions.extend(regular_versions)
    
    def format(self, include_metadata: bool = True) -> str:
        """Format the complete changelog for output."""
        lines = []
        
        if self.header:
            lines.append(self.header.strip())
            lines.append("")
        
        for version in self.versions:
            lines.append(version.format(include_metadata))
            
        if self.footer:
            lines.append(self.footer.strip())
            
        return "\n".join(lines)


class ChangelogParser:
    """Parses changelog files in Keep a Changelog format."""
    
    VERSION_PATTERN = re.compile(
        r'^## \[(?P<version>[^\]]+)\](?:\s*-\s*(?P<date>\d{4}-\d{2}-\d{2}))?',
        re.MULTILINE
    )
    
    SECTION_PATTERN = re.compile(r'^### (?P<section>.+)$', re.MULTILINE)
    
    ENTRY_PATTERN = re.compile(r'^- (?P<text>.+)$', re.MULTILINE)
    
    def __init__(self, logger=None):
        """Initialize ChangelogParser."""
        self.logger = logger or get_logger("changelog_utils")
    
    def parse_file(self, filepath: Union[str, Path]) -> Changelog:
        """
        Parse a changelog file.
        
        Args:
            filepath: Path to the changelog file
            
        Returns:
            Parsed Changelog object
            
        Raises:
            ChangelogError: If file cannot be read or parsed
        """
        filepath = Path(filepath)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            raise ChangelogError(f"Failed to read changelog file: {e}")
        
        return self.parse_content(content, filepath)
    
    def parse_content(self, content: str, filepath: Optional[Path] = None) -> Changelog:
        """
        Parse changelog content.
        
        Args:
            content: Changelog file content
            filepath: Optional filepath for reference
            
        Returns:
            Parsed Changelog object
        """
        changelog = Changelog(filepath=filepath)
        
        # Split content into sections based on version headers
        version_matches = list(self.VERSION_PATTERN.finditer(content))
        
        if not version_matches:
            # No versions found, treat entire content as header
            changelog.header = content.strip()
            return changelog
        
        # Extract header (content before first version)
        first_match = version_matches[0]
        if first_match.start() > 0:
            changelog.header = content[:first_match.start()].strip()
        
        # Parse each version section
        for i, match in enumerate(version_matches):
            version = match.group('version')
            date_str = match.group('date')
            date = None
            
            if date_str:
                try:
                    date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    self.logger.warning(f"Invalid date format: {date_str}")
            
            # Get content for this version
            start = match.end()
            if i + 1 < len(version_matches):
                end = version_matches[i + 1].start()
            else:
                end = len(content)
            
            version_content = content[start:end].strip()
            
            # Parse version content
            version_obj = self._parse_version_content(version, date, version_content)
            changelog.add_version(version_obj)
        
        return changelog
    
    def _parse_version_content(
        self,
        version: str,
        date: Optional[datetime.date],
        content: str
    ) -> ChangelogVersion:
        """Parse the content of a version section."""
        version_obj = ChangelogVersion(version=version, date=date, raw_text=content)
        
        # Find all sections
        section_matches = list(self.SECTION_PATTERN.finditer(content))
        
        if not section_matches:
            # No sections found, store raw content
            return version_obj
        
        # Parse each section
        for i, match in enumerate(section_matches):
            section_name = match.group('section')
            section_enum = ChangelogSection.from_string(section_name)
            
            if not section_enum:
                self.logger.warning(f"Unknown section: {section_name}")
                continue
            
            # Get content for this section
            start = match.end()
            if i + 1 < len(section_matches):
                end = section_matches[i + 1].start()
            else:
                end = len(content)
            
            section_content = content[start:end].strip()
            
            # Parse entries in this section
            for entry_match in self.ENTRY_PATTERN.finditer(section_content):
                entry_text = entry_match.group('text').strip()
                
                # Extract metadata from entry
                pr_match = re.search(r'#(\d+)', entry_text)
                pr_number = int(pr_match.group(1)) if pr_match else None
                
                author_match = re.search(r'@(\w+)', entry_text)
                author = author_match.group(1) if author_match else None
                
                # Clean entry text (remove metadata)
                clean_text = re.sub(r'\s*\([^)]*\)\s*$', '', entry_text).strip()
                
                entry = ChangelogEntry(
                    text=clean_text,
                    section=section_enum,
                    pr_number=pr_number,
                    author=author
                )
                
                version_obj.add_entry(entry)
        
        return version_obj


class ChangelogGenerator:
    """Generates changelog entries from commit messages."""
    
    CONVENTIONAL_COMMIT_PATTERN = re.compile(
        r'^(?P<type>\w+)(?:\((?P<scope>[^)]+)\))?(?P<breaking>!)?: (?P<description>.+)$'
    )
    
    TYPE_TO_SECTION = {
        'feat': ChangelogSection.ADDED,
        'fix': ChangelogSection.FIXED,
        'docs': ChangelogSection.CHANGED,
        'style': ChangelogSection.CHANGED,
        'refactor': ChangelogSection.CHANGED,
        'perf': ChangelogSection.PERFORMANCE,
        'test': ChangelogSection.CHANGED,
        'build': ChangelogSection.CHANGED,
        'ci': ChangelogSection.CHANGED,
        'chore': ChangelogSection.CHANGED,
        'revert': ChangelogSection.CHANGED,
        'security': ChangelogSection.SECURITY,
        'breaking': ChangelogSection.BREAKING,
    }
    
    def __init__(self, logger=None):
        """Initialize ChangelogGenerator."""
        self.logger = logger or get_logger("changelog_utils")
    
    def generate_entry_from_commit(self, commit: Dict[str, Any]) -> Optional[ChangelogEntry]:
        """
        Generate a changelog entry from a commit.
        
        Args:
            commit: Commit dictionary with 'subject', 'body', 'hash', 'author_name'
            
        Returns:
            ChangelogEntry or None if commit should be skipped
        """
        subject = commit.get('subject', '')
        body = commit.get('body', '')
        
        # Parse conventional commit
        match = self.CONVENTIONAL_COMMIT_PATTERN.match(subject)
        
        if match:
            commit_type = match.group('type')
            scope = match.group('scope')
            is_breaking = bool(match.group('breaking'))
            description = match.group('description')
            
            # Determine section
            if is_breaking or 'BREAKING CHANGE' in body:
                section = ChangelogSection.BREAKING
            else:
                section = self.TYPE_TO_SECTION.get(commit_type)
                
            if not section:
                # Unknown type, skip
                return None
                
            # Format entry text
            if scope:
                text = f"**{scope}**: {description}"
            else:
                text = description
                
        else:
            # Not a conventional commit, try to categorize by keywords
            subject_lower = subject.lower()
            
            if any(word in subject_lower for word in ['add', 'new', 'create', 'implement']):
                section = ChangelogSection.ADDED
            elif any(word in subject_lower for word in ['fix', 'bug', 'issue', 'resolve']):
                section = ChangelogSection.FIXED
            elif any(word in subject_lower for word in ['security', 'vulnerability', 'cve']):
                section = ChangelogSection.SECURITY
            elif any(word in subject_lower for word in ['remove', 'delete']):
                section = ChangelogSection.REMOVED
            elif any(word in subject_lower for word in ['deprecate', 'deprecated']):
                section = ChangelogSection.DEPRECATED
            elif any(word in subject_lower for word in ['perf', 'performance', 'optimize']):
                section = ChangelogSection.PERFORMANCE
            else:
                section = ChangelogSection.CHANGED
                
            text = subject
        
        # Extract PR number if present
        pr_match = re.search(r'#(\d+)', subject)
        pr_number = int(pr_match.group(1)) if pr_match else None
        
        return ChangelogEntry(
            text=text,
            section=section,
            pr_number=pr_number,
            commit_hash=commit.get('hash'),
            author=commit.get('author_name')
        )
    
    def group_entries_by_section(
        self,
        entries: List[ChangelogEntry]
    ) -> Dict[ChangelogSection, List[ChangelogEntry]]:
        """Group entries by their section."""
        grouped = defaultdict(list)
        
        for entry in entries:
            grouped[entry.section].append(entry)
            
        return dict(grouped)
    
    def format_version_content(
        self,
        entries: List[ChangelogEntry],
        version: str,
        date: Optional[datetime.date] = None
    ) -> str:
        """
        Format entries into a version section.
        
        Args:
            entries: List of changelog entries
            version: Version string
            date: Optional release date
            
        Returns:
            Formatted version section content
        """
        if not entries:
            return ""
            
        version_obj = ChangelogVersion(version=version, date=date)
        
        for entry in entries:
            version_obj.add_entry(entry)
            
        return version_obj.format()


class ChangelogValidator:
    """Validates changelog format and content."""
    
    PLACEHOLDER_PATTERNS = [
        r'^n/?a$',
        r'^none$',
        r'^nothing$',
        r'^tbd$',
        r'^todo$',
        r'^-\s*$',
        r'^\.\.\.$',
        r'^pending$',
        r'^wip$',
        r'^work in progress$'
    ]
    
    def __init__(self, logger=None):
        """Initialize ChangelogValidator."""
        self.logger = logger or get_logger("changelog_utils")
    
    def validate_changelog(self, changelog: Changelog) -> List[str]:
        """
        Validate a changelog for common issues.
        
        Args:
            changelog: Parsed Changelog object
            
        Returns:
            List of validation error messages
        """
        errors = []
        
        # Check for duplicate versions
        versions = [v.version for v in changelog.versions]
        duplicates = [v for v in versions if versions.count(v) > 1]
        if duplicates:
            errors.append(f"Duplicate versions found: {', '.join(set(duplicates))}")
        
        # Validate each version
        for version in changelog.versions:
            version_errors = self.validate_version(version)
            errors.extend([f"[{version.version}] {e}" for e in version_errors])
            
        return errors
    
    def validate_version(self, version: ChangelogVersion) -> List[str]:
        """Validate a version section."""
        errors = []
        
        # Check if version is empty
        if version.is_empty():
            errors.append("Version has no entries")
            return errors
        
        # Check for invalid sections
        for section in version.sections:
            if not isinstance(section, ChangelogSection):
                errors.append(f"Invalid section type: {section}")
        
        # Check for placeholder entries
        for section, entries in version.sections.items():
            for entry in entries:
                if self._is_placeholder(entry.text):
                    errors.append(f"Placeholder entry in {section.value}: '{entry.text}'")
                    
        return errors
    
    def _is_placeholder(self, text: str) -> bool:
        """Check if text is a placeholder."""
        text_lower = text.strip().lower()
        
        for pattern in self.PLACEHOLDER_PATTERNS:
            if re.match(pattern, text_lower, re.IGNORECASE):
                return True
                
        return False
    
    def validate_file(self, filepath: Union[str, Path]) -> List[str]:
        """
        Validate a changelog file.
        
        Args:
            filepath: Path to changelog file
            
        Returns:
            List of validation error messages
        """
        try:
            parser = ChangelogParser(self.logger)
            changelog = parser.parse_file(filepath)
            return self.validate_changelog(changelog)
        except Exception as e:
            return [f"Failed to parse changelog: {e}"]


# Convenience functions
def parse_changelog(filepath: Union[str, Path]) -> Changelog:
    """Parse a changelog file."""
    parser = ChangelogParser()
    return parser.parse_file(filepath)


def extract_version_content(filepath: Union[str, Path], version: str) -> Optional[str]:
    """
    Extract content for a specific version from a changelog.
    
    Args:
        filepath: Path to changelog file
        version: Version to extract (with or without 'v' prefix)
        
    Returns:
        Version content or None if not found
    """
    changelog = parse_changelog(filepath)
    version_obj = changelog.get_version(version)
    
    if version_obj:
        return version_obj.raw_text or version_obj.format()
    return None


def validate_changelog_file(filepath: Union[str, Path]) -> List[str]:
    """
    Validate a changelog file.
    
    Returns:
        List of validation errors (empty if valid)
    """
    validator = ChangelogValidator()
    return validator.validate_file(filepath)


def extract_changelog_section(filepath: Union[str, Path], version: str) -> Optional[str]:
    """Extract a specific version section from changelog"""
    return extract_version_content(filepath, version)


def validate_changelog_format(content: str) -> bool:
    """Validate changelog follows expected format"""
    # Basic validation - check for common changelog patterns
    required_patterns = [
        r'#\s+Changelog',  # Main header
        r'##\s+\[?\d+\.\d+\.\d+\]?',  # Version headers
    ]
    
    for pattern in required_patterns:
        if not re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
            return False
    
    return True