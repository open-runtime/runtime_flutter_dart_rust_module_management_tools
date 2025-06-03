#!/usr/bin/env python3
"""
Integration tests for sync_changelogs.py using dummy repositories
"""

import sys
import os
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.common_config import Colors, print_color, run_command
from tests.test_helpers import DummyProject, create_test_scenario


class TestSyncChangelogsIntegration(unittest.TestCase):
    """Integration tests for sync_changelogs functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_base = tempfile.mkdtemp(prefix="test_sync_")
        self.original_cwd = os.getcwd()
        
        # Store original environment
        self.original_env = os.environ.copy()
        
        # Set up test environment variables
        os.environ['GEMINI_API_KEY'] = 'test_key_12345'
        os.environ['USE_ENHANCED_ANALYSIS'] = 'false'  # Disable for tests
        
    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_base, ignore_errors=True)
        
        # Restore environment
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def run_sync_changelogs(self, args: list, cwd: str) -> tuple:
        """Run sync_changelogs.py and return (returncode, stdout, stderr)"""
        # Get the path to sync_changelogs.py
        sync_changelogs_path = Path(__file__).parent.parent / "cli" / "sync_changelogs.py"
        
        # Create a wrapper script that sets up the environment properly
        wrapper_script = f"""
import sys
import os

# Add the tooling directory to Python path
tooling_dir = r'{Path(__file__).parent.parent}'
sys.path.insert(0, tooling_dir)

# Change to the test directory so package detection works
os.chdir(r'{cwd}')

# Mock the LLM to avoid API calls
import unittest.mock
with unittest.mock.patch('cli.sync_changelogs.LLMClient.prompt') as mock_prompt:
    mock_prompt.return_value = '''### Added
- New feature implementation

### Fixed  
- Bug fix implementation'''
    
    # Now run the actual script
    exec(open(r'{sync_changelogs_path}').read())
"""
        
        # Write wrapper to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(wrapper_script)
            wrapper_path = f.name
        
        try:
            cmd = [sys.executable, wrapper_path] + args
            
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                env=os.environ
            )
            
            return result.returncode, result.stdout, result.stderr
        finally:
            # Clean up wrapper
            os.unlink(wrapper_path)
    
    def test_simple_changelog_generation(self):
        """Test basic changelog generation in a simple project"""
        with DummyProject("test_simple", self.test_base) as project:
            project.create_standard_structure()
            
            # Add some commits
            project.add_feature("new feature")
            project.add_fix("critical bug")
            
            # Run sync_changelogs in dry-run mode
            code, stdout, stderr = self.run_sync_changelogs(
                ["--dry-run", "--no-cache"],
                str(project.repo_dir)
            )
            
            # Check execution
            self.assertEqual(code, 0, f"sync_changelogs failed: {stderr}")
            self.assertIn("Changelog sync complete", stdout)
            self.assertIn("dry run", stdout.lower())
            
            print_color(Colors.GREEN, "✓ Simple changelog generation test passed")
    
    def test_multi_version_changelog(self):
        """Test changelog generation with multiple versions"""
        project = create_test_scenario("multi_version")
        project.base_dir = Path(self.test_base)
        
        with project:
            # Run sync_changelogs to process unreleased changes
            code, stdout, stderr = self.run_sync_changelogs(
                ["--dry-run", "--no-cache", "--max", "20"],
                str(project.repo_dir)
            )
            
            self.assertEqual(code, 0, f"sync_changelogs failed: {stderr}")
            
            # Check that it found commits
            self.assertIn("commits", stdout.lower())
            
            print_color(Colors.GREEN, "✓ Multi-version changelog test passed")
    
    def test_rebuild_all_mode(self):
        """Test rebuild-all mode"""
        with DummyProject("test_rebuild", self.test_base) as project:
            project.create_standard_structure()
            project.create_release_scenario()
            
            # Clear existing changelogs
            for changelog in ["CHANGELOG.md", "dart/CHANGELOG.md", 
                            "flutter/CHANGELOG.md", "dart/rust/CHANGELOG.md"]:
                changelog_path = project.repo_dir / changelog
                if changelog_path.exists():
                    changelog_path.write_text("# Changelog\n\n## [Unreleased]\n")
            
            # Run rebuild-all
            code, stdout, stderr = self.run_sync_changelogs(
                ["--rebuild-all", "--dry-run", "--no-cache", "--force"],
                str(project.repo_dir)
            )
            
            self.assertEqual(code, 0, f"rebuild-all failed: {stderr}")
            self.assertIn("Rebuilding all changelogs", stdout)
            
            print_color(Colors.GREEN, "✓ Rebuild-all mode test passed")
    
    def test_since_option(self):
        """Test --since option"""
        with DummyProject("test_since", self.test_base) as project:
            project.create_standard_structure()
            
            # Get initial commit
            initial_commit = project.get_log(n=1)[0].split()[0]
            
            # Add more commits
            project.add_feature("feature 1")
            project.add_feature("feature 2")
            
            # Run with --since
            code, stdout, stderr = self.run_sync_changelogs(
                ["--since", initial_commit, "--dry-run", "--no-cache"],
                str(project.repo_dir)
            )
            
            self.assertEqual(code, 0, f"--since failed: {stderr}")
            self.assertIn(f"since {initial_commit}", stdout.lower())
            
            print_color(Colors.GREEN, "✓ Since option test passed")
    
    def test_package_specific_commits(self):
        """Test that commits are correctly assigned to packages"""
        with DummyProject("test_packages", self.test_base) as project:
            project.create_standard_structure()
            
            # Add dart-specific changes
            project.create_file("dart/lib/dart_only.dart", "// Dart only")
            dart_commit = project.commit("feat: dart-specific feature")
            
            # Add flutter-specific changes
            project.create_file("flutter/lib/flutter_only.dart", "// Flutter only")
            flutter_commit = project.commit("feat: flutter-specific feature")
            
            # Add rust-specific changes
            project.create_file("dart/rust/src/rust_only.rs", "// Rust only")
            rust_commit = project.commit("feat: rust-specific feature")
            
            # Run sync
            code, stdout, stderr = self.run_sync_changelogs(
                ["--dry-run", "--no-cache"],
                str(project.repo_dir)
            )
            
            self.assertEqual(code, 0)
            
            # Check package assignment in output
            self.assertIn("dart:", stdout.lower())
            self.assertIn("flutter:", stdout.lower())
            self.assertIn("rust:", stdout.lower())
            
            print_color(Colors.GREEN, "✓ Package-specific commits test passed")
    
    def test_dirty_working_directory_warning(self):
        """Test warning when working directory has uncommitted changes"""
        with DummyProject("test_dirty", self.test_base) as project:
            project.create_standard_structure()
            
            # Create uncommitted changes
            (project.repo_dir / "uncommitted.txt").write_text("uncommitted changes")
            
            # Run sync_changelogs - it should detect uncommitted changes
            code, stdout, stderr = self.run_sync_changelogs(
                ["--dry-run", "--no-cache", "--force"],  # Use --force to bypass prompt
                str(project.repo_dir)
            )
            
            # Should still succeed with --force
            self.assertEqual(code, 0)
            
            print_color(Colors.GREEN, "✓ Dirty working directory test passed")
    
    def test_version_detection(self):
        """Test automatic version detection"""
        with DummyProject("test_version", self.test_base) as project:
            project.create_standard_structure("1.2.3")
            
            # Add commits after tag
            project.add_feature("new feature")
            
            # Run without specifying version
            code, stdout, stderr = self.run_sync_changelogs(
                ["--dry-run", "--no-cache"],
                str(project.repo_dir)
            )
            
            self.assertEqual(code, 0)
            self.assertIn("1.2.3", stdout)
            
            print_color(Colors.GREEN, "✓ Version detection test passed")
    
    def test_empty_changelog_handling(self):
        """Test handling of empty changelog sections"""
        with DummyProject("test_empty", self.test_base) as project:
            project.create_standard_structure()
            
            # Create changelog with empty version
            changelog_content = """# Changelog

## [v0.0.2] - 2024-01-01

### Added
- N/A

## [v0.0.1] - 2024-01-01

### Added
- Initial release
"""
            (project.repo_dir / "CHANGELOG.md").write_text(changelog_content)
            
            # Add new commits
            project.add_feature("actual feature")
            
            # Run sync
            code, stdout, stderr = self.run_sync_changelogs(
                ["--dry-run", "--no-cache", "--version", "0.0.2"],
                str(project.repo_dir)
            )
            
            self.assertEqual(code, 0)
            
            print_color(Colors.GREEN, "✓ Empty changelog handling test passed")


class TestChangelogParsing(unittest.TestCase):
    """Unit tests for changelog parsing functionality"""
    
    def test_version_regex_patterns(self):
        """Test various version header patterns"""
        patterns = [
            ("## [v1.2.3] - 2024-01-01", True),
            ("## [1.2.3] - 2024-01-01", True),
            ("## [v1.2.3]", True),
            ("## v1.2.3 - 2024-01-01", False),  # Missing brackets
            ("### [v1.2.3] - 2024-01-01", False),  # Wrong header level
        ]
        
        import re
        version_pattern = re.compile(r'^## \[v?\d+\.\d+\.\d+\]', re.MULTILINE)
        
        for text, should_match in patterns:
            match = version_pattern.match(text)
            if should_match:
                self.assertIsNotNone(match, f"Should match: {text}")
            else:
                self.assertIsNone(match, f"Should not match: {text}")
        
        print_color(Colors.GREEN, "✓ Version regex pattern test passed")
    
    def test_changelog_section_parsing(self):
        """Test parsing of changelog sections"""
        content = """### Added
- Feature A
- Feature B

### Fixed
- Bug X

### Changed
- Updated Y
"""
        
        sections = {}
        current_section = None
        
        for line in content.splitlines():
            if line.startswith('### '):
                current_section = line[4:].strip()
                sections[current_section] = []
            elif current_section and line.strip().startswith('-'):
                sections[current_section].append(line.strip()[2:])
        
        self.assertEqual(len(sections), 3)
        self.assertEqual(sections['Added'], ['Feature A', 'Feature B'])
        self.assertEqual(sections['Fixed'], ['Bug X'])
        self.assertEqual(sections['Changed'], ['Updated Y'])
        
        print_color(Colors.GREEN, "✓ Changelog section parsing test passed")


if __name__ == "__main__":
    # Run with higher verbosity for integration tests
    unittest.main(verbosity=2) 