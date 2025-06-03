#!/usr/bin/env python3
"""
Test helper functions for creating dummy repositories and project structures
"""

import os
import sys
import tempfile
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.common_config import Colors, print_color, run_command


class DummyGitRepo:
    """Helper class for creating dummy git repositories for testing"""
    
    def __init__(self, name: str = "test_repo", base_dir: Optional[str] = None):
        """Initialize a dummy git repository"""
        self.name = name
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            self.temp_dir = tempfile.mkdtemp(prefix=f"{name}_")
            self.base_dir = Path(self.temp_dir)
        
        self.repo_dir = self.base_dir / name
        self.repo_dir.mkdir(parents=True, exist_ok=True)
        
        # Store original directory
        self.original_cwd = os.getcwd()
        
        # Initialize git repo
        os.chdir(self.repo_dir)
        run_command(['git', 'init'])
        run_command(['git', 'config', 'user.name', 'Test User'])
        run_command(['git', 'config', 'user.email', 'test@example.com'])
        
    def __enter__(self):
        """Context manager entry"""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup"""
        os.chdir(self.original_cwd)
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_file(self, path: str, content: str) -> Path:
        """Create a file with content"""
        file_path = self.repo_dir / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        return file_path
    
    def commit(self, message: str, files: Optional[List[str]] = None, 
               date: Optional[datetime] = None) -> str:
        """Create a commit with optional specific date"""
        if files:
            for file in files:
                run_command(['git', 'add', file])
        else:
            run_command(['git', 'add', '-A'])
        
        # Set commit date if provided
        env = os.environ.copy()
        if date:
            date_str = date.strftime('%Y-%m-%d %H:%M:%S')
            env['GIT_AUTHOR_DATE'] = date_str
            env['GIT_COMMITTER_DATE'] = date_str
        
        # Use subprocess directly for env support
        result = subprocess.run(
            ['git', 'commit', '-m', message],
            env=env,
            capture_output=True,
            text=True
        )
        code = result.returncode
        commit_hash = result.stdout
        
        if code == 0:
            # Get the short hash
            code, short_hash, _ = run_command(['git', 'rev-parse', '--short', 'HEAD'])
            return short_hash.strip() if code == 0 else ""
        return ""
    
    def tag(self, tag_name: str, message: Optional[str] = None) -> bool:
        """Create a tag"""
        cmd = ['git', 'tag']
        if message:
            cmd.extend(['-a', tag_name, '-m', message])
        else:
            cmd.append(tag_name)
        
        code, _, _ = run_command(cmd)
        return code == 0
    
    def create_branch(self, branch_name: str, checkout: bool = True) -> bool:
        """Create and optionally checkout a branch"""
        code, _, _ = run_command(['git', 'branch', branch_name])
        if code == 0 and checkout:
            code, _, _ = run_command(['git', 'checkout', branch_name])
        return code == 0
    
    def merge(self, branch_name: str, no_ff: bool = False) -> bool:
        """Merge a branch"""
        cmd = ['git', 'merge', branch_name]
        if no_ff:
            cmd.insert(2, '--no-ff')
        
        code, _, _ = run_command(cmd)
        return code == 0
    
    def get_log(self, format: str = "oneline", n: int = 10) -> List[str]:
        """Get git log"""
        code, output, _ = run_command(['git', 'log', f'--{format}', f'-n{n}'])
        if code == 0:
            return output.strip().split('\n') if output else []
        return []


class DummyProject(DummyGitRepo):
    """Helper class for creating dummy Dart/Flutter/Rust projects"""
    
    def __init__(self, name: str = "test_project", base_dir: Optional[str] = None):
        """Initialize a dummy project with standard structure"""
        super().__init__(name, base_dir)
        self.dart_name = f"runtime_{name}"
        self.flutter_name = f"runtime_flutter_{name}"
        self.rust_name = f"runtime_rust_{name}"
        
    def create_standard_structure(self, version: str = "0.0.1"):
        """Create the standard project structure"""
        # Create dart package
        self.create_file("dart/pubspec.yaml", f"""name: {self.dart_name}
version: {version}
description: Dart package for {self.name}

environment:
  sdk: '>=2.12.0 <3.0.0'

dependencies:
  ffi: ^2.0.0
""")
        
        self.create_file("dart/lib/src/core.dart", """// Core functionality
class Core {
  void doSomething() {
    print('Doing something');
  }
}
""")
        
        # Create flutter package
        self.create_file("flutter/pubspec.yaml", f"""name: {self.flutter_name}
version: {version}
description: Flutter package for {self.name}

environment:
  sdk: '>=2.12.0 <3.0.0'
  flutter: '>=2.0.0'

dependencies:
  flutter:
    sdk: flutter
  {self.dart_name}:
    path: ../dart
""")
        
        self.create_file("flutter/lib/widgets.dart", """import 'package:flutter/material.dart';

class MyWidget extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container();
  }
}
""")
        
        # Create rust package
        self.create_file("dart/rust/Cargo.toml", f"""[package]
name = "{self.rust_name}"
version = "{version}"
edition = "2021"

[dependencies]
""")
        
        self.create_file("dart/rust/src/lib.rs", """#[no_mangle]
pub extern "C" fn hello_rust() -> *const u8 {
    "Hello from Rust!\\0".as_ptr()
}
""")
        
        # Create changelogs
        self.create_changelog("CHANGELOG.md", version, "Initial release")
        self.create_changelog("dart/CHANGELOG.md", version, "Initial Dart package release")
        self.create_changelog("flutter/CHANGELOG.md", version, "Initial Flutter package release")
        self.create_changelog("dart/rust/CHANGELOG.md", version, "Initial Rust FFI bindings")
        
        # Create initial commit
        self.commit(f"Initial commit - v{version}")
        self.tag(f"v{version}")
        
    def create_changelog(self, path: str, version: str, content: str, 
                        date: Optional[str] = None):
        """Create a changelog file"""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
            
        changelog_content = f"""# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v{version}] - {date}

### Added
- {content}
"""
        self.create_file(path, changelog_content)
    
    def add_feature(self, feature_name: str, commit_message: Optional[str] = None,
                   files: Optional[Dict[str, str]] = None) -> str:
        """Add a feature with changes to multiple files"""
        if not commit_message:
            commit_message = f"feat: add {feature_name}"
            
        if not files:
            # Default files to modify
            files = {
                "dart/lib/src/feature.dart": f"""// {feature_name} implementation
class {feature_name.title().replace(' ', '')} {{
  void execute() {{
    print('Executing {feature_name}');
  }}
}}
""",
                "flutter/lib/feature_widget.dart": f"""import 'package:flutter/material.dart';

class {feature_name.title().replace(' ', '')}Widget extends StatelessWidget {{
  @override
  Widget build(BuildContext context) {{
    return Text('{feature_name}');
  }}
}}
"""
            }
        
        # Create files
        for path, content in files.items():
            self.create_file(path, content)
        
        # Commit
        return self.commit(commit_message)
    
    def add_fix(self, bug_description: str, commit_message: Optional[str] = None) -> str:
        """Add a bug fix"""
        if not commit_message:
            commit_message = f"fix: {bug_description}"
        
        # Modify an existing file
        core_file = self.repo_dir / "dart/lib/src/core.dart"
        if core_file.exists():
            content = core_file.read_text()
            content += f"\n  // Fix for: {bug_description}\n"
            core_file.write_text(content)
        
        return self.commit(commit_message)
    
    def create_release_scenario(self) -> Dict[str, List[str]]:
        """Create a complex release scenario with multiple commits"""
        commits = {
            "features": [],
            "fixes": [],
            "other": []
        }
        
        # Add some features
        commits["features"].append(
            self.add_feature("vector search", "feat: implement vector search algorithm")
        )
        commits["features"].append(
            self.add_feature("caching layer", "feat: add caching layer for performance")
        )
        
        # Add some fixes
        commits["fixes"].append(
            self.add_fix("memory leak in search", "fix: resolve memory leak in vector search")
        )
        commits["fixes"].append(
            self.add_fix("null pointer exception", "fix: handle null values in cache")
        )
        
        # Add some other changes
        self.create_file("docs/API.md", "# API Documentation\n\nNew API docs")
        commits["other"].append(self.commit("docs: add API documentation"))
        
        self.create_file(".github/workflows/test.yml", "name: Test\non: [push]")
        commits["other"].append(self.commit("ci: add GitHub Actions workflow"))
        
        return commits
    
    def simulate_pr_workflow(self, pr_number: int = 42) -> Dict[str, any]:
        """Simulate a PR workflow with feature branch"""
        # Create feature branch
        self.create_branch("feature/awesome-feature")
        
        # Add changes
        commits = []
        commits.append(self.add_feature("awesome feature", "feat: add awesome feature"))
        commits.append(self.add_fix("edge case handling", "fix: handle edge cases in awesome feature"))
        
        # Create PR-style merge commit
        self.create_branch("main", checkout=True)
        self.merge("feature/awesome-feature", no_ff=True)
        
        # Get merge commit
        code, merge_commit, _ = run_command(['git', 'rev-parse', 'HEAD'])
        
        return {
            "pr_number": pr_number,
            "branch": "feature/awesome-feature",
            "commits": commits,
            "merge_commit": merge_commit.strip() if code == 0 else None
        }


def create_test_scenario(scenario: str) -> DummyProject:
    """Create a specific test scenario"""
    scenarios = {
        "simple": lambda p: p.create_standard_structure(),
        "release": lambda p: (p.create_standard_structure(), p.create_release_scenario()),
        "pr": lambda p: (p.create_standard_structure(), p.simulate_pr_workflow()),
        "multi_version": lambda p: create_multi_version_scenario(p)
    }
    
    project = DummyProject(f"test_{scenario}")
    if scenario in scenarios:
        scenarios[scenario](project)
    else:
        project.create_standard_structure()
    
    return project


def create_multi_version_scenario(project: DummyProject):
    """Create a scenario with multiple versions and releases"""
    # v0.0.1 - Initial
    project.create_standard_structure("0.0.1")
    
    # v0.0.2 - Add features
    project.add_feature("search functionality")
    project.add_feature("export capability")
    project.add_fix("initialization bug")
    
    # Update versions
    for file in ["dart/pubspec.yaml", "flutter/pubspec.yaml"]:
        content = (project.repo_dir / file).read_text()
        content = content.replace("version: 0.0.1", "version: 0.0.2")
        (project.repo_dir / file).write_text(content)
    
    project.commit("chore: bump version to 0.0.2")
    project.tag("v0.0.2")
    
    # v0.0.3 - More changes
    project.add_feature("advanced filtering")
    project.add_fix("performance issue in search")
    project.add_fix("UI glitch in export")
    
    # Update versions
    for file in ["dart/pubspec.yaml", "flutter/pubspec.yaml"]:
        content = (project.repo_dir / file).read_text()
        content = content.replace("version: 0.0.2", "version: 0.0.3")
        (project.repo_dir / file).write_text(content)
    
    project.commit("chore: bump version to 0.0.3")
    project.tag("v0.0.3")
    
    # Add some unreleased changes
    project.add_feature("beta feature")
    project.add_fix("edge case in filtering")
    
    return project


if __name__ == "__main__":
    # Demo the test helpers
    print_color(Colors.PURPLE, "Test Helper Demo")
    print_color(Colors.PURPLE, "=" * 50)
    
    # Create a simple project
    with DummyProject("demo_project") as project:
        project.create_standard_structure()
        
        print_color(Colors.GREEN, f"✓ Created project at: {project.repo_dir}")
        print_color(Colors.BLUE, "\nProject structure:")
        
        # Show structure
        for root, dirs, files in os.walk(project.repo_dir):
            level = root.replace(str(project.repo_dir), '').count(os.sep)
            indent = ' ' * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 2 * (level + 1)
            for file in files:
                if not file.startswith('.'):
                    print(f"{subindent}{file}")
        
        # Show git log
        print_color(Colors.BLUE, "\nGit log:")
        for line in project.get_log():
            print_color(Colors.GRAY, f"  {line}") 