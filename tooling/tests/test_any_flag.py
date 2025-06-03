#!/usr/bin/env python3
"""
Test script to verify --any flag functionality in smart_commit tools
"""

import sys
import os
import tempfile
import shutil
import subprocess
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.common_config import Colors, print_color, run_command
from tests.test_helpers import DummyGitRepo


def test_any_flag_categorization():
    """Test that --any flag properly categorizes files in any repo structure"""
    print_color(Colors.PURPLE, "Testing --any flag file categorization")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a generic project structure (not dart/flutter/rust)
        repo = DummyGitRepo("test_generic_repo", tmpdir)
        
        # Create various files in different directories
        files_to_create = [
            "README.md",
            "package.json",
            ".gitignore",
            "src/index.js",
            "src/components/Button.js",
            "src/utils/helpers.js",
            "test/index.test.js",
            "test/components/Button.test.js",
            "docs/API.md",
            "docs/GUIDE.md",
            ".github/workflows/ci.yml",
            "scripts/build.sh",
            "config/webpack.config.js"
        ]
        
        for file_path in files_to_create:
            repo.create_file(file_path, f"// Content of {file_path}")
        
        # Stage all files
        run_command(['git', 'add', '.'])
        
        # Test categorization with --any flag
        from cli.smart_commit_fast import FastFileAnalyzer
        
        # Get all files
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            cwd=repo.repo_dir
        )
        
        all_files = result.stdout.strip().split('\n') if result.stdout else []
        
        # Test with any_structure=True
        categories = FastFileAnalyzer.categorize_files(all_files, any_structure=True)
        
        print_color(Colors.BLUE, "\nCategorized files (--any mode):")
        for category, files in sorted(categories.items()):
            print_color(Colors.GREEN, f"\n{category}:")
            for file in files:
                print(f"  - {file}")
        
        # Verify categorization
        assert "root" in categories  # README.md, package.json
        assert any(cat in categories for cat in ["index.js", "components", "utils"])  # src/ files
        assert "tests" in categories  # test/ files
        assert "docs" in categories  # docs/ files
        assert "config" in categories  # .gitignore, .github/
        
        print_color(Colors.GREEN, "\n✓ File categorization test passed!")
        
        # Test with any_structure=False (should use default categorization)
        categories_default = FastFileAnalyzer.categorize_files(all_files, any_structure=False)
        
        print_color(Colors.BLUE, "\nCategorized files (default mode):")
        for category, files in sorted(categories_default.items()):
            if files:
                print_color(Colors.YELLOW, f"\n{category}:")
                for file in files:
                    print(f"  - {file}")
        
        # In default mode, most files should go to "other" since they don't match dart/flutter/rust
        assert "other" in categories_default
        assert len(categories_default.get("other", [])) > 0
        
        print_color(Colors.GREEN, "\n✓ Default categorization test passed!")


def test_smart_commit_with_any_flag():
    """Test that smart_commit.py works with --any flag"""
    print_color(Colors.PURPLE, "\n\nTesting smart_commit.py with --any flag")
    
    # Check if smart_commit.py has the --any flag
    smart_commit_path = Path(__file__).parent.parent / "cli" / "smart_commit.py"
    
    result = subprocess.run(
        [sys.executable, str(smart_commit_path), "--help"],
        capture_output=True,
        text=True
    )
    
    if "--any" in result.stdout:
        print_color(Colors.GREEN, "✓ smart_commit.py has --any flag")
    else:
        print_color(Colors.RED, "✗ smart_commit.py missing --any flag")
    
    # Check smart_commit_fast.py
    smart_commit_fast_path = Path(__file__).parent.parent / "cli" / "smart_commit_fast.py"
    
    result = subprocess.run(
        [sys.executable, str(smart_commit_fast_path), "--help"],
        capture_output=True,
        text=True
    )
    
    if "--any" in result.stdout:
        print_color(Colors.GREEN, "✓ smart_commit_fast.py has --any flag")
    else:
        print_color(Colors.RED, "✗ smart_commit_fast.py missing --any flag")


if __name__ == "__main__":
    print_color(Colors.PURPLE, "=" * 60)
    print_color(Colors.PURPLE, "Testing --any flag functionality")
    print_color(Colors.PURPLE, "=" * 60)
    
    try:
        test_any_flag_categorization()
        test_smart_commit_with_any_flag()
        
        print_color(Colors.GREEN, "\n" + "=" * 60)
        print_color(Colors.GREEN, "All tests passed!")
        print_color(Colors.GREEN, "=" * 60)
    except Exception as e:
        print_color(Colors.RED, f"\nTest failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 