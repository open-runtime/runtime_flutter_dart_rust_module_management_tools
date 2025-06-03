#!/usr/bin/env python3
"""
generate_release_notes.py - Generate release notes from changelog files

This script generates polished release notes by:
1. Extracting changelog entries for the current version
2. Using AI to create a summary of highlights
3. Formatting everything into a complete release note

Compatible with GitHub Actions workflows on all platforms.

Requires: Python 3.6+

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved
"""

import os
import sys
import re
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Tuple
import argparse

# Add the script directory to Python path for imports
script_dir = Path(__file__).parent.absolute()
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

# Support both direct execution and package imports
import sys
import os

# Add parent directory to path for direct execution
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    # Try package import first (when installed via pip)
    from tooling.core.common_config import *
except ImportError:
    # Fall back to direct import (when running file directly)
    from core.common_config import *

# ============================================================================
# CONSTANTS
# ============================================================================

# Get dynamic package information
PACKAGE_INFO = get_package_info()

# Changelog files
CHANGELOG_FILES = {
    'root': PACKAGE_INFO['root']['changelog'],
    'dart': PACKAGE_INFO['dart']['changelog'],
    'flutter': PACKAGE_INFO['flutter']['changelog'], 
    'rust': PACKAGE_INFO['rust']['changelog']
}

PACKAGE_NAMES = {
    'root': 'Project Overview',
    'dart': 'Dart Package',
    'flutter': 'Flutter Package',
    'rust': 'Rust Package'
}

# ============================================================================
# CHANGELOG EXTRACTION
# ============================================================================

def extract_changelog_section(file_path: str, version: str) -> str:
    """Extract changelog section for a specific version"""
    # Remove 'v' prefix if present
    clean_version = version.lstrip('v')
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return ""
    
    # Find the version section
    pattern = rf'^## \[v{re.escape(clean_version)}\]'
    lines = content.split('\n')
    
    start_idx = None
    for i, line in enumerate(lines):
        if re.match(pattern, line):
            start_idx = i + 1
            break
    
    if start_idx is None:
        return ""
    
    # Find the next version header or end
    end_idx = len(lines)
    for i in range(start_idx, len(lines)):
        if re.match(r'^## \[v\d+\.\d+\.\d+\]', lines[i]):
            end_idx = i
            break
    
    # Extract and clean the section
    section_lines = lines[start_idx:end_idx]
    
    # Remove empty lines at start and end
    while section_lines and not section_lines[0].strip():
        section_lines.pop(0)
    while section_lines and not section_lines[-1].strip():
        section_lines.pop()
    
    return '\n'.join(section_lines)

def extract_all_changelogs(version: str) -> Dict[str, str]:
    """Extract changelog sections for all components"""
    changelogs = {}
    
    for component, file_path in CHANGELOG_FILES.items():
        content = extract_changelog_section(file_path, version)
        changelogs[component] = content
        
        if content:
            print(f"✅ Extracted {len(content.split(chr(10)))} lines from {component} changelog")
        else:
            print(f"⚠️  No changelog entry found for {component} (version {version})")
    
    return changelogs

# ============================================================================
# AI SUMMARY GENERATION
# ============================================================================

def generate_ai_summary(version: str, changelogs: Dict[str, str]) -> str:
    """Generate AI summary of changelog highlights"""
    # Check for API key
    if not check_api_key():
        return "AI summary generation skipped (no API key configured)"
    
    # Check for gemini-cli
    if not check_gemini_cli():
        return "AI summary generation skipped (gemini-cli not installed)"
    
    # Get package names
    names = detect_package_names()
    
    # Create the prompt
    prompt_lines = [
        f"You are writing a concise, polished release summary for version {version} of the {names.root_package_name} library.",
        "This library provides high-performance functionality with Dart, Flutter, and Rust components.",
        "",
        "Based on the changelog entries below, create a brief summary that:",
        "1. Highlights the most important changes users care about",
        "2. Groups related changes together logically", 
        "3. Uses clear, concise language",
        "4. Includes relevant emojis for visual appeal",
        "5. Focuses on user impact rather than implementation details",
        "6. Is no more than 20-30 lines total",
        "",
        "Format the summary with:",
        "- A brief 1-2 sentence overview at the top",
        "- Organized sections with markdown headers (##)",
        "- Bullet points for individual items",
        "- Bold text for emphasis on key features",
        "",
        "Here are the raw changelog entries:",
        "",
        "PROJECT OVERVIEW:",
        changelogs.get('root', 'No changes recorded'),
        "",
        "DART PACKAGE:",
        changelogs.get('dart', 'No changes recorded'),
        "",
        "FLUTTER PACKAGE:", 
        changelogs.get('flutter', 'No changes recorded'),
        "",
        "RUST ENGINE:",
        changelogs.get('rust', 'No changes recorded'),
        "",
        "Generate only the markdown summary, nothing else."
    ]
    
    prompt = '\n'.join(prompt_lines)
    
    # Try Pro model first, then fall back to Flash
    models = [
        ("gemini-2.5-pro-preview-05-06", 60),  # Pro with 60s timeout
        ("gemini-2.0-flash-exp", 30)           # Flash with 30s timeout
    ]
    
    for model, timeout in models:
        try:
            print(f"🤖 Generating AI summary with {model}...")
            
            # Run gemini-cli with stdin
            cmd = ['gemini-cli', 'prompt', '-', '--model', model]
            process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE, text=True)
            
            # Send prompt via stdin
            stdout, stderr = process.communicate(input=prompt, timeout=timeout)
            
            if process.returncode == 0:
                summary = stdout.strip()
                if summary:
                    print(f"✅ AI summary generated successfully with {model}")
                    return summary
                else:
                    print(f"⚠️  {model} returned empty summary")
                    if model == models[-1][0]:  # Last model
                        return "Failed to generate AI summary (empty response)"
                    else:
                        print("Trying fallback model...")
                        continue
            else:
                print(f"❌ {model} failed: {stderr}")
                if model == models[-1][0]:  # Last model
                    return f"Failed to generate AI summary: {stderr}"
                else:
                    print("Trying fallback model...")
                    continue
                    
        except subprocess.TimeoutExpired:
            print(f"❌ {model} timed out after {timeout}s")
            if model == models[-1][0]:  # Last model
                return "Failed to generate AI summary (timeout)"
            else:
                print("Trying fallback model...")
                continue
        except Exception as e:
            print(f"❌ Error with {model}: {e}")
            if model == models[-1][0]:  # Last model
                return f"Failed to generate AI summary: {str(e)}"
            else:
                print("Trying fallback model...")
                continue
    
    return "Failed to generate AI summary (all models failed)"

# ============================================================================
# RELEASE NOTES GENERATION
# ============================================================================

def generate_release_notes(args: argparse.Namespace) -> str:
    """Generate complete release notes"""
    # Get package names
    names = detect_package_names()
    
    # Extract changelogs
    changelogs = extract_all_changelogs(args.version)
    
    # Generate AI summary
    ai_summary = generate_ai_summary(args.version, changelogs)
    
    # Build release notes
    notes = []
    
    if args.is_tag_release:
        # Full release notes for tags
        notes.append(f"# Code {names.root_package_name} Dynamic Libraries Release {args.version}")
        notes.append("")
        notes.append("## Release Highlights")
        notes.append("")
        notes.append(ai_summary)
        notes.append("")
        notes.append("## Component Changelogs")
        notes.append("")
        
        # Add individual changelogs
        for component in ['root', 'dart', 'flutter', 'rust']:
            if component == 'root':
                notes.append(f"### {PACKAGE_NAMES[component]}")
            else:
                package_name = args.package_names.get(component, PACKAGE_NAMES[component])
                notes.append(f"### {PACKAGE_NAMES[component]} ({package_name})")
            notes.append("")
            
            if changelogs.get(component):
                notes.append(changelogs[component])
            else:
                notes.append("No changelog entries found for this version.")
            notes.append("")
        
        # Add download links
        notes.append("## Download Links")
        notes.append("")
        
        # Windows
        notes.append("### Windows (x86_64)")
        notes.append(f"- [Windows Libraries (Runtime)]({args.runtime_base_url}/windows_x64/{names.root_package_name}_windows_x64.zip)")
        notes.append(f"- [Windows Libraries (Pieces)]({args.pieces_base_url}/windows_x64/{names.root_package_name}_windows_x64.zip)")
        notes.append("")
        
        # Linux
        notes.append("### Linux (x86_64)")
        notes.append(f"- [Linux Libraries (Runtime)]({args.runtime_base_url}/linux_x64/{names.root_package_name}_linux_x64.zip)")
        notes.append(f"- [Linux Libraries (Pieces)]({args.pieces_base_url}/linux_x64/{names.root_package_name}_linux_x64.zip)")
        notes.append("")
        
        # macOS Intel
        notes.append("### MacOS (Intel x86_64)")
        notes.append(f"- [MacOS Intel Libraries (Runtime)]({args.runtime_base_url}/macos_x64/{names.root_package_name}_macos_x64.zip)")
        notes.append(f"- [MacOS Intel Libraries (Pieces)]({args.pieces_base_url}/macos_x64/{names.root_package_name}_macos_x64.zip)")
        notes.append("")
        
        # macOS ARM
        notes.append("### MacOS (Apple Silicon arm64)")
        notes.append(f"- [MacOS Apple Silicon Libraries (Runtime)]({args.runtime_base_url}/macos_arm64/{names.root_package_name}_macos_arm64.zip)")
        notes.append(f"- [MacOS Apple Silicon Libraries (Pieces)]({args.pieces_base_url}/macos_arm64/{names.root_package_name}_macos_arm64.zip)")
        notes.append("")
        
        # WASM
        notes.append("### WebAssembly (WASM)")
        notes.append(f"- [WebAssembly Files (Runtime)]({args.runtime_base_url}/wasm/{names.root_package_name}_wasm.zip)")
        notes.append(f"- [WebAssembly Files (Pieces)]({args.pieces_base_url}/wasm/{names.root_package_name}_wasm.zip)")
        notes.append(f"- [{args.rust_package_name}_bg.wasm (Runtime)]({args.runtime_base_url}/wasm/{args.rust_package_name}_bg.wasm)")
        notes.append(f"- [{args.rust_package_name}.js (Runtime)]({args.runtime_base_url}/wasm/{args.rust_package_name}.js)")
        notes.append(f"- [{args.rust_package_name}_bg.wasm (Pieces)]({args.pieces_base_url}/wasm/{args.rust_package_name}_bg.wasm)")
        notes.append(f"- [{args.rust_package_name}.js (Pieces)]({args.pieces_base_url}/wasm/{args.rust_package_name}.js)")
        notes.append("")
        
        # Storage buckets
        notes.append("## Storage Buckets")
        notes.append("You can view all available libraries in the Google Cloud Storage buckets here:")
        notes.append(f"- 🔗 [Google Cloud Console (Runtime)]({args.runtime_console_url})")
        notes.append(f"- 🔗 [Google Cloud Console (Pieces)]({args.pieces_console_url})")
        notes.append("")
        
        # Installation instructions
        notes.append("## Installation")
        notes.append("1. Download the appropriate libraries for your platform")
        notes.append("2. Extract the zip file")
        notes.append("3. Copy the libraries to your project:")
        notes.append("   - For Dart projects: Copy the library to your project's lib directory")
        notes.append("   - For Flutter projects: Copy the library to your project's assets directory")
        notes.append("   - For Web projects: Copy the WASM and JS files to your web assets directory")
        notes.append("")
        
        # Platform notes
        notes.append("## Notes")
        notes.append(f"- Windows: The library file is `{args.package_name}.dll`")
        notes.append(f"- Linux: The library file is `lib{args.package_name}.so`")
        notes.append(f"- MacOS: The library file is `{args.package_name}.dylib`")
        notes.append(f"- Web: The files are `{args.rust_package_name}_bg.wasm` and `{args.rust_package_name}.js`")
        notes.append("- Make sure to update your pubspec.yaml to reference the correct path to the library.")
        
    else:
        # PR draft release notes - CONCISE VERSION
        notes.append(f"# Draft Release for Pull Request #{args.pr_number}")
        notes.append("")
        notes.append(f"This is an automated draft release containing build artifacts for [Pull Request #{args.pr_number}]({args.pr_url}).")
        notes.append("")
        notes.append(f"**Build Info:**")
        notes.append(f"- Commit: `{args.commit_sha}`")
        notes.append(f"- Version: `{args.version}`")
        notes.append("")
        notes.append("**Note:** These artifacts are for testing purposes only and should not be used in production.")
        notes.append("")
        
        # Add AI summary only if it was successfully generated
        if ai_summary and not ai_summary.startswith("Failed to generate") and not ai_summary.startswith("AI summary generation skipped"):
            notes.append("## What's New")
            notes.append("")
            notes.append(ai_summary)
            notes.append("")
        
        # Add a simple link to view full changelogs with proper GitHub URLs
        notes.append("## Full Changelogs")
        notes.append("")
        notes.append("For detailed changes in this version, see:")
        
        # Extract the base GitHub URL from the PR URL
        if args.pr_url:
            # PR URL format: https://github.com/owner/repo/pull/123
            parts = args.pr_url.split('/')
            if len(parts) >= 5:
                base_url = '/'.join(parts[:5])  # https://github.com/owner/repo
                branch = f"blob/{args.commit_sha}"
                
                notes.append(f"- 📋 [Project Overview Changelog]({base_url}/{branch}/CHANGELOG.md)")
                notes.append(f"- 🎯 [Dart Package Changelog]({base_url}/{branch}/dart/CHANGELOG.md)")
                notes.append(f"- 📱 [Flutter Package Changelog]({base_url}/{branch}/flutter/CHANGELOG.md)")
                notes.append(f"- ⚙️ [Rust Package Changelog]({base_url}/{branch}/dart/rust/CHANGELOG.md)")
            else:
                # Fallback to relative links if URL parsing fails
                notes.append("- 📋 [Project Overview Changelog](CHANGELOG.md)")
                notes.append("- 🎯 [Dart Package Changelog](dart/CHANGELOG.md)")
                notes.append("- 📱 [Flutter Package Changelog](flutter/CHANGELOG.md)")
                notes.append("- ⚙️ [Rust Package Changelog](dart/rust/CHANGELOG.md)")
        else:
            # Fallback to relative links if no PR URL
            notes.append("- 📋 [Project Overview Changelog](CHANGELOG.md)")
            notes.append("- 🎯 [Dart Package Changelog](dart/CHANGELOG.md)")
            notes.append("- 📱 [Flutter Package Changelog](flutter/CHANGELOG.md)")
            notes.append("- ⚙️ [Rust Package Changelog](dart/rust/CHANGELOG.md)")
        
        notes.append("")
        
        # Add download links (Runtime only for PRs)
        notes.append("## Download Artifacts")
        notes.append("")
        
        notes.append("### Pre-built Libraries")
        notes.append(f"- **Windows (x64):** [{names.root_package_name}_windows_x64.zip]({args.runtime_base_url}/windows_x64/{names.root_package_name}_windows_x64.zip)")
        notes.append(f"- **Linux (x64):** [{names.root_package_name}_linux_x64.zip]({args.runtime_base_url}/linux_x64/{names.root_package_name}_linux_x64.zip)")
        notes.append(f"- **macOS (Intel):** [{names.root_package_name}_macos_x64.zip]({args.runtime_base_url}/macos_x64/{names.root_package_name}_macos_x64.zip)")
        notes.append(f"- **macOS (Apple Silicon):** [{names.root_package_name}_macos_arm64.zip]({args.runtime_base_url}/macos_arm64/{names.root_package_name}_macos_arm64.zip)")
        notes.append(f"- **WebAssembly:** [{names.root_package_name}_wasm.zip]({args.runtime_base_url}/wasm/{names.root_package_name}_wasm.zip)")
        notes.append("")
        
        notes.append("### Individual WASM Files")
        notes.append(f"- [{args.rust_package_name}_bg.wasm]({args.runtime_base_url}/wasm/{args.rust_package_name}_bg.wasm)")
        notes.append(f"- [{args.rust_package_name}.js]({args.runtime_base_url}/wasm/{args.rust_package_name}.js)")
        notes.append("")
        
        notes.append("📦 [Browse all artifacts in Google Cloud Storage]" + f"({args.runtime_console_url})")
    
    return '\n'.join(notes)

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Generate release notes from changelogs')
    
    # Required arguments
    parser.add_argument('--version', required=True, help='Version to generate notes for (e.g., v1.2.3)')
    parser.add_argument('--artifact-version', required=True, help='Version for artifact paths (e.g., v1.2.3 or PR-123)')
    parser.add_argument('--output', required=True, help='Output file path')
    
    # Release type
    parser.add_argument('--tag-release', action='store_true', help='This is a tag release (not a PR)')
    
    # PR information (for draft releases)
    parser.add_argument('--pr-number', help='PR number for draft releases')
    parser.add_argument('--pr-url', help='PR URL for draft releases')
    parser.add_argument('--commit-sha', help='Commit SHA for draft releases')
    
    # Get dynamic package names for defaults
    names = detect_package_names()
    
    # Package names
    parser.add_argument('--package-name', default=names.dart_package_name, help='Main package name')
    parser.add_argument('--rust-package-name', default=names.rust_package_name, help='Rust package name')
    parser.add_argument('--flutter-package-name', default=names.flutter_package_name, help='Flutter package name')
    
    # GCS paths
    parser.add_argument('--gcs-base-path', default=f'open-runtime-ci-cd-dynamic-libraries/{names.dart_package_name}',
                       help='GCS base path')
    
    args = parser.parse_args()
    
    # Ensure we're in project root
    ensure_project_root()
    
    print_header("Generating Release Notes")
    print(f"Version: {args.version}")
    print(f"Artifact Version: {args.artifact_version}")
    print(f"Output: {args.output}")
    print(f"Type: {'Tag Release' if args.tag_release else 'PR Draft'}")
    print()
    
    # Build URLs
    args.runtime_base_url = f"https://storage.googleapis.com/{args.gcs_base_path}/{args.artifact_version}"
    args.runtime_console_url = f"https://console.cloud.google.com/storage/browser/{args.gcs_base_path}/{args.artifact_version}"
    args.pieces_base_url = f"https://storage.googleapis.com/pieces-libraries/{args.package_name}/{args.artifact_version}"
    args.pieces_console_url = f"https://console.cloud.google.com/storage/browser/pieces-libraries/{args.package_name}/{args.artifact_version}"
    
    # Store package names
    args.package_names = {
        'dart': args.package_name,
        'flutter': args.flutter_package_name,
        'rust': args.rust_package_name
    }
    
    # For compatibility
    args.is_tag_release = args.tag_release
    
    # Generate release notes
    try:
        release_notes = generate_release_notes(args)
        
        # Write to output file
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(release_notes)
        
        print(f"✅ Release notes written to {args.output}")
        
        # Also print to stdout for debugging
        print()
        print("--- Generated Release Notes ---")
        print(release_notes)
        print("--- End of Release Notes ---")
        
        return 0
        
    except Exception as e:
        print_color(Colors.RED, f"Error generating release notes: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 