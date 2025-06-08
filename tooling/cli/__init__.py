"""
CLI tools for runtime_flutter_dart_rust_module_management_tools.

Unified tools:
- version_tools.py - Version management (get-tag, update, prepare, push)
- release_tools.py - Release management (check, notes, create, retag)
- commit_tools.py - Commit message generation
- changelog_tools.py - Changelog management (validate, analyze)
- pr_tools.py - Pull request management (create, open, list)
- contributor_analyzer.py - GitHub contributor analysis across organizations

Specialized tools:
- sync_changelogs.py - Advanced changelog synchronization (3900+ lines)
- cli_utils.py - Shared CLI utilities
"""

# List of available CLI tools
CLI_TOOLS = [
    'version_tools',
    'release_tools', 
    'commit_tools',
    'changelog_tools',
    'pr_tools',
    'contributor_analyzer',
    'sync_changelogs',
]

# Tool descriptions for help
TOOL_DESCRIPTIONS = {
    'version_tools': 'Version management (get-tag, update, prepare, push)',
    'release_tools': 'Release workflow (check, notes, create, retag)',
    'commit_tools': 'AI-powered commit message generation',
    'changelog_tools': 'Changelog validation and analysis',
    'pr_tools': 'Pull request creation and management',
    'contributor_analyzer': 'GitHub contributor analysis across organizations',
    'sync_changelogs': 'Advanced changelog synchronization with AI',
}

__all__ = CLI_TOOLS + ['cli_utils'] 