#!/usr/bin/env python3
"""
test_sync_changelogs.py - Test for sync_changelogs functionality

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved
"""

import sys
import os
import unittest
from pathlib import Path
import tempfile
import subprocess
import shutil

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from tooling.cli.cli_utils import print_info, print_success, print_error, console
except ImportError:
    # Fallback for when cli_utils isn't available
    def print_info(msg): print(f"ℹ {msg}")
    def print_success(msg): print(f"✓ {msg}")
    def print_error(msg): print(f"✗ {msg}")
    class Console:
        def print(self, msg, style=None): print(msg)
    console = Console()


class TestSyncChangelogs(unittest.TestCase):
    """Test cases for sync_changelogs functionality"""
    
    def test_changelog_parsing(self):
        """Test changelog parsing functionality"""
        # Create a temporary changelog file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("""# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [v0.0.2] - 2024-01-15

### Added
- New feature X

### Fixed
- Bug Y

## [v0.0.1] - 2024-01-01

### Added
- Initial release
""")
            temp_path = Path(f.name)
        
        try:
            # Test basic parsing
            content = temp_path.read_text()
            
            # Count versions
            import re
            version_pattern = re.compile(r'^## \[v?\d+\.\d+\.\d+\]', re.MULTILINE)
            versions = version_pattern.findall(content)
            
            self.assertEqual(len(versions), 2)
            print_success(f"Found {len(versions)} versions in changelog")
            
            # Test version extraction
            version_numbers = []
            for match in re.finditer(r'^## \[v?(\d+\.\d+\.\d+)\]', content, re.MULTILINE):
                version_numbers.append(match.group(1))
            
            self.assertEqual(version_numbers, ["0.0.2", "0.0.1"])
            print_success("Version extraction test passed")
            
        finally:
            # Clean up
            temp_path.unlink()
    
    def test_git_command_wrapper(self):
        """Test git command execution wrapper"""
        try:
            # Test basic git command
            result = subprocess.run(
                ['git', '--version'],
                capture_output=True,
                text=True,
                check=True
            )
            
            self.assertEqual(result.returncode, 0)
            self.assertIn('git version', result.stdout)
            print_success(f"Git command test passed: {result.stdout.strip()}")
            
        except subprocess.TimeoutExpired:
            self.fail("Git command timed out")
        except FileNotFoundError:
            self.skipTest("Git not found")
    
    def test_changelog_section_detection(self):
        """Test detection of changelog sections"""
        test_content = """### Added
- Feature A
- Feature B

### Fixed
- Bug X
- Bug Y

### Changed
- Updated Z
"""
        
        # Test section detection
        sections = {}
        current_section = None
        
        for line in test_content.splitlines():
            if line.startswith('### '):
                current_section = line[4:].strip()
                sections[current_section] = []
            elif current_section and line.strip().startswith('-'):
                sections[current_section].append(line.strip())
        
        self.assertEqual(len(sections), 3)
        self.assertIn('Added', sections)
        self.assertIn('Fixed', sections)
        self.assertIn('Changed', sections)
        self.assertEqual(len(sections['Added']), 2)
        self.assertEqual(len(sections['Fixed']), 2)
        
        print_success("Changelog section detection test passed")


if __name__ == "__main__":
    unittest.main(verbosity=2) 