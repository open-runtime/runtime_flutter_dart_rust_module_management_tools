"""
Changelog parser for managing and parsing changelog files.
"""
import pathlib
import re
from typing import Dict, List, Optional, Tuple

from .models import VersionEntry


class ChangelogParser:
    """Parse and manage changelog files."""
    
    def __init__(self, path: pathlib.Path, package_key: str = "root"):
        self.path = path
        self.package_key = package_key
        self.content = ""
        self.versions: Dict[str, VersionEntry] = {}
        self._load()
    
    def _load(self):
        """Load changelog content from file"""
        if self.path.exists():
            self.content = self.path.read_text()
        else:
            self.content = self._default_header()
        self._parse_versions()
    
    def _default_header(self) -> str:
        """Generate default changelog header"""
        header = "# Changelog\n\n"
        header += "All notable changes to this project will be documented in this file.\n\n"
        header += "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),\n"
        header += "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n\n"
        
        # Add comparison links section
        header += "---\n\n"
        header += "<!-- Links -->\n"
        header += "<!-- These should be at the end of the file -->\n"
        
        return header
    
    def _parse_versions(self):
        """Parse version entries from changelog content"""
        # Pattern to match version headers like ## [1.0.0] - 2024-01-01
        version_pattern = r'^##\s*\[([^\]]+)\](?:\s*-\s*(.+?))?$'
        
        lines = self.content.split('\n')
        current_version = None
        current_date = None
        current_content = []
        
        for i, line in enumerate(lines):
            match = re.match(version_pattern, line, re.MULTILINE)
            if match:
                # Save previous version if exists
                if current_version:
                    content = '\n'.join(current_content).strip()
                    self.versions[current_version] = VersionEntry(
                        version=current_version,
                        date=current_date or "",
                        content=content,
                        is_empty=self._is_empty_section(content)
                    )
                
                # Start new version
                current_version = match.group(1)
                current_date = match.group(2) or ""
                current_content = []
            elif current_version:
                current_content.append(line)
        
        # Save last version
        if current_version:
            content = '\n'.join(current_content).strip()
            self.versions[current_version] = VersionEntry(
                version=current_version,
                date=current_date or "",
                content=content,
                is_empty=self._is_empty_section(content)
            )
    
    def _is_empty_section(self, content: str) -> bool:
        """Check if a version section is empty or contains only N/A"""
        if not content.strip():
            return True
        
        # Check for N/A pattern
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        if len(lines) == 1 and lines[0].lower() in ['n/a', 'n/a.', '- n/a', '- n/a.']:
            return True
        
        # Check if only contains section headers with no content
        section_headers = {'### Added', '### Changed', '### Deprecated', 
                          '### Removed', '### Fixed', '### Security'}
        has_content = False
        for line in lines:
            if line and line not in section_headers and not line.startswith('###'):
                has_content = True
                break
        
        return not has_content
    
    def get_empty_versions(self) -> List[str]:
        """Get list of empty version numbers"""
        return [v for v, entry in self.versions.items() if entry.is_empty]
    
    def validate_entry(self, content: str) -> Tuple[bool, List[str]]:
        """Validate a changelog entry
        
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        # Check for Keep a Changelog sections
        valid_sections = {'Added', 'Changed', 'Deprecated', 'Removed', 'Fixed', 'Security'}
        found_sections = set()
        
        for line in content.split('\n'):
            if line.startswith('### '):
                section = line[4:].strip()
                if section not in valid_sections:
                    issues.append(f"Invalid section: {section}")
                else:
                    found_sections.add(section)
        
        # Check for empty sections
        if not found_sections and content.strip():
            issues.append("No valid sections found")
        
        # Check for commit hashes (they should be links)
        commit_pattern = r'\b[0-9a-f]{7,40}\b'
        for match in re.finditer(commit_pattern, content):
            if not (match.start() > 0 and content[match.start()-1] == '['):
                issues.append(f"Unlinked commit hash: {match.group()}")
        
        return len(issues) == 0, issues
    
    def merge_version(self, version: str, date: str, new_content: str):
        """Merge new content for a version"""
        if version in self.versions:
            self._merge_existing_version(version, new_content)
        else:
            self._insert_new_version(version, date, new_content)
    
    def _merge_existing_version(self, version: str, new_content: str):
        """Merge new content into existing version"""
        existing_entry = self.versions[version]
        
        # If existing is empty or N/A, replace entirely
        if existing_entry.is_empty:
            merged = new_content
        else:
            # Otherwise merge sections
            merged = self._merge_sections(existing_entry.content, new_content)
        
        # Update in content
        version_header = f"## [{version}]"
        if existing_entry.date:
            version_header += f" - {existing_entry.date}"
        
        # Find the version section in content
        lines = self.content.split('\n')
        start_idx = None
        end_idx = None
        
        for i, line in enumerate(lines):
            if line.startswith(f"## [{version}]"):
                start_idx = i
            elif start_idx is not None and line.startswith("## ["):
                end_idx = i
                break
        
        if end_idx is None:
            end_idx = len(lines)
        
        # Replace the section
        new_lines = lines[:start_idx+1] + [merged] + lines[end_idx:]
        self.content = '\n'.join(new_lines)
        
        # Update parsed version
        existing_entry.content = merged
        existing_entry.is_empty = self._is_empty_section(merged)
    
    def _merge_sections(self, existing: str, new: str) -> str:
        """Merge changelog sections intelligently"""
        existing_sections = self._parse_sections(existing)
        new_sections = self._parse_sections(new)
        
        # Merge sections
        merged_sections = {}
        for section in ['Added', 'Changed', 'Deprecated', 'Removed', 'Fixed', 'Security']:
            entries = []
            
            # Add existing entries
            if section in existing_sections:
                entries.extend(existing_sections[section])
            
            # Add new entries (avoiding duplicates)
            if section in new_sections:
                for entry in new_sections[section]:
                    if not any(self._similar_entries(entry, e) for e in entries):
                        entries.append(entry)
            
            if entries:
                merged_sections[section] = entries
        
        # Build merged content
        result = []
        for section in ['Added', 'Changed', 'Deprecated', 'Removed', 'Fixed', 'Security']:
            if section in merged_sections:
                result.append(f"### {section}")
                for entry in merged_sections[section]:
                    result.append(entry)
                result.append("")  # Blank line after section
        
        return '\n'.join(result).strip()
    
    def _similar_entries(self, entry1: str, entry2: str) -> bool:
        """Check if two entries are similar enough to be duplicates"""
        # Normalize entries
        def normalize(s):
            # Remove markdown formatting
            s = re.sub(r'\*\*(.*?)\*\*', r'\1', s)  # Bold
            s = re.sub(r'`(.*?)`', r'\1', s)        # Code
            s = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', s)  # Links
            # Remove common prefixes
            s = re.sub(r'^[-*]\s*', '', s)
            # Normalize whitespace
            s = ' '.join(s.split())
            return s.lower()
        
        norm1 = normalize(entry1)
        norm2 = normalize(entry2)
        
        # Exact match after normalization
        if norm1 == norm2:
            return True
        
        # Check if one contains the other (substring match)
        if len(norm1) > 10 and len(norm2) > 10:
            if norm1 in norm2 or norm2 in norm1:
                return True
        
        # Fuzzy matching - check word overlap
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        # Ignore common words
        common_words = {'the', 'a', 'an', 'to', 'for', 'in', 'on', 'at', 'and', 'or', 'of', 'with'}
        words1 = words1 - common_words
        words2 = words2 - common_words
        
        if len(words1) >= 3 and len(words2) >= 3:
            overlap = len(words1 & words2)
            similarity = overlap / min(len(words1), len(words2))
            return similarity > 0.7
        
        return False
    
    def _parse_sections(self, content: str) -> Dict[str, List[str]]:
        """Parse content into sections"""
        sections = {}
        current_section = None
        
        for line in content.split('\n'):
            if line.startswith('### '):
                current_section = line[4:].strip()
                sections[current_section] = []
            elif current_section and line.strip():
                sections[current_section].append(line)
        
        return sections
    
    def _insert_new_version(self, version: str, date: str, content: str):
        """Insert a new version entry"""
        version_header = f"## [{version}]"
        if date:
            version_header += f" - {date}"
        
        new_entry = f"{version_header}\n\n{content}\n"
        
        # Find insertion point (after header, before first version)
        lines = self.content.split('\n')
        insert_idx = 0
        
        # Skip header until we find the first version or end of header
        for i, line in enumerate(lines):
            if line.startswith('## ['):
                insert_idx = i
                break
            elif line.strip() == '---' or line.startswith('<!-- '):
                # Found the links section, insert before it
                insert_idx = i
                break
        else:
            # No versions found, add at end
            insert_idx = len(lines)
        
        # Insert the new version
        lines.insert(insert_idx, new_entry)
        self.content = '\n'.join(lines)
        
        # Update parsed versions
        self.versions[version] = VersionEntry(
            version=version,
            date=date,
            content=content,
            is_empty=self._is_empty_section(content)
        )
    
    def save(self, backup: bool = True):
        """Save changelog to file"""
        if backup and self.path.exists():
            backup_path = self.path.with_suffix('.bak')
            backup_path.write_text(self.path.read_text())
        
        # Ensure directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)
        
        # Clean up content
        self.content = self._ensure_final_newline(self.content)
        self.content = self._ensure_proper_spacing(self.content)
        
        # Write file
        self.path.write_text(self.content)
    
    def _ensure_final_newline(self, content: str) -> str:
        """Ensure content ends with exactly one newline"""
        return content.rstrip() + '\n'
    
    def _ensure_proper_spacing(self, content: str) -> str:
        """Ensure proper spacing between sections"""
        # Replace multiple blank lines with double blank lines
        content = re.sub(r'\n\n\n+', '\n\n', content)
        # Ensure blank line before version headers
        content = re.sub(r'([^\n])\n(## \[)', r'\1\n\n\2', content)
        return content 