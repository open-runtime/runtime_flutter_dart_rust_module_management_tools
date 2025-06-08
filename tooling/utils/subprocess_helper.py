"""
Helper functions for subprocess calls that work with both direct execution and package installation.
"""

import subprocess
import sys
import os
from pathlib import Path


def run_cli_tool(tool_name, args=None, **kwargs):
    """
    Run a CLI tool with fallback support for different execution methods.
    
    Args:
        tool_name: Name of the tool (e.g., 'smart_commit', 'sync_changelogs')
        args: List of arguments to pass to the tool
        **kwargs: Additional arguments for subprocess.run
        
    Returns:
        subprocess.CompletedProcess
    """
    if args is None:
        args = []
    
    # Try different execution methods in order of preference
    methods = [
        # 1. Try installed command (fastest, works after pip install)
        _try_installed_command,
        # 2. Try module execution (works with package structure)
        _try_module_execution,
        # 3. Try direct script execution (fallback for development)
        _try_direct_execution,
    ]
    
    last_error = None
    for method in methods:
        try:
            return method(tool_name, args, **kwargs)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            last_error = e
            continue
    
    # If all methods failed, raise the last error
    if last_error:
        raise last_error
    else:
        raise RuntimeError(f"Could not find or execute tool: {tool_name}")


def _try_installed_command(tool_name, args, **kwargs):
    """Try running as an installed command."""
    # Map tool names to command names
    command_map = {
        'smart_commit': 'runtime_fdr_management_tools-commit',
        'smart_commit_fast': 'runtime_fdr_management_tools-commit-fast',
        'sync_changelogs': 'runtime_fdr_management_tools-changelog',
        'sync_changelog_ultra': 'runtime_fdr_management_tools-changelog-ultra',
        'analyze_changelog_history': 'runtime_fdr_management_tools-changelog-analyze',
        'release': 'runtime_fdr_management_tools-release',
        'prepare_new_patch': 'runtime_fdr_management_tools-prepare-patch',
        'push_new_patch': 'runtime_fdr_management_tools-push-patch',
        'retag_release': 'runtime_fdr_management_tools-retag',
        'update_version': 'runtime_fdr_management_tools-version',
        'get_new_patch_tag': 'runtime_fdr_management_tools-next-tag',
        'validate_changelogs': 'runtime_fdr_management_tools-validate',
        'pre_release_check': 'runtime_fdr_management_tools-prerelease-check',
        'open_pull_request_current_tagged_branch': 'runtime_fdr_management_tools-pr',
        'generate_release_notes': 'runtime_fdr_management_tools-release-notes',
        'setup_ai_tools': 'runtime_fdr_management_tools-setup',
        'setup_permissions': 'runtime_fdr_management_tools-setup-permissions',
        'install_gemini_cli': 'runtime_fdr_management_tools-install-gemini',
    }
    
    command = command_map.get(tool_name, f'runtime_fdr_management_tools-{tool_name.replace("_", "-")}')
    return subprocess.run([command] + args, check=True, **kwargs)


def _try_module_execution(tool_name, args, **kwargs):
    """Try running as a Python module."""
    return subprocess.run(
        [sys.executable, '-m', f'tooling.cli.{tool_name}'] + args,
        check=True,
        **kwargs
    )


def _try_direct_execution(tool_name, args, **kwargs):
    """Try running the script directly."""
    # Find the tooling directory
    current_file = Path(__file__).resolve()
    tooling_dir = current_file.parent.parent  # Go up from utils to tooling
    script_path = tooling_dir / 'cli' / f'{tool_name}.py'
    
    if not script_path.exists():
        # Try from project root
        project_root = tooling_dir.parent
        script_path = project_root / 'tooling' / 'cli' / f'{tool_name}.py'
    
    if not script_path.exists():
        raise FileNotFoundError(f"Could not find script: {tool_name}.py")
    
    return subprocess.run(
        [sys.executable, str(script_path)] + args,
        check=True,
        **kwargs
    )


# Convenience function for scripts that need to call other tools
def call_tool(tool_name, *args, capture_output=False, text=True, **kwargs):
    """
    Simplified interface for calling other CLI tools.
    
    Example:
        result = call_tool('get_new_patch_tag', '--format', 'json')
        print(result.stdout)
    """
    return run_cli_tool(
        tool_name,
        list(args),
        capture_output=capture_output,
        text=text,
        **kwargs
    ) 