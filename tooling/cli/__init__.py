"""
Command-line interface tools for repository management.

Each CLI tool can be run independently:
- Directly: python tooling/cli/script_name.py
- As module: python -m tooling.cli.script_name
- As command: rt-command-name (after pip install)
"""

# List available CLI modules (but don't import them automatically)
CLI_MODULES = [
    'smart_commit',
    'smart_commit_fast',
    'sync_changelogs',
    'sync_changelog_ultra',
    'release',
    'prepare_new_patch',
    'push_new_patch',
    'retag_release',
    'update_version',
    'get_new_patch_tag',
    'validate_changelogs',
    'pre_release_check',
    'analyze_changelog_history',
    'generate_release_notes',
    'open_pull_request_current_tagged_branch',
    'setup_ai_tools',
    'setup_permissions',
    'install_gemini_cli',
]

# For backward compatibility, provide lazy imports
def __getattr__(name):
    """Lazy import of CLI modules."""
    if name in CLI_MODULES:
        import importlib
        return importlib.import_module(f'.{name}', __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = CLI_MODULES 