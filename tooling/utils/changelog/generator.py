"""
Changelog generator using AI or conventional commits.
"""
import re
from typing import Dict, List, Optional

from .models import GitCommit, CONVENTIONAL_TYPES, CHANGELOG_SECTIONS


class ChangelogGenerator:
    """Generate changelog entries from commits and context."""
    
    def __init__(self, package: str, version: str):
        self.package = package
        self.version = version
    
    def generate(self, commits: List[GitCommit], selected_files: List[str], 
                 context: str, existing_content: str, version_context: str = "") -> str:
        """Generate changelog content.
        
        Args:
            commits: List of commits for this version
            selected_files: List of relevant files
            context: Analysis context from analyzers
            existing_content: Existing changelog content to avoid duplicates
            version_context: Additional context about the version
            
        Returns:
            Generated changelog content in Keep a Changelog format
        """
        # Check if we can use conventional commits
        conventional_commits = [c for c in commits if c.conventional]
        if len(conventional_commits) >= len(commits) * 0.7:  # 70% are conventional
            return self._generate_from_conventional(commits)
        
        # Otherwise, generate summary based on context
        return self._generate_from_context(commits, context, selected_files)
    
    def _generate_from_conventional(self, commits: List[GitCommit]) -> str:
        """Generate changelog from conventional commits"""
        # Group by changelog section
        groups = self._group_conventional_commits(commits)
        
        # Build content
        content_parts = []
        
        for section in CHANGELOG_SECTIONS:
            if section in groups and groups[section]:
                content_parts.append(f"### {section}")
                
                # Sort entries
                entries = []
                for commit in groups[section]:
                    entry = self._format_conventional_entry(commit)
                    if entry:
                        entries.append(entry)
                
                # Remove duplicates
                unique_entries = []
                for entry in entries:
                    if not any(self._similar_entries(entry, e) for e in unique_entries):
                        unique_entries.append(entry)
                
                # Add entries
                for entry in sorted(unique_entries):
                    content_parts.append(entry)
                
                content_parts.append("")  # Blank line after section
        
        return '\n'.join(content_parts).strip()
    
    def _generate_from_context(self, commits: List[GitCommit], context: str, 
                               files: List[str]) -> str:
        """Generate changelog from analysis context"""
        # This is a simplified version - in production you'd use AI here
        content_parts = []
        
        # Analyze commits for patterns
        features = []
        fixes = []
        changes = []
        
        for commit in commits:
            msg = commit.message.split('\n')[0]
            msg_lower = msg.lower()
            
            if any(word in msg_lower for word in ['add', 'new', 'feature', 'implement']):
                features.append(self._format_simple_entry(commit, msg))
            elif any(word in msg_lower for word in ['fix', 'bug', 'issue', 'resolve']):
                fixes.append(self._format_simple_entry(commit, msg))
            else:
                changes.append(self._format_simple_entry(commit, msg))
        
        # Build sections
        if features:
            content_parts.append("### Added")
            for entry in features[:10]:  # Limit entries
                content_parts.append(entry)
            if len(features) > 10:
                content_parts.append(f"- ... and {len(features) - 10} more features")
            content_parts.append("")
        
        if changes:
            content_parts.append("### Changed")
            for entry in changes[:10]:
                content_parts.append(entry)
            if len(changes) > 10:
                content_parts.append(f"- ... and {len(changes) - 10} more changes")
            content_parts.append("")
        
        if fixes:
            content_parts.append("### Fixed")
            for entry in fixes[:10]:
                content_parts.append(entry)
            if len(fixes) > 10:
                content_parts.append(f"- ... and {len(fixes) - 10} more fixes")
            content_parts.append("")
        
        return '\n'.join(content_parts).strip()
    
    def _group_conventional_commits(self, commits: List[GitCommit]) -> Dict[str, List[GitCommit]]:
        """Group commits by changelog section based on conventional type"""
        groups = {section: [] for section in CHANGELOG_SECTIONS}
        
        for commit in commits:
            if not commit.conventional:
                # Try to infer section
                msg_lower = commit.message.lower()
                if 'security' in msg_lower:
                    groups['Security'].append(commit)
                elif any(word in msg_lower for word in ['fix', 'bug']):
                    groups['Fixed'].append(commit)
                elif any(word in msg_lower for word in ['add', 'new', 'feat']):
                    groups['Added'].append(commit)
                elif any(word in msg_lower for word in ['remove', 'delete']):
                    groups['Removed'].append(commit)
                elif any(word in msg_lower for word in ['deprecat']):
                    groups['Deprecated'].append(commit)
                else:
                    groups['Changed'].append(commit)
            else:
                # Map conventional type to section
                section = CONVENTIONAL_TYPES.get(commit.conventional.type, 'Changed')
                
                # Handle breaking changes
                if commit.conventional.breaking:
                    # Add to Changed with BREAKING CHANGE note
                    groups['Changed'].append(commit)
                else:
                    groups[section].append(commit)
        
        return groups
    
    def _format_conventional_entry(self, commit: GitCommit) -> Optional[str]:
        """Format a conventional commit as changelog entry"""
        if not commit.conventional:
            return None
        
        # Build entry
        entry_parts = []
        
        # Add scope if present
        if commit.conventional.scope:
            entry_parts.append(f"**{commit.conventional.scope}:**")
        
        # Add description
        desc = commit.conventional.description
        # Capitalize first letter
        if desc and desc[0].islower():
            desc = desc[0].upper() + desc[1:]
        entry_parts.append(desc)
        
        # Add breaking change note
        if commit.conventional.breaking:
            entry_parts.append("**BREAKING CHANGE**")
        
        # Add attribution
        if hasattr(commit, 'short_hash'):
            entry_parts.append(f"({commit.short_hash})")
        
        return f"- {' '.join(entry_parts)}"
    
    def _format_simple_entry(self, commit: GitCommit, message: str) -> str:
        """Format a simple changelog entry"""
        # Clean up message
        message = message.strip()
        
        # Remove conventional commit prefix if present
        message = re.sub(r'^\w+(\([^)]+\))?!?:\s*', '', message)
        
        # Capitalize first letter
        if message and message[0].islower():
            message = message[0].upper() + message[1:]
        
        # Add attribution
        attribution = f"({commit.short_hash})" if hasattr(commit, 'short_hash') else ""
        
        return f"- {message} {attribution}".strip()
    
    def _similar_entries(self, entry1: str, entry2: str) -> bool:
        """Check if two entries are similar"""
        # Normalize entries
        def normalize(s):
            # Remove markdown formatting
            s = re.sub(r'\*\*(.*?)\*\*', r'\1', s)  # Bold
            s = re.sub(r'`(.*?)`', r'\1', s)        # Code
            s = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', s)  # Links
            s = re.sub(r'\([\w\d]+\)', '', s)      # Remove hashes
            # Remove common prefixes
            s = re.sub(r'^[-*]\s*', '', s)
            # Normalize whitespace
            s = ' '.join(s.split())
            return s.lower().strip()
        
        norm1 = normalize(entry1)
        norm2 = normalize(entry2)
        
        # Check various similarity criteria
        if not norm1 or not norm2:
            return False
        
        # Exact match
        if norm1 == norm2:
            return True
        
        # One contains the other
        if norm1 in norm2 or norm2 in norm1:
            return True
        
        # Word overlap for longer entries
        if len(norm1) > 20 and len(norm2) > 20:
            words1 = set(norm1.split())
            words2 = set(norm2.split())
            common = words1 & words2
            if len(common) > max(len(words1), len(words2)) * 0.7:
                return True
        
        return False 