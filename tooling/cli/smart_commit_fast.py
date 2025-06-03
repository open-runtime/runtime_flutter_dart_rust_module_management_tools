#!/usr/bin/env python3
"""
smart_commit_fast.py - Fast AI-powered commit message generator

Default: Ultra-fast Flash model (2-3s) for everyday commits
--max flag: Comprehensive Pro model analysis for complex changes

This is an optimized version that prioritizes speed while maintaining quality.

Requires: Python 3.6+, git, gemini-cli

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved
"""

import os
import sys
import subprocess
import tempfile
import argparse
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import time
import hashlib
import json
from datetime import datetime, timedelta

# Add the script directory to Python path for imports
script_dir = Path(__file__).parent.absolute()
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

# Import our common configuration
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
except ImportError:
    print("Error: Could not import common_config.py", file=sys.stderr)
    print("Make sure common_config.py exists in the same directory", file=sys.stderr)
    sys.exit(1)

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Configuration for smart commit fast mode"""
    QUICK_MODE = True  # Default to quick mode
    MAX_DIFF_LINES = 500  # Limit diff size per package
    MAX_FILES_PER_PACKAGE = 5  # Limit files shown in summary
    MAX_DIFF_PER_FILE = 100  # Max lines per file diff
    SAMPLE_DIFFS_COUNT = 5  # Number of sample diffs in quick mode
    SKIP_CROSS_ANALYSIS = False
    
    # Model selection
    FLASH_MODEL = "gemini-2.0-flash-exp"
    PRO_MODEL = "gemini-2.0-flash-exp"
    
    @classmethod
    def set_max_mode(cls):
        """Switch to max analysis mode"""
        cls.QUICK_MODE = False
        os.environ['GEMINI_MODEL'] = cls.PRO_MODEL

# ============================================================================
# TEXT SANITIZATION (Reuse from common_config)
# ============================================================================

class FastTextSanitizer:
    """Fast text sanitization optimized for performance"""
    
    # Compile regex patterns once for performance
    ANSI_ESCAPE = re.compile(r'\x1b(?:\[[0-9;]*[mGKHJFlh]|\([AB]|\[[0-9;]*[hl])')
    SPINNER_CHARS = re.compile(r'[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]')
    PROGRESS_LINES = re.compile(r'^\s*[\|\/\-\\⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]')
    MARKDOWN_CODE_BLOCKS = re.compile(r'^```[a-zA-Z0-9_-]*\s*$', re.MULTILINE)
    
    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """Fast sanitization of text"""
        if not text:
            return ""
        
        # Apply all regex replacements in one pass
        text = cls.ANSI_ESCAPE.sub('', text)
        text = cls.SPINNER_CHARS.sub('', text)
        text = text.replace('\r', '')
        
        # Remove control characters efficiently
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
        
        return text
    
    @classmethod
    def clean_ai_response(cls, response: str) -> str:
        """Clean AI response quickly"""
        if not response:
            return ""
        
        response = cls.sanitize_text(response)
        
        # Remove markdown code blocks
        response = cls.MARKDOWN_CODE_BLOCKS.sub('', response)
        response = response.replace('```', '')
        
        # Remove progress indicator lines
        lines = response.split('\n')
        lines = [line for line in lines if not cls.PROGRESS_LINES.match(line)]
        
        # Trim empty lines efficiently
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        
        return '\n'.join(lines)

# ============================================================================
# ENHANCED CONTEXT GATHERING (Phase 1)
# ============================================================================

class EnhancedContextGatherer:
    """Gather rich context for better analysis"""
    
    def __init__(self):
        self.sanitizer = FastTextSanitizer()
    
    def get_file_history(self, file: str, num_commits: int = 5) -> Dict[str, any]:
        """Get recent history of the file"""
        try:
            # Get recent commits that touched this file
            result = subprocess.run(
                ['git', 'log', '--oneline', '-n', str(num_commits), '--', file],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return {"error": "Failed to get history"}
            
            commits = result.stdout.strip().split('\n') if result.stdout else []
            
            # Get more detailed info for recent commits
            history = {
                "recent_commits": commits,
                "last_modified": self._get_last_modified_date(file),
                "change_frequency": len(commits)
            }
            
            # Get the last significant change
            if commits:
                last_commit_hash = commits[0].split()[0]
                diff_result = subprocess.run(
                    ['git', 'show', '--no-patch', '--format=%B', last_commit_hash],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if diff_result.returncode == 0:
                    history["last_commit_message"] = diff_result.stdout.strip()
            
            return history
            
        except Exception as e:
            return {"error": str(e)}
    
    def _get_last_modified_date(self, file: str) -> Optional[str]:
        """Get last modified date of file"""
        try:
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%cd', '--date=short', '--', file],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout.strip()
        except:
            pass
        return None
    
    def get_related_issues(self) -> Dict[str, List[str]]:
        """Extract issue numbers from branch name and recent commits"""
        issues = {
            "branch_issues": [],
            "commit_issues": [],
            "pr_references": []
        }
        
        try:
            # Get current branch name
            result = subprocess.run(
                ['git', 'branch', '--show-current'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode == 0 and result.stdout:
                branch = result.stdout.strip()
                # Common issue patterns in branch names
                issue_patterns = [
                    r'issue[/-]?(\d+)',
                    r'bug[/-]?(\d+)',
                    r'feature[/-]?(\d+)',
                    r'fix[/-]?(\d+)',
                    r'#(\d+)',
                    r'gh[/-]?(\d+)'
                ]
                
                for pattern in issue_patterns:
                    matches = re.findall(pattern, branch, re.IGNORECASE)
                    issues["branch_issues"].extend(matches)
            
            # Get recent commit messages for issue references
            result = subprocess.run(
                ['git', 'log', '--oneline', '-n', '10'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout:
                commit_messages = result.stdout.strip()
                # Look for issue references in commits
                issue_refs = re.findall(r'#(\d+)', commit_messages)
                issues["commit_issues"] = list(set(issue_refs))
                
                # Look for PR references
                pr_refs = re.findall(r'PR[# ]?(\d+)', commit_messages, re.IGNORECASE)
                issues["pr_references"] = list(set(pr_refs))
            
        except Exception:
            pass
        
        return issues
    
    def get_code_symbols(self, file: str, diff: str) -> Dict[str, List[str]]:
        """Extract symbols (functions, classes) from file changes"""
        symbols = {
            "functions": [],
            "classes": [],
            "imports": [],
            "exports": [],
            "modified_symbols": []
        }
        
        # Determine file type
        ext = Path(file).suffix.lower()
        
        if ext in ['.py']:
            symbols.update(self._extract_python_symbols(diff))
        elif ext in ['.dart']:
            symbols.update(self._extract_dart_symbols(diff))
        elif ext in ['.rs']:
            symbols.update(self._extract_rust_symbols(diff))
        elif ext in ['.js', '.ts', '.jsx', '.tsx']:
            symbols.update(self._extract_javascript_symbols(diff))
        
        return symbols
    
    def _extract_python_symbols(self, diff: str) -> Dict[str, List[str]]:
        """Extract Python symbols from diff"""
        symbols = {
            "functions": [],
            "classes": [],
            "imports": []
        }
        
        lines = diff.split('\n')
        for line in lines:
            # Look for added/modified lines
            if line.startswith('+') and not line.startswith('+++'):
                clean_line = line[1:].strip()
                
                # Functions
                func_match = re.match(r'def\s+(\w+)\s*\(', clean_line)
                if func_match:
                    symbols["functions"].append(func_match.group(1))
                
                # Classes
                class_match = re.match(r'class\s+(\w+)\s*[\(:]', clean_line)
                if class_match:
                    symbols["classes"].append(class_match.group(1))
                
                # Imports
                import_match = re.match(r'(?:from\s+\S+\s+)?import\s+(.+)', clean_line)
                if import_match:
                    symbols["imports"].append(import_match.group(1).strip())
        
        return symbols
    
    def _extract_dart_symbols(self, diff: str) -> Dict[str, List[str]]:
        """Extract Dart symbols from diff"""
        symbols = {
            "functions": [],
            "classes": [],
            "imports": []
        }
        
        lines = diff.split('\n')
        for line in lines:
            if line.startswith('+') and not line.startswith('+++'):
                clean_line = line[1:].strip()
                
                # Functions/methods
                func_patterns = [
                    r'(?:void|int|String|bool|double|Future|Stream|dynamic)\s+(\w+)\s*\(',
                    r'(\w+)\s*\([^)]*\)\s*(?:async\s*)?{',
                ]
                for pattern in func_patterns:
                    match = re.search(pattern, clean_line)
                    if match:
                        symbols["functions"].append(match.group(1))
                
                # Classes
                class_match = re.match(r'class\s+(\w+)', clean_line)
                if class_match:
                    symbols["classes"].append(class_match.group(1))
                
                # Imports
                import_match = re.match(r'import\s+[\'"]([^\'"])+[\'"]', clean_line)
                if import_match:
                    symbols["imports"].append(import_match.group(1))
        
        return symbols
    
    def _extract_rust_symbols(self, diff: str) -> Dict[str, List[str]]:
        """Extract Rust symbols from diff"""
        symbols = {
            "functions": [],
            "structs": [],
            "traits": [],
            "imports": []
        }
        
        lines = diff.split('\n')
        for line in lines:
            if line.startswith('+') and not line.startswith('+++'):
                clean_line = line[1:].strip()
                
                # Functions
                func_match = re.match(r'(?:pub\s+)?(?:async\s+)?fn\s+(\w+)', clean_line)
                if func_match:
                    symbols["functions"].append(func_match.group(1))
                
                # Structs
                struct_match = re.match(r'(?:pub\s+)?struct\s+(\w+)', clean_line)
                if struct_match:
                    symbols["structs"].append(struct_match.group(1))
                
                # Traits
                trait_match = re.match(r'(?:pub\s+)?trait\s+(\w+)', clean_line)
                if trait_match:
                    symbols["traits"].append(trait_match.group(1))
                
                # Use statements
                use_match = re.match(r'use\s+(.+);', clean_line)
                if use_match:
                    symbols["imports"].append(use_match.group(1))
        
        return symbols
    
    def _extract_javascript_symbols(self, diff: str) -> Dict[str, List[str]]:
        """Extract JavaScript/TypeScript symbols from diff"""
        symbols = {
            "functions": [],
            "classes": [],
            "imports": [],
            "exports": []
        }
        
        lines = diff.split('\n')
        for line in lines:
            if line.startswith('+') and not line.startswith('+++'):
                clean_line = line[1:].strip()
                
                # Functions
                func_patterns = [
                    r'function\s+(\w+)',
                    r'const\s+(\w+)\s*=\s*(?:async\s+)?\(',
                    r'(?:export\s+)?(?:async\s+)?function\s+(\w+)',
                ]
                for pattern in func_patterns:
                    match = re.search(pattern, clean_line)
                    if match:
                        symbols["functions"].append(match.group(1))
                
                # Classes
                class_match = re.match(r'(?:export\s+)?class\s+(\w+)', clean_line)
                if class_match:
                    symbols["classes"].append(class_match.group(1))
                
                # Imports
                import_match = re.match(r'import\s+(.+)\s+from', clean_line)
                if import_match:
                    symbols["imports"].append(import_match.group(1).strip())
                
                # Exports
                export_match = re.match(r'export\s+(?:default\s+)?(.+)', clean_line)
                if export_match and 'from' not in export_match.group(1):
                    symbols["exports"].append(export_match.group(1).strip())
        
        return symbols
    
    def get_dependency_hints(self, file: str) -> Dict[str, List[str]]:
        """Get hints about file dependencies"""
        deps = {
            "imports_this_file": [],
            "imported_by_this_file": [],
            "test_files": [],
            "related_files": []
        }
        
        try:
            # Find files that might import this file
            filename = Path(file).name
            stem = Path(file).stem
            
            # Search for imports of this file
            grep_patterns = []
            
            if file.endswith('.py'):
                grep_patterns.append(f"import.*{stem}")
                grep_patterns.append(f"from.*{stem}")
            elif file.endswith('.dart'):
                grep_patterns.append(f"import.*{filename}")
            elif file.endswith('.rs'):
                grep_patterns.append(f"use.*{stem}")
            elif file.endswith(('.js', '.ts')):
                grep_patterns.append(f"import.*from.*{filename}")
                grep_patterns.append(f"require.*{filename}")
            
            for pattern in grep_patterns:
                result = subprocess.run(
                    ['git', 'grep', '-l', pattern],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0 and result.stdout:
                    importing_files = result.stdout.strip().split('\n')
                    deps["imports_this_file"].extend(
                        [f for f in importing_files if f != file]
                    )
            
            # Find test files
            test_patterns = [
                f"{stem}_test",
                f"test_{stem}",
                f"{stem}.test",
                f"{stem}.spec"
            ]
            
            for pattern in test_patterns:
                result = subprocess.run(
                    ['find', '.', '-name', f"*{pattern}*", '-type', 'f'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0 and result.stdout:
                    test_files = result.stdout.strip().split('\n')
                    deps["test_files"].extend([f.lstrip('./') for f in test_files if f])
            
        except Exception:
            pass
        
        # Remove duplicates
        for key in deps:
            deps[key] = list(set(deps[key]))
        
        return deps
    
    def gather_enhanced_context(self, files: List[str], diffs: Dict[str, str]) -> Dict[str, any]:
        """Gather all enhanced context for the commit"""
        context = {
            "timestamp": datetime.now().isoformat(),
            "branch_info": self._get_branch_info(),
            "issues": self.get_related_issues(),
            "file_contexts": {},
            "overall_stats": {
                "total_files": len(files),
                "languages": set(),
                "has_tests": False,
                "has_docs": False
            }
        }
        
        # Analyze each file
        for file in files:
            if not file:
                continue
            
            file_context = {
                "history": self.get_file_history(file, num_commits=3),
                "symbols": self.get_code_symbols(file, diffs.get(file, "")),
                "dependencies": self.get_dependency_hints(file),
                "file_type": self._determine_file_type(file)
            }
            
            context["file_contexts"][file] = file_context
            
            # Update overall stats
            if file_context["file_type"]["language"]:
                context["overall_stats"]["languages"].add(file_context["file_type"]["language"])
            if file_context["file_type"]["is_test"]:
                context["overall_stats"]["has_tests"] = True
            if file_context["file_type"]["is_doc"]:
                context["overall_stats"]["has_docs"] = True
        
        return context
    
    def _get_branch_info(self) -> Dict[str, str]:
        """Get current branch information"""
        info = {}
        try:
            # Current branch
            result = subprocess.run(
                ['git', 'branch', '--show-current'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                info["current_branch"] = result.stdout.strip()
            
            # Upstream branch
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                info["upstream_branch"] = result.stdout.strip()
            
            # Commits ahead/behind
            result = subprocess.run(
                ['git', 'rev-list', '--left-right', '--count', 'HEAD...@{u}'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0 and result.stdout:
                ahead, behind = result.stdout.strip().split('\t')
                info["commits_ahead"] = int(ahead)
                info["commits_behind"] = int(behind)
        
        except Exception:
            pass
        
        return info
    
    def _determine_file_type(self, file: str) -> Dict[str, any]:
        """Determine file type and characteristics"""
        path = Path(file)
        ext = path.suffix.lower()
        name = path.name.lower()
        
        file_type = {
            "extension": ext,
            "language": None,
            "is_test": False,
            "is_doc": False,
            "is_config": False,
            "is_generated": False
        }
        
        # Language detection
        lang_map = {
            '.py': 'python',
            '.dart': 'dart',
            '.rs': 'rust',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.go': 'go',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'c',
            '.hpp': 'cpp',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.rb': 'ruby',
            '.php': 'php',
            '.cs': 'csharp',
            '.sh': 'shell',
            '.bash': 'shell',
            '.zsh': 'shell',
            '.fish': 'shell',
            '.ps1': 'powershell',
            '.r': 'r',
            '.R': 'r',
            '.scala': 'scala',
            '.clj': 'clojure',
            '.ex': 'elixir',
            '.exs': 'elixir',
            '.erl': 'erlang',
            '.hrl': 'erlang',
            '.lua': 'lua',
            '.vim': 'vim',
            '.pl': 'perl',
            '.pm': 'perl'
        }
        
        file_type["language"] = lang_map.get(ext)
        
        # Test detection
        test_patterns = ['test', 'spec', '_test', '.test', '.spec', 'tests/', 'test/']
        file_type["is_test"] = any(pattern in str(path) for pattern in test_patterns)
        
        # Doc detection
        doc_extensions = ['.md', '.rst', '.txt', '.adoc', '.org']
        doc_patterns = ['readme', 'changelog', 'contributing', 'license', 'docs/', 'documentation/']
        file_type["is_doc"] = ext in doc_extensions or any(pattern in str(path).lower() for pattern in doc_patterns)
        
        # Config detection
        config_extensions = ['.yml', '.yaml', '.json', '.toml', '.ini', '.cfg', '.conf']
        config_patterns = ['config', 'settings', '.env', 'makefile', 'dockerfile', '.gitignore']
        file_type["is_config"] = ext in config_extensions or any(pattern in name for pattern in config_patterns)
        
        # Generated file detection
        generated_patterns = ['generated', '.g.dart', '.pb.go', '.gen.', 'build/', 'dist/', 'target/']
        file_type["is_generated"] = any(pattern in str(path) for pattern in generated_patterns)
        
        return file_type

# ============================================================================
# MULTI-STAGE ANALYSIS PIPELINE (Phase 2)
# ============================================================================

class MultiStageAnalyzer:
    """Multi-stage analysis for comprehensive understanding"""
    
    def __init__(self, model: str = None):
        self.model = model or os.environ.get('GEMINI_MODEL', Config.FLASH_MODEL)
        self.sanitizer = FastTextSanitizer()
        self.context_gatherer = EnhancedContextGatherer()
    
    def stage1_classify_changes(self, files: List[str], context: Dict) -> Dict[str, any]:
        """Stage 1: Classify files by importance and change type"""
        
        # Build a summary of files and their contexts
        file_summaries = []
        for file in files[:50]:  # Limit to prevent huge prompts
            if file not in context["file_contexts"]:
                continue
            
            fc = context["file_contexts"][file]
            summary = f"File: {file}"
            
            if fc["file_type"]["language"]:
                summary += f" ({fc['file_type']['language']})"
            
            if fc["symbols"]:
                symbols = []
                for key, values in fc["symbols"].items():
                    if values and key != "modified_symbols":
                        symbols.append(f"{key}: {', '.join(values[:3])}")
                if symbols:
                    summary += f"\nSymbols: {'; '.join(symbols)}"
            
            if fc["dependencies"]["imports_this_file"]:
                summary += f"\nImported by: {len(fc['dependencies']['imports_this_file'])} files"
            
            if fc["history"].get("last_commit_message"):
                summary += f"\nLast change: {fc['history']['last_commit_message'][:50]}..."
            
            file_summaries.append(summary)
        
        prompt = f"""Analyze these file changes and classify them by importance and type.

Context:
- Branch: {context.get('branch_info', {}).get('current_branch', 'unknown')}
- Total files: {context['overall_stats']['total_files']}
- Languages: {', '.join(context['overall_stats']['languages'])}
- Has tests: {context['overall_stats']['has_tests']}
- Has docs: {context['overall_stats']['has_docs']}

Files and their contexts:
{chr(10).join(file_summaries)}

For each file, classify:
1. Importance: critical/high/medium/low
2. Change type: feature/fix/refactor/perf/test/docs/style/build
3. Risk level: high/medium/low
4. Needs detailed analysis: yes/no

Focus on:
- API changes (critical importance)
- Core logic changes (high importance)
- Breaking changes (high risk)
- Cross-package dependencies

Output as JSON with structure (include only sections that are relevant):
{{
  "classifications": {{  // Optional: Include if you can classify files
    "filename": {{
      "importance": "critical|high|medium|low",  // Optional
      "change_type": "feature|fix|refactor|perf|test|docs|style|build",  // Optional
      "risk": "high|medium|low",  // Optional
      "needs_analysis": true|false,  // Optional
      "reason": "brief explanation"  // Optional but recommended if including file
    }}
  }},
  "overall_assessment": {{  // Optional: Include if you can assess overall changes
    "primary_change_type": "main type",  // Optional
    "has_breaking_changes": true|false,  // Optional
    "cross_package_impact": true|false,  // Optional
    "suggested_commit_type": "feat|fix|refactor|perf|test|docs|style|build|chore"  // Optional
  }}
}}

IMPORTANT: Output valid JSON only, no markdown formatting. Include only the sections and fields that you can confidently determine."""

        try:
            result = self._call_gemini(prompt)
            # Parse JSON response
            return json.loads(result)
        except (json.JSONDecodeError, Exception) as e:
            # Fallback classification - return minimal structure
            return {
                "classifications": {},
                "overall_assessment": {
                    "suggested_commit_type": "refactor"
                }
            }
    
    def stage2_deep_analysis(self, critical_files: List[Tuple[str, str, Dict]], 
                           context: Dict) -> Dict[str, str]:
        """Stage 2: Deep analysis of critical files"""
        analyses = {}
        
        # Analyze critical files with more context
        for file, diff, classification in critical_files[:10]:  # Limit to top 10
            if not diff:
                continue
            
            file_context = context["file_contexts"].get(file, {})
            
            prompt = f"""Perform deep analysis of this critical file change.

File: {file}
Classification: {classification.get('reason', 'Critical change')}
Language: {file_context.get('file_type', {}).get('language', 'unknown')}

Change Context:
- Last modified: {file_context.get('history', {}).get('last_modified', 'unknown')}
- Previous commit: {file_context.get('history', {}).get('last_commit_message', 'N/A')}
- Imported by: {len(file_context.get('dependencies', {}).get('imports_this_file', []))} files
- Test files: {', '.join(file_context.get('dependencies', {}).get('test_files', [])) or 'None found'}

Symbols changed:
{json.dumps(file_context.get('symbols', {}), indent=2)}

Diff (limited):
{diff[:2000]}

Analyze:
1. What is the purpose of these changes?
2. What are the technical implications?
3. Are there any breaking changes to APIs or interfaces?
4. What other files/packages might be affected?
5. Are there any performance implications?
6. What tests should be updated or added?

Be specific and technical. Focus on impact and dependencies.

IMPORTANT: Output as plain text without markdown formatting."""

            try:
                analysis = self._call_gemini(prompt)
                analyses[file] = analysis
            except Exception as e:
                analyses[file] = f"Analysis failed: {str(e)}"
        
        return analyses
    
    def stage3_dependency_impact(self, analyses: Dict[str, str], 
                               classifications: Dict,
                               context: Dict) -> Dict[str, any]:
        """Stage 3: Analyze dependencies and ripple effects"""
        
        # Build dependency graph summary
        dependency_info = []
        
        for file, analysis in analyses.items():
            file_ctx = context["file_contexts"].get(file, {})
            deps = file_ctx.get("dependencies", {})
            
            if deps.get("imports_this_file"):
                dependency_info.append(f"{file} is imported by: {', '.join(deps['imports_this_file'][:5])}")
            
            if deps.get("test_files"):
                dependency_info.append(f"{file} has tests: {', '.join(deps['test_files'])}")
        
        prompt = f"""Analyze the dependency impacts and ripple effects of these changes.

Overall Change Assessment:
{json.dumps(classifications.get('overall_assessment', {}), indent=2)}

File Analyses:
{chr(10).join(f"=== {file} ===\n{analysis}\n" for file, analysis in list(analyses.items())[:5])}

Dependency Information:
{chr(10).join(dependency_info)}

Analyze:
1. Which files need to be updated due to these changes?
2. Are there any circular dependencies or coupling issues?
3. What is the blast radius of these changes?
4. Which packages are affected and how?
5. What integration points need attention?
6. Are there any missing test updates?

Output as JSON (include only sections that are relevant):
{{
  "affected_files": ["list of files that need updates"],  // Optional: Include if files need updates
  "affected_packages": {{  // Optional: Include if packages are affected
    "package_name": "impact description"
  }},
  "integration_points": ["list of integration points"],  // Optional: Include if there are integration concerns
  "missing_tests": ["suggested test files/cases"],  // Optional: Include if tests are missing
  "risk_assessment": {{  // Optional: Include if you can assess risk
    "blast_radius": "small|medium|large",  // Optional
    "breaking_changes": ["list of breaking changes"],  // Optional: Include if there are breaking changes
    "migration_needed": true|false  // Optional: Include if migration is needed
  }}
}}

IMPORTANT: Output valid JSON only. Include only the sections and fields that you can confidently determine."""

        try:
            result = self._call_gemini(prompt)
            return json.loads(result)
        except (json.JSONDecodeError, Exception) as e:
            # Return empty structure - all fields are optional
            return {}
    
    def stage4_generate_metadata(self, all_analyses: Dict) -> Dict[str, any]:
        """Stage 4: Generate rich metadata for the commit"""
        
        prompt = f"""Generate comprehensive metadata for this commit based on all analyses.

Classifications:
{json.dumps(all_analyses.get('classifications', {}), indent=2)}

Dependency Impact:
{json.dumps(all_analyses.get('dependency_impact', {}), indent=2)}

Deep Analyses Summary:
{chr(10).join(f"{file}: {analysis[:200]}..." for file, analysis in list(all_analyses.get('deep_analyses', {}).items())[:3])}

Generate metadata (include only sections that are relevant):
{{
  "semantic_version_bump": "major|minor|patch",  // Optional: Include if you can determine version impact
  "changelog_entry": {{  // Optional: Include if changes warrant a changelog entry
    "type": "Added|Changed|Deprecated|Removed|Fixed|Security",  // Optional
    "description": "user-facing description",  // Optional but recommended if including changelog_entry
    "breaking_changes": ["list of breaking changes"],  // Optional: Include only if there are breaking changes
    "migration_guide": "migration instructions if needed"  // Optional: Include only if migration is needed
  }},
  "pr_labels": ["suggested PR labels"],  // Optional: Include if you can suggest relevant labels
  "review_checklist": ["items to check during review"],  // Optional: Include if there are specific review concerns
  "documentation_updates": ["docs that need updating"],  // Optional: Include if docs need updates
  "follow_up_tasks": ["suggested follow-up work"]  // Optional: Include if there are follow-up tasks
}}

IMPORTANT: Output valid JSON only. Include only the sections and fields that you can confidently determine."""

        try:
            result = self._call_gemini(prompt)
            return json.loads(result)
        except (json.JSONDecodeError, Exception) as e:
            # Return empty structure - all fields are optional
            return {}
    
    def generate_enhanced_commit_message(self, all_analyses: Dict, 
                                       quick_mode: bool = False) -> str:
        """Generate the final enhanced commit message"""
        
        if quick_mode:
            # Simplified prompt for quick mode
            prompt = f"""Generate a conventional commit message based on these changes.

File Classifications:
{json.dumps(all_analyses.get('classifications', {}).get('overall_assessment', {}), indent=2)}

Context:
- Primary change type: {all_analyses.get('classifications', {}).get('overall_assessment', {}).get('primary_change_type', 'refactor')}
- Has breaking changes: {all_analyses.get('classifications', {}).get('overall_assessment', {}).get('has_breaking_changes', False)}
- Cross-package impact: {all_analyses.get('classifications', {}).get('overall_assessment', {}).get('cross_package_impact', False)}

Generate a commit message with:
1. Type: {all_analyses.get('classifications', {}).get('overall_assessment', {}).get('suggested_commit_type', 'refactor')}
2. Concise subject (50 chars max)
3. Detailed body explaining the changes

Format:
<type>(<scope>): <subject>

<body>

IMPORTANT: Output as plain text without markdown formatting."""
        else:
            # Comprehensive prompt for max mode
            prompt = f"""Generate a comprehensive commit message using all analysis data.

Classifications:
{json.dumps(all_analyses.get('classifications', {}), indent=2)}

Dependency Impact:
{json.dumps(all_analyses.get('dependency_impact', {}), indent=2)}

Metadata:
{json.dumps(all_analyses.get('metadata', {}), indent=2)}

Deep Analyses (summary):
{chr(10).join(f"- {file}: {analysis[:100]}..." for file, analysis in list(all_analyses.get('deep_analyses', {}).items())[:5])}

Create a detailed commit message that:
1. Uses type: {all_analyses.get('classifications', {}).get('overall_assessment', {}).get('suggested_commit_type', 'feat')}
2. Has a clear, descriptive subject (50 chars max)
3. Includes comprehensive body with:
   - Overview of changes
   - Technical details per package/component
   - Breaking changes (if any)
   - Migration guide (if needed)
   - Performance impacts
   - Test coverage updates

Format:
<type>(<scope>): <subject>

<comprehensive body>

<footer with BREAKING CHANGE if applicable>

IMPORTANT: Output as plain text without markdown formatting."""

        return self._call_gemini(prompt)
    
    def _call_gemini(self, prompt: str) -> str:
        """Make a gemini call"""
        try:
            process = subprocess.Popen(
                ['gemini-cli', 'prompt', '-', '--model', self.model],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, _ = process.communicate(input=prompt, timeout=30)
            
            if process.returncode != 0:
                raise Exception("Gemini call failed")
            
            return self.sanitizer.clean_ai_response(stdout)
            
        except subprocess.TimeoutExpired:
            process.kill()
            raise Exception("AI analysis timeout")
        except Exception as e:
            raise Exception(f"AI error: {str(e)}")

# ============================================================================
# FAST FILE OPERATIONS
# ============================================================================

class FastFileAnalyzer:
    """Fast file categorization and diff generation"""
    
    # Package patterns compiled once
    PACKAGE_PATTERNS = [
        (re.compile(r'^dart/rust/'), 'rust'),
        (re.compile(r'^flutter/'), 'flutter'),
        (re.compile(r'^dart/'), 'dart'),
        (re.compile(r'^tooling/'), 'tooling'),
        (re.compile(r'^documentation/'), 'documentation'),
        (re.compile(r'^\.github/'), 'github'),
        (re.compile(r'^(README|LICENSE|CHANGELOG|CONTRIBUTING|AUTHORS|SECURITY|CODE_OF_CONDUCT)'), 'meta'),
        (re.compile(r'^(Makefile|\.gitignore|\.gitattributes|\.editorconfig)'), 'config'),
        (re.compile(r'^\w+\.(toml|yaml|yml|json)$'), 'root-config'),
    ]
    
    @classmethod
    def categorize_files(cls, files: List[str], any_structure: bool = False) -> Dict[str, List[str]]:
        """Quickly categorize files by package"""
        packages = defaultdict(list)
        
        if any_structure:
            # For any repository structure, categorize by directory
            for file in files:
                if not file:
                    continue
                
                # Extract filename from git status
                clean_file = re.sub(r'^[MADRCU?!]\s+', '', file.strip())
                
                # Categorize by directory structure
                if '/' not in clean_file:
                    # Root-level file
                    package = 'root'
                else:
                    # Use first directory as package
                    parts = clean_file.split('/')
                    first_dir = parts[0]
                    
                    # Special handling for common directories
                    if first_dir.startswith('.'):
                        package = 'config'
                    elif first_dir in ['test', 'tests', 'spec', 'specs']:
                        package = 'tests'
                    elif first_dir in ['doc', 'docs', 'documentation']:
                        package = 'docs'
                    elif first_dir in ['src', 'lib', 'pkg']:
                        # For src/lib/pkg, use the second level if available
                        if len(parts) > 1 and parts[1]:
                            package = parts[1]
                        else:
                            package = first_dir
                    else:
                        package = first_dir
                
                packages[package].append(clean_file)
        else:
            # Original behavior for dart/flutter/rust structure
            for file in files:
                if not file:
                    continue
                
                # Extract filename from git status
                clean_file = re.sub(r'^[MADRCU?!]\s+', '', file.strip())
                
                # Find package using compiled patterns
                package = None
                for pattern, pkg_name in cls.PACKAGE_PATTERNS:
                    if pattern.match(clean_file):
                        package = pkg_name
                        break
                
                # If no pattern matched, categorize based on location
                if package is None:
                    if '/' not in clean_file:
                        # Root-level file
                        package = 'root'
                    else:
                        # Other subdirectory
                        package = 'other'
                
                packages[package].append(clean_file)
        
        return dict(packages)
            
    @staticmethod
    def get_limited_diff(file: str, max_lines: int) -> str:
        """Get diff with size limit for performance"""
        diff_parts = []
        
        # Get staged diff
        try:
            result = subprocess.run(
                ['git', 'diff', '--cached', '--', file],
                capture_output=True,
                text=True,
                timeout=2  # Quick timeout
            )
            if result.returncode == 0 and result.stdout:
                staged_diff = result.stdout
                line_count = staged_diff.count('\n')
                
                if line_count > max_lines:
                    diff_parts.append(f"STAGED: {file}")
                    diff_parts.append(f"[Diff truncated: {line_count} lines]")
                    diff_parts.extend(staged_diff.split('\n')[:max_lines])
                    diff_parts.append("...")
                else:
                    diff_parts.append(f"STAGED: {file}")
                    diff_parts.append(staged_diff)
        except subprocess.TimeoutExpired:
            diff_parts.append(f"STAGED: {file} [Timeout]")
        
        # Get unstaged diff
        try:
            result = subprocess.run(
                ['git', 'diff', '--', file],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0 and result.stdout:
                unstaged_diff = result.stdout
                line_count = unstaged_diff.count('\n')
                
                if line_count > max_lines:
                    diff_parts.append(f"UNSTAGED: {file}")
                    diff_parts.append(f"[Diff truncated: {line_count} lines]")
                    diff_parts.extend(unstaged_diff.split('\n')[:max_lines])
                    diff_parts.append("...")
                else:
                    diff_parts.append(f"UNSTAGED: {file}")
                    diff_parts.append(unstaged_diff)
        except subprocess.TimeoutExpired:
            diff_parts.append(f"UNSTAGED: {file} [Timeout]")
        
        return '\n'.join(diff_parts) if diff_parts else ""

# ============================================================================
# FAST AI ANALYZER
# ============================================================================

class FastAIAnalyzer:
    """Optimized AI analysis for speed"""
    
    def __init__(self):
        self.model = os.environ.get('GEMINI_MODEL', Config.FLASH_MODEL)
        self.sanitizer = FastTextSanitizer()
        self.context_gatherer = EnhancedContextGatherer()
        self.multi_stage = MultiStageAnalyzer(self.model)
    
    def analyze_quick_mode(self, all_files: List[str], any_structure: bool = False) -> str:
        """Single fast AI call for quick mode with enhanced context"""
        print_color(Colors.BLUE, "\nGathering enhanced context...", file=sys.stderr)
        
        # Get basic diffs for context gathering
        file_diffs = {}
        for file in all_files[:20]:  # Limit for performance
            clean_file = re.sub(r'^[MADRCU?!]\s+', '', file.strip())
            diff = FastFileAnalyzer.get_limited_diff(clean_file, 50)
            if diff:
                file_diffs[clean_file] = diff
        
        # Gather enhanced context
        clean_files = [re.sub(r'^[MADRCU?!]\s+', '', f.strip()) for f in all_files]
        context = self.context_gatherer.gather_enhanced_context(clean_files[:20], file_diffs)
        
        print_color(Colors.BLUE, "Analyzing all changes in quick mode...", file=sys.stderr)
        
        # Categorize files
        packages = FastFileAnalyzer.categorize_files(all_files, any_structure)
        
        # Build enhanced summary
        changes_summary = []
        package_count = 0
        
        for package, files in packages.items():
            if not files:
                continue
            
            package_count += 1
            
            # Format package name for display
            if package == 'root':
                display_name = "Root level"
            elif package == 'meta':
                display_name = "Repository metadata"
            elif package == 'config':
                display_name = "Repository configuration"
            elif package == 'root-config':
                display_name = "Root configuration files"
            elif package == 'github':
                display_name = "GitHub/CI configuration"
            elif package == 'documentation':
                display_name = "Documentation"
            elif package == 'other':
                display_name = "Other files"
            else:
                display_name = f"{package.capitalize()} package"
            
            changes_summary.append(f"{display_name} ({len(files)} files):")
            
            # Show limited files with context
            for i, file in enumerate(files[:Config.MAX_FILES_PER_PACKAGE]):
                file_info = [f"  - {file}"]
                
                # Add context if available
                if file in context["file_contexts"]:
                    fc = context["file_contexts"][file]
                    if fc["file_type"]["language"]:
                        file_info.append(f" ({fc['file_type']['language']})")
                    if fc["symbols"]:
                        symbols = []
                        for key, values in fc["symbols"].items():
                            if values and key != "modified_symbols":
                                symbols.extend(values[:2])
                        if symbols:
                            file_info.append(f" [symbols: {', '.join(symbols)}]")
                
                changes_summary.append(''.join(file_info))
            
            if len(files) > Config.MAX_FILES_PER_PACKAGE:
                changes_summary.append(f"  ... and {len(files) - Config.MAX_FILES_PER_PACKAGE} more files")
            changes_summary.append("")
        
        # Add context information
        context_info = []
        if context["issues"]["branch_issues"]:
            context_info.append(f"Related issues: #{', #'.join(context['issues']['branch_issues'])}")
        if context["branch_info"].get("current_branch"):
            context_info.append(f"Branch: {context['branch_info']['current_branch']}")
        if context["overall_stats"]["languages"]:
            context_info.append(f"Languages: {', '.join(context['overall_stats']['languages'])}")
        
        # Get sample diffs with symbol context
        sample_diffs = []
        diff_count = 0
        
        for package, files in packages.items():
            for file in files[:Config.SAMPLE_DIFFS_COUNT]:
                if diff_count >= Config.SAMPLE_DIFFS_COUNT:
                    break
                
                diff = FastFileAnalyzer.get_limited_diff(file, 50)
                if diff:
                    sample_diffs.append(f"=== {package}: {file} ===")
                    
                    # Add file context
                    if file in context["file_contexts"]:
                        fc = context["file_contexts"][file]
                        if fc["history"].get("last_commit_message"):
                            sample_diffs.append(f"Last change: {fc['history']['last_commit_message'][:60]}...")
                        if fc["dependencies"]["imports_this_file"]:
                            sample_diffs.append(f"Imported by: {len(fc['dependencies']['imports_this_file'])} files")
                    
                    sample_diffs.append(diff)
                    sample_diffs.append("")
                    diff_count += 1
        
        # Create optimized prompt with context
        repo_context = "in a vector search library" if not any_structure else ""
        prompt = f"""Generate a conventional commit message for these changes{' ' + repo_context if repo_context else ''}.

CONTEXT:
{chr(10).join(context_info)}

CHANGES SUMMARY ({package_count} packages/areas affected):
{chr(10).join(changes_summary)}

SAMPLE DIFFS (showing {diff_count} of many files):
{chr(10).join(sample_diffs)}

Create a commit message that:
1. Uses the appropriate type (feat/fix/docs/style/refactor/perf/test/build/ci/chore)
2. Has a concise subject line (50 chars max)
3. Includes a body that summarizes the main changes
4. Groups related changes together
5. Mentions ALL affected areas including:
   - Core packages (dart, flutter, rust)
   - Root-level configuration files
   - Documentation changes
   - Tooling updates
   - Any other affected areas
6. References any related issues if found

Format:
<type>(<scope>): <subject>

<body with key changes>

Be concise but informative. Focus on the what and why, not implementation details.
Make sure to mention changes at the repository root level if any exist.

IMPORTANT: Output the commit message as plain text. Do NOT wrap it in markdown code blocks."""

        return self._call_gemini(prompt)
    
    def analyze_package(self, package: str, files: List[str], any_structure: bool = False) -> str:
        """Analyze a single package with enhanced context"""
        if not files:
            return "NO_CHANGES"
        
        # Gather enhanced context for package files
        file_diffs = {}
        clean_files = []
        
        for file in files[:10]:  # Limit for performance
            diff = FastFileAnalyzer.get_limited_diff(file, Config.MAX_DIFF_PER_FILE)
            if diff:
                file_diffs[file] = diff
                clean_files.append(file)
        
        if not file_diffs:
            return "NO_CHANGES"
        
        # Get enhanced context
        context = self.context_gatherer.gather_enhanced_context(clean_files, file_diffs)
        
        # Build file summaries with context
        file_summaries = []
        for file in clean_files:
            if file in context["file_contexts"]:
                fc = context["file_contexts"][file]
                summary = [f"- {file}"]
                
                if fc["symbols"]:
                    symbols = []
                    for key, values in fc["symbols"].items():
                        if values:
                            symbols.append(f"{key}: {', '.join(values[:3])}")
                    if symbols:
                        summary.append(f"\n  Symbols: {'; '.join(symbols)}")
                
                if fc["dependencies"]["imports_this_file"]:
                    summary.append(f"\n  Imported by: {len(fc['dependencies']['imports_this_file'])} files")
                
                if fc["history"].get("last_commit_message"):
                    summary.append(f"\n  Last change: {fc['history']['last_commit_message'][:50]}...")
                
                file_summaries.append(''.join(summary))
        
        # Get limited diffs
        diffs = []
        total_lines = 0
        
        for file in files:
            if total_lines > Config.MAX_DIFF_LINES:
                break
            
            diff = FastFileAnalyzer.get_limited_diff(file, Config.MAX_DIFF_PER_FILE)
            if diff:
                diffs.append(diff)
                total_lines += diff.count('\n')
        
        # Adjust description based on package type
        if package == 'root':
            package_desc = "root level of the repository"
        elif package == 'meta':
            package_desc = "repository metadata files"
        elif package == 'config':
            package_desc = "repository configuration"
        elif package == 'root-config':
            package_desc = "root-level configuration files"
        elif package == 'github':
            package_desc = "GitHub configuration"
        elif package == 'documentation':
            package_desc = "documentation"
        else:
            package_desc = f"{package} package"
        
        repo_context = " of a vector search library" if not any_structure else ""
        prompt = f"""Analyze changes in the {package_desc}{repo_context}.

Files changed: {len(files)}
Context:
- Languages: {', '.join(context['overall_stats']['languages'])}
- Has tests: {context['overall_stats']['has_tests']}
- Related issues: {', '.join(context['issues']['branch_issues']) if context['issues']['branch_issues'] else 'None'}

File summaries:
{chr(10).join(file_summaries)}

Diffs:
{chr(10).join(diffs)}

Provide a brief technical summary of:
1. Main changes and their purpose
2. Impact on the {'repository' if package in ['root', 'meta', 'config', 'root-config'] else 'package'}
3. Any breaking changes or important notes
4. Dependencies affected

Be concise and technical. Focus on what matters for a commit message.

IMPORTANT: Output as plain text without markdown code blocks."""

        return self._call_gemini(prompt)
    
    def analyze_enhanced_max_mode(self, all_files: List[str]) -> Tuple[str, Dict]:
        """Run enhanced max mode with multi-stage analysis"""
        print_color(Colors.BLUE, "\nRunning enhanced multi-stage analysis...", file=sys.stderr)
        
        # Stage 0: Gather enhanced context
        print_color(Colors.BLUE, "Stage 0: Gathering enhanced context...", file=sys.stderr)
        
        file_diffs = {}
        clean_files = []
        
        for file in all_files:
            clean_file = re.sub(r'^[MADRCU?!]\s+', '', file.strip())
            clean_files.append(clean_file)
            
            # Get limited diff for context
            diff = FastFileAnalyzer.get_limited_diff(clean_file, 200)
            if diff:
                file_diffs[clean_file] = diff
        
        context = self.context_gatherer.gather_enhanced_context(clean_files[:50], file_diffs)
        
        # Stage 1: Classify changes
        print_color(Colors.BLUE, "Stage 1: Classifying changes by importance...", file=sys.stderr)
        classifications = self.multi_stage.stage1_classify_changes(clean_files, context)
        
        # Stage 2: Deep analysis of critical files
        print_color(Colors.BLUE, "Stage 2: Deep analysis of critical files...", file=sys.stderr)
        
        critical_files = []
        for file, classification in classifications.get("classifications", {}).items():
            if classification.get("importance") in ["critical", "high"] and classification.get("needs_analysis"):
                diff = file_diffs.get(file, "")
                if not diff:
                    diff = FastFileAnalyzer.get_limited_diff(file, 500)
                critical_files.append((file, diff, classification))
        
        deep_analyses = {}
        if critical_files:
            deep_analyses = self.multi_stage.stage2_deep_analysis(critical_files, context)
        
        # Stage 3: Dependency impact analysis
        print_color(Colors.BLUE, "Stage 3: Analyzing dependency impacts...", file=sys.stderr)
        dependency_impact = self.multi_stage.stage3_dependency_impact(
            deep_analyses, classifications, context
        )
        
        # Stage 4: Generate metadata
        print_color(Colors.BLUE, "Stage 4: Generating commit metadata...", file=sys.stderr)
        all_analyses = {
            "classifications": classifications,
            "deep_analyses": deep_analyses,
            "dependency_impact": dependency_impact,
            "context": context
        }
        
        metadata = self.multi_stage.stage4_generate_metadata(all_analyses)
        all_analyses["metadata"] = metadata
        
        # Generate final message
        print_color(Colors.BLUE, "Generating enhanced commit message...", file=sys.stderr)
        
        # Show metadata to user
        if metadata.get("semantic_version_bump"):
            print_color(Colors.YELLOW, f"\nSuggested version bump: {metadata['semantic_version_bump']}", file=sys.stderr)
        if metadata.get("pr_labels"):
            print_color(Colors.YELLOW, f"Suggested PR labels: {', '.join(metadata['pr_labels'])}", file=sys.stderr)
        if dependency_impact.get("risk_assessment", {}).get("breaking_changes"):
            print_color(Colors.RED, f"Breaking changes detected!", file=sys.stderr)
        
        commit_message = self.multi_stage.generate_enhanced_commit_message(all_analyses, quick_mode=False)
        
        # Return both message and metadata
        return (commit_message, metadata)
    
    def generate_final_message(self, analyses: str) -> str:
        """Generate final commit message from analyses"""
        prompt = f"""Create a conventional commit message based on these package analyses:

{analyses}

Generate a commit message that:
1. Uses appropriate type (feat/fix/docs/style/refactor/perf/test/build/ci/chore)
2. Has a clear subject line (50 chars max)
3. Includes a comprehensive body
4. Mentions ALL affected areas:
   - Core packages (dart, flutter, rust) if changed
   - Root-level files and configurations if changed
   - Documentation updates if any
   - Tooling changes if any
   - GitHub/CI configuration if changed

Format:
<type>(<scope>): <subject>

<body>

Focus on the overall change impact across the entire repository.
Ensure root-level changes are not overlooked.

IMPORTANT: Output as plain text without markdown code blocks."""

        return self._call_gemini(prompt)
    
    def _call_gemini(self, prompt: str) -> str:
        """Make a fast gemini call with timeout"""
        try:
            process = subprocess.Popen(
                ['gemini-cli', 'prompt', '-', '--model', self.model],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, _ = process.communicate(input=prompt, timeout=30)
            
            if process.returncode != 0:
                raise Exception("Gemini call failed")
            
            return self.sanitizer.clean_ai_response(stdout)
            
        except subprocess.TimeoutExpired:
            process.kill()
            raise Exception("AI analysis timeout")
        except Exception as e:
            raise Exception(f"AI error: {str(e)}")

# ============================================================================
# GITHUB URL HELPER
# ============================================================================

def get_github_commit_url(commit_hash: str) -> Optional[str]:
    """Get GitHub URL for a commit"""
    try:
        # Get remote URL
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return None
        
        remote_url = result.stdout.strip()
        
        # Convert SSH to HTTPS if needed
        if remote_url.startswith('git@github.com:'):
            remote_url = remote_url.replace('git@github.com:', 'https://github.com/')
        
        # Remove .git suffix
        if remote_url.endswith('.git'):
            remote_url = remote_url[:-4]
        
        # Ensure it's a GitHub URL
        if 'github.com' not in remote_url:
            return None
        
        return f"{remote_url}/commit/{commit_hash}"
        
    except Exception:
        return None

# ============================================================================
# MAIN FAST COMMIT CLASS
# ============================================================================

class FastSmartCommit:
    """Fast smart commit implementation"""
    
    def __init__(self, args):
        self.args = args
        self.analyzer = FastAIAnalyzer()
        self.any_structure = args.any
        
        # Configure based on arguments
        if args.max:
            Config.set_max_mode()
        if args.skip_cross:
            Config.SKIP_CROSS_ANALYSIS = True
        if args.enhanced:
            # Enhanced mode uses Pro model for better analysis
            os.environ['GEMINI_MODEL'] = Config.PRO_MODEL
    
    def check_prerequisites(self):
        """Quick prerequisite check"""
        if not check_gemini_cli():
            sys.exit(1)
        if not check_api_key():
            sys.exit(1)
        print_color(Colors.GREEN, "✓ All prerequisites met")
    
    def get_all_changes(self) -> List[str]:
        """Get all changed files quickly"""
        all_files = []
        
        # Use single git status command for efficiency
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0 and result.stdout:
            all_files = result.stdout.strip().split('\n')
        
        # Clean output
        return [FastTextSanitizer.sanitize_text(f) for f in all_files if f]
    
    def run_quick_mode(self, all_files: List[str]) -> str:
        """Run in quick mode with single AI call"""
        return self.analyzer.analyze_quick_mode(all_files, self.any_structure)
    
    def run_max_mode(self, all_files: List[str]) -> str:
        """Run in max mode with parallel analysis"""
        if self.args.enhanced:
            # Use enhanced multi-stage analysis
            return self.analyzer.analyze_enhanced_max_mode(all_files)
        
        print_color(Colors.BLUE, "\nCategorizing and analyzing changes...")
        
        # Categorize files
        packages = FastFileAnalyzer.categorize_files(all_files, self.any_structure)
        
        # Analyze packages in parallel using processes for true parallelism
        analyses = {}
        
        with ProcessPoolExecutor(max_workers=len(packages)) as executor:
            # Submit all tasks
            futures = {}
            for package, files in packages.items():
                if files:
                    # Create a new analyzer instance for each process
                    future = executor.submit(self._analyze_package_worker, package, files, self.any_structure)
                    futures[future] = package
            
            # Collect results
            for future in as_completed(futures):
                package = futures[future]
                try:
                    result = future.result()
                    if result != "NO_CHANGES":
                        analyses[package] = result
                except Exception as e:
                    print_color(Colors.YELLOW, f"Failed to analyze {package}: {str(e)}", file=sys.stderr)
        
        if not analyses:
            return ""
        
        # Compile analyses
        all_analyses = []
        for package, analysis in analyses.items():
            all_analyses.append(f"=== {package} package ===")
            all_analyses.append(analysis)
            all_analyses.append("")
        
        # Generate final message
        print_color(Colors.BLUE, "\nGenerating commit message...")
        return self.analyzer.generate_final_message('\n'.join(all_analyses))
    
    @staticmethod
    def _analyze_package_worker(package: str, files: List[str], any_structure: bool = False) -> str:
        """Worker function for parallel analysis"""
        # Create a new analyzer instance in the subprocess
        analyzer = FastAIAnalyzer()
        return analyzer.analyze_package(package, files, any_structure)
    
    def display_enhanced_metadata(self, metadata: Dict):
        """Display enhanced metadata to user"""
        if not metadata:
            return
        
        print_color(Colors.BLUE, "\n📊 Commit Metadata:", file=sys.stderr)
        
        if metadata.get("semantic_version_bump"):
            print_color(Colors.YELLOW, f"  Version bump: {metadata['semantic_version_bump']}", file=sys.stderr)
        
        if metadata.get("pr_labels"):
            print_color(Colors.BLUE, f"  PR labels: {', '.join(metadata['pr_labels'])}", file=sys.stderr)
        
        if metadata.get("review_checklist"):
            print_color(Colors.BLUE, "  Review checklist:", file=sys.stderr)
            for item in metadata["review_checklist"][:3]:
                print_color(Colors.GRAY, f"    ✓ {item}", file=sys.stderr)
            if len(metadata["review_checklist"]) > 3:
                print_color(Colors.GRAY, f"    ... and {len(metadata['review_checklist']) - 3} more", file=sys.stderr)
        
        if metadata.get("documentation_updates"):
            print_color(Colors.YELLOW, f"  Docs to update: {', '.join(metadata['documentation_updates'])}", file=sys.stderr)
        
        if metadata.get("follow_up_tasks"):
            print_color(Colors.YELLOW, "  Follow-up tasks:", file=sys.stderr)
            for task in metadata["follow_up_tasks"][:2]:
                print_color(Colors.GRAY, f"    → {task}", file=sys.stderr)
        
        changelog = metadata.get("changelog_entry", {})
        if changelog.get("breaking_changes"):
            print_color(Colors.RED, "  ⚠️  Breaking changes:", file=sys.stderr)
            for change in changelog["breaking_changes"]:
                print_color(Colors.RED, f"    • {change}", file=sys.stderr)
        
        print()
    
    def save_commit_metadata(self, commit_hash: str, metadata: Dict):
        """Save commit metadata for future reference"""
        try:
            # Create .git/commit-metadata directory if it doesn't exist
            metadata_dir = Path(".git/commit-metadata")
            metadata_dir.mkdir(exist_ok=True)
            
            # Save metadata as JSON
            metadata_file = metadata_dir / f"{commit_hash}.json"
            with open(metadata_file, 'w') as f:
                json.dump({
                    "commit": commit_hash,
                    "timestamp": datetime.now().isoformat(),
                    "metadata": metadata
                }, f, indent=2)
            
            print_color(Colors.GRAY, f"  Metadata saved to {metadata_file}", file=sys.stderr)
        except Exception:
            # Silently fail - metadata is optional
            pass
    
    def commit_changes(self, commit_message: str, metadata: Dict = None):
        """Commit changes, optionally push, and show GitHub URL"""
        # Add and commit
        run_command(['git', 'add', '.'])
        code, _, stderr = run_command(['git', 'commit', '-m', commit_message])
        
        if code != 0:
            print_color(Colors.RED, f"Commit failed: {stderr}")
            return
        
        # Get the commit hash
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            commit_hash = result.stdout.strip()
            print_color(Colors.GREEN, f"✓ Changes committed successfully! ({commit_hash[:8]})")
            
            # Save metadata if available
            if metadata:
                self.save_commit_metadata(commit_hash, metadata)
            
            # Try to get GitHub URL
            github_url = get_github_commit_url(commit_hash)
            if github_url:
                print_color(Colors.BLUE, f"\n🔗 GitHub URL: {github_url}")
                print_color(Colors.GRAY, "   (Will be available after pushing to GitHub)")
        else:
            print_color(Colors.GREEN, "✓ Changes committed successfully!")
        
        # Display metadata after commit (if available)
        if metadata:
            self.display_enhanced_metadata(metadata)
        
        # Ask about pushing
        push_choice = input(f"\n{Colors.YELLOW}Push to origin? (Y/n): {Colors.NC}")
        if not push_choice.lower().startswith('n'):
            # Get current branch
            code, branch, _ = run_command(['git', 'branch', '--show-current'])
            if code == 0 and branch:
                print_color(Colors.BLUE, f"Pushing to origin/{branch}...")
                code, _, stderr = run_command(['git', 'push', 'origin', branch])
                if code == 0:
                    print_color(Colors.GREEN, f"✓ Pushed to origin/{branch}")
                    
                    # Show push URL if available
                    if github_url:
                        # Convert commit URL to branch URL
                        branch_url = github_url.rsplit('/commit/', 1)[0] + f"/tree/{branch}"
                        print_color(Colors.BLUE, f"\n🌿 Branch URL: {branch_url}")
                        print_color(Colors.BLUE, f"📍 Commit URL: {github_url}")
                        print_color(Colors.GRAY, "   (Both URLs are now active on GitHub)")
                else:
                    print_color(Colors.RED, f"Failed to push: {stderr}")
            else:
                print_color(Colors.RED, "Could not determine current branch")
    
    def run(self):
        """Main execution"""
        print_color(Colors.PURPLE, "╔════════════════════════════════════════╗")
        print_color(Colors.PURPLE, "║   Smart Commit Tool v3.1 (Optimized)   ║")
        if Config.QUICK_MODE:
            print_color(Colors.PURPLE, "║     🚀 FLASH MODE (Default) 🚀         ║")
        elif self.args.enhanced:
            print_color(Colors.PURPLE, "║   🧠 ENHANCED ANALYSIS MODE 🧠         ║")
        else:
            print_color(Colors.PURPLE, "║     🔬 MAX ANALYSIS MODE 🔬            ║")
        print_color(Colors.PURPLE, "╚════════════════════════════════════════╝")
        print()
        
        # Start timer
        start_time = time.time()
        
        # Prerequisites
        self.check_prerequisites()
        
        # Get changes
        print_color(Colors.BLUE, "\nChecking for changes...")
        all_files = self.get_all_changes()
        
        if not all_files:
            print_color(Colors.YELLOW, "No changes detected. Nothing to commit.")
            return
        
        # Generate commit message based on mode
        try:
            metadata = None
            
            if Config.QUICK_MODE:
                commit_message = self.run_quick_mode(all_files)
            else:
                if self.args.enhanced:
                    # Enhanced mode returns both message and metadata
                    result = self.analyzer.analyze_enhanced_max_mode(all_files)
                    
                    # Check if we got metadata back
                    if isinstance(result, tuple) and len(result) == 2:
                        commit_message, metadata = result
                    else:
                        commit_message = result
                else:
                    commit_message = self.run_max_mode(all_files)
            
            if not commit_message:
                raise Exception("Empty commit message")
                
        except Exception as e:
            print_color(Colors.RED, f"\nFailed to generate commit message: {str(e)}")
            return
        
        # Show elapsed time
        elapsed = time.time() - start_time
        print_color(Colors.GRAY, f"\nAnalysis completed in {elapsed:.1f}s", file=sys.stderr)
        
        # Show the generated message
        print_color(Colors.GREEN, "\nGenerated commit message:")
        print_color(Colors.PURPLE, "━" * 40)
        print(commit_message)
        print_color(Colors.PURPLE, "━" * 40)
        
        # Quick confirmation
        if Config.QUICK_MODE:
            # Simple Y/n prompt for quick mode
            response = input(f"\n{Colors.YELLOW}Use this message? (Y/n): {Colors.NC}")
            if not response.lower().startswith('n'):
                self.commit_changes(commit_message, metadata)
            else:
                print_color(Colors.YELLOW, "Commit cancelled.")
        else:
            # Full options for max mode
            print("\nOptions:")
            print("  1) Use this message")
            print("  2) Edit message")
            print("  3) Cancel")
            
            choice = input("Choose (1-3): ")
            
            if choice == '1':
                self.commit_changes(commit_message, metadata)
            elif choice == '2':
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                    f.write(commit_message)
                    temp_file = f.name
                
                editor = os.environ.get('EDITOR', 'vim')
                subprocess.call([editor, temp_file])
                
                with open(temp_file, 'r') as f:
                    edited = f.read().strip()
                os.unlink(temp_file)
                
                if edited:
                    self.commit_changes(edited, metadata)
                else:
                    print_color(Colors.YELLOW, "Empty message - commit cancelled.")
            else:
                print_color(Colors.YELLOW, "Cancelled.")

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Fast AI-powered commit message generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
By default, uses quick mode with Flash model for fast commits (2-3s)

Examples:
  %(prog)s                    # Quick commit (default, 2-3s)
  %(prog)s --max              # Comprehensive analysis (15-20s)
  %(prog)s --max --enhanced   # Enhanced multi-stage analysis (20-30s)
  %(prog)s --max --skip-cross # Detailed but skip cross-package analysis
  %(prog)s --any              # Work with any repository structure
        """
    )
    
    parser.add_argument(
        '-m', '--max',
        action='store_true',
        help='Maximum analysis mode - comprehensive multi-package analysis (uses Pro model)'
    )
    
    parser.add_argument(
        '-s', '--skip-cross',
        action='store_true',
        help='Skip cross-package analysis (only works with --max)'
    )
    
    parser.add_argument(
        '-e', '--enhanced',
        action='store_true',
        help='Enhanced mode with multi-stage analysis, context gathering, and metadata generation'
    )
    
    parser.add_argument(
        '-a', '--any',
        action='store_true',
        help='Work with any repository structure (not just dart/flutter/rust)'
    )
    
    return parser.parse_args()

def main():
    """Main entry point"""
    # Parse arguments
    args = parse_arguments()
    
    # Set default Flash model
    os.environ['GEMINI_MODEL'] = Config.FLASH_MODEL
    
    # Run fast commit
    committer = FastSmartCommit(args)
    
    try:
        committer.run()
    except KeyboardInterrupt:
        print()
        print_color(Colors.YELLOW, "Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_color(Colors.RED, f"Error: {str(e)}")
        sys.exit(1)
    finally:
        # Cleanup
        cleanup_temp_files()

if __name__ == "__main__":
    main()