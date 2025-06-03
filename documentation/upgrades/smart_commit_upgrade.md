# Upgrade Plan: smart_commit.py

## Overview
AI-powered commit message generator with comprehensive multi-package analysis and cross-package dependency detection. This is the full-featured version compared to smart_commit_fast.py.

## Current State
- **Dependencies**: Standard library + common_config
- **Key Features**: Multi-package analysis, dependency detection, interactive workflow
- **Performance**: Slower but more thorough than smart_commit_fast

## Recommended Upgrades

### 1. Async Analysis Pipeline
```python
# Parallel package analysis with asyncio
import asyncio
from typing import Dict, List, AsyncIterator
import aiohttp
from dataclasses import dataclass

@dataclass
class PackageAnalysis:
    package_name: str
    files: List[str]
    summary: str
    dependencies: List[str]
    symbols: List[str]
    
class AsyncPackageAnalyzer:
    def __init__(self, ai_client: 'AsyncAIClient'):
        self.ai_client = ai_client
        self.semaphore = asyncio.Semaphore(5)  # Limit concurrent operations
    
    async def analyze_all_packages(
        self,
        packages: Dict[str, List[str]]
    ) -> Dict[str, PackageAnalysis]:
        """Analyze all packages in parallel"""
        tasks = []
        
        for package, files in packages.items():
            if files:  # Only analyze packages with changes
                task = self._analyze_with_semaphore(package, files)
                tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Build result dict, filtering out errors
        analysis_dict = {}
        for result in results:
            if isinstance(result, PackageAnalysis):
                analysis_dict[result.package_name] = result
            else:
                print(f"Error analyzing package: {result}")
        
        return analysis_dict
    
    async def _analyze_with_semaphore(
        self,
        package: str,
        files: List[str]
    ) -> PackageAnalysis:
        """Analyze single package with rate limiting"""
        async with self.semaphore:
            return await self._analyze_package(package, files)
    
    async def _analyze_package(
        self,
        package: str,
        files: List[str]
    ) -> PackageAnalysis:
        """Deep analysis of a single package"""
        # Parallel sub-analyses
        tasks = [
            self._extract_symbols(files),
            self._detect_dependencies(files),
            self._generate_summary(package, files)
        ]
        
        symbols, dependencies, summary = await asyncio.gather(*tasks)
        
        return PackageAnalysis(
            package_name=package,
            files=files,
            summary=summary,
            dependencies=dependencies,
            symbols=symbols
        )
```

### 2. Machine Learning Enhancement
```python
# ML-based commit classification and generation
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
import numpy as np
from typing import List, Tuple
import joblib

class MLCommitClassifier:
    def __init__(self, model_path: Optional[Path] = None):
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            ngram_range=(1, 2),
            stop_words='english'
        )
        self.classifier = RandomForestClassifier(n_estimators=100)
        
        if model_path and model_path.exists():
            self.load_model(model_path)
        else:
            self._train_default_model()
    
    def _train_default_model(self):
        """Train on common commit patterns"""
        # Training data with diff summaries and commit types
        training_data = [
            # (diff_summary, commit_type, scope)
            ("add new authentication module with JWT support", "feat", "auth"),
            ("fix null pointer exception in payment processor", "fix", "payment"),
            ("update API documentation with new endpoints", "docs", "api"),
            ("refactor database connection pooling", "refactor", "db"),
            ("improve search query performance by 50%", "perf", "search"),
            ("add unit tests for user service", "test", "user"),
            ("update webpack configuration", "build", "config"),
            ("configure GitHub Actions workflow", "ci", "workflow"),
            ("update dependencies to latest versions", "chore", "deps"),
            ("breaking: change API response format", "feat!", "api"),
        ]
        
        summaries, types, scopes = zip(*training_data)
        
        # Vectorize summaries
        X = self.vectorizer.fit_transform(summaries)
        
        # Train classifier for commit type
        self.classifier.fit(X, types)
        
        # Train scope predictor separately
        self.scope_vectorizer = TfidfVectorizer(max_features=500)
        self.scope_classifier = RandomForestClassifier(n_estimators=50)
        X_scope = self.scope_vectorizer.fit_transform(summaries)
        self.scope_classifier.fit(X_scope, scopes)
    
    def predict_commit_type(
        self,
        diff_summary: str,
        confidence_threshold: float = 0.7
    ) -> Tuple[str, float]:
        """Predict commit type with confidence score"""
        X = self.vectorizer.transform([diff_summary])
        
        # Get prediction probabilities
        probs = self.classifier.predict_proba(X)[0]
        max_prob_idx = np.argmax(probs)
        
        commit_type = self.classifier.classes_[max_prob_idx]
        confidence = probs[max_prob_idx]
        
        # Fall back to 'chore' if confidence is low
        if confidence < confidence_threshold:
            return 'chore', confidence
        
        return commit_type, confidence
    
    def predict_scope(self, diff_summary: str) -> str:
        """Predict commit scope"""
        X = self.scope_vectorizer.transform([diff_summary])
        return self.scope_classifier.predict(X)[0]
    
    def save_model(self, path: Path):
        """Save trained model"""
        joblib.dump({
            'vectorizer': self.vectorizer,
            'classifier': self.classifier,
            'scope_vectorizer': self.scope_vectorizer,
            'scope_classifier': self.scope_classifier
        }, path)
    
    def load_model(self, path: Path):
        """Load trained model"""
        models = joblib.load(path)
        self.vectorizer = models['vectorizer']
        self.classifier = models['classifier']
        self.scope_vectorizer = models['scope_vectorizer']
        self.scope_classifier = models['scope_classifier']
```

### 3. Advanced Code Analysis
```python
# Deep code analysis with tree-sitter
import tree_sitter
from tree_sitter import Language, Parser
from typing import Set, Dict, List
from pathlib import Path

class AdvancedCodeAnalyzer:
    def __init__(self):
        # Load language parsers
        self.parsers = {
            '.py': self._setup_python_parser(),
            '.js': self._setup_javascript_parser(),
            '.ts': self._setup_typescript_parser(),
            '.rs': self._setup_rust_parser(),
            '.dart': self._setup_dart_parser(),
        }
        
    def analyze_file_changes(
        self,
        file_path: str,
        old_content: str,
        new_content: str
    ) -> Dict[str, Any]:
        """Analyze semantic changes in a file"""
        ext = Path(file_path).suffix
        parser = self.parsers.get(ext)
        
        if not parser:
            return self._basic_analysis(old_content, new_content)
        
        # Parse both versions
        old_tree = parser.parse(bytes(old_content, 'utf8'))
        new_tree = parser.parse(bytes(new_content, 'utf8'))
        
        # Analyze changes
        return {
            'added_functions': self._find_added_functions(old_tree, new_tree),
            'modified_functions': self._find_modified_functions(old_tree, new_tree),
            'added_classes': self._find_added_classes(old_tree, new_tree),
            'imports_changed': self._analyze_import_changes(old_tree, new_tree),
            'complexity_change': self._calculate_complexity_change(old_tree, new_tree),
            'test_coverage_impact': self._estimate_test_impact(old_tree, new_tree),
        }
    
    def _find_added_functions(
        self,
        old_tree: tree_sitter.Tree,
        new_tree: tree_sitter.Tree
    ) -> List[str]:
        """Find newly added functions"""
        old_functions = self._extract_functions(old_tree)
        new_functions = self._extract_functions(new_tree)
        
        return list(new_functions - old_functions)
    
    def _extract_functions(self, tree: tree_sitter.Tree) -> Set[str]:
        """Extract function names from AST"""
        functions = set()
        
        # Query for function definitions (Python example)
        query = self.python_language.query("""
        (function_definition
            name: (identifier) @function_name)
        """)
        
        captures = query.captures(tree.root_node)
        for node, _ in captures:
            functions.add(node.text.decode('utf8'))
        
        return functions
    
    def _calculate_complexity_change(
        self,
        old_tree: tree_sitter.Tree,
        new_tree: tree_sitter.Tree
    ) -> int:
        """Calculate cyclomatic complexity change"""
        old_complexity = self._calculate_complexity(old_tree)
        new_complexity = self._calculate_complexity(new_tree)
        
        return new_complexity - old_complexity
```

### 4. Cross-Package Dependency Detection
```python
# Enhanced dependency detection
from typing import Dict, List, Set, Tuple
import re
from pathlib import Path

class DependencyAnalyzer:
    def __init__(self):
        self.import_patterns = {
            'python': [
                re.compile(r'^import\s+(\S+)', re.M),
                re.compile(r'^from\s+(\S+)\s+import', re.M)
            ],
            'javascript': [
                re.compile(r'import\s+.*\s+from\s+[\'"](.+?)[\'"]', re.M),
                re.compile(r'require\([\'"](.+?)[\'"]\)', re.M)
            ],
            'dart': [
                re.compile(r'^import\s+[\'"](.+?)[\'"]', re.M)
            ],
            'rust': [
                re.compile(r'^use\s+(\S+)', re.M),
                re.compile(r'^extern\s+crate\s+(\S+)', re.M)
            ]
        }
    
    def analyze_cross_package_impact(
        self,
        changes: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """Analyze impact across packages"""
        impact_map = {}
        
        # Build dependency graph
        dep_graph = self._build_dependency_graph(changes)
        
        # For each changed package, find affected packages
        for package, files in changes.items():
            affected = self._find_affected_packages(package, dep_graph)
            if affected:
                impact_map[package] = affected
        
        return impact_map
    
    def _build_dependency_graph(
        self,
        changes: Dict[str, List[str]]
    ) -> Dict[str, Set[str]]:
        """Build graph of package dependencies"""
        graph = {}
        
        # Scan all packages for dependencies
        for package in ['dart', 'flutter', 'rust', 'python']:
            deps = self._scan_package_dependencies(package)
            graph[package] = deps
        
        return graph
    
    def _find_affected_packages(
        self,
        changed_package: str,
        dep_graph: Dict[str, Set[str]]
    ) -> List[str]:
        """Find packages that depend on the changed package"""
        affected = []
        
        for package, deps in dep_graph.items():
            if changed_package in deps and package != changed_package:
                affected.append(package)
        
        return affected
```

### 5. Interactive Commit Builder
```python
# Enhanced interactive commit interface
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.shortcuts import checkboxlist_dialog, radiolist_dialog
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax

console = Console()

class InteractiveCommitBuilder:
    def __init__(self, analyzer_results: Dict[str, Any]):
        self.results = analyzer_results
        self.console = console
        
    def build_commit_interactively(self) -> str:
        """Interactive commit message building"""
        # 1. Select commit type
        commit_type = self._select_commit_type()
        
        # 2. Select scope
        scope = self._select_scope()
        
        # 3. Enter subject
        subject = self._enter_subject()
        
        # 4. Select changed items to highlight
        highlights = self._select_highlights()
        
        # 5. Add breaking change note if needed
        breaking = self._check_breaking_change()
        
        # 6. Generate body
        body = self._generate_body(highlights)
        
        # 7. Preview and confirm
        message = self._build_message(commit_type, scope, subject, body, breaking)
        
        if self._preview_and_confirm(message):
            return message
        else:
            # Recursive call to rebuild
            return self.build_commit_interactively()
    
    def _select_commit_type(self) -> str:
        """Select commit type with descriptions"""
        result = radiolist_dialog(
            title="Select Commit Type",
            text="Choose the type that best describes your changes:",
            values=[
                ("feat", "✨ A new feature"),
                ("fix", "🐛 A bug fix"),
                ("docs", "📚 Documentation only changes"),
                ("style", "💎 Code style changes (formatting, etc)"),
                ("refactor", "📦 Code refactoring"),
                ("perf", "🚀 Performance improvements"),
                ("test", "🚨 Adding or updating tests"),
                ("build", "🛠  Build system changes"),
                ("ci", "⚙️  CI configuration changes"),
                ("chore", "♻️  Other changes"),
                ("revert", "🗑  Revert previous commit"),
            ]
        ).run()
        
        return result or "chore"
    
    def _select_highlights(self) -> List[str]:
        """Select important changes to highlight"""
        # Get all significant changes
        changes = []
        
        if 'added_functions' in self.results:
            for func in self.results['added_functions']:
                changes.append(('function', f"Added function: {func}"))
        
        if 'modified_classes' in self.results:
            for cls in self.results['modified_classes']:
                changes.append(('class', f"Modified class: {cls}"))
        
        # Let user select which to include
        selected = checkboxlist_dialog(
            title="Select Changes to Highlight",
            text="Choose the most important changes:",
            values=changes
        ).run()
        
        return selected or []
    
    def _preview_and_confirm(self, message: str) -> bool:
        """Preview commit message with syntax highlighting"""
        self.console.clear()
        self.console.print("[bold]Commit Message Preview:[/bold]\n")
        
        # Syntax highlight the commit message
        syntax = Syntax(message, "text", theme="monokai", line_numbers=True)
        self.console.print(syntax)
        
        # Show stats
        table = Table(title="Commit Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Subject Length", str(len(message.split('\n')[0])))
        table.add_row("Total Length", str(len(message)))
        table.add_row("Line Count", str(len(message.split('\n'))))
        
        self.console.print("\n", table)
        
        return prompt("\nAccept this commit message? (y/n): ").lower() == 'y'
```

### 6. Commit History Learning
```python
# Learn from repository's commit history
from collections import Counter
import re
from typing import List, Dict

class CommitHistoryLearner:
    def __init__(self, repo_path: str = '.'):
        self.repo = git.Repo(repo_path)
        self.patterns = self._learn_patterns()
        
    def _learn_patterns(self) -> Dict[str, Any]:
        """Learn commit patterns from history"""
        commits = list(self.repo.iter_commits(max_count=1000))
        
        # Analyze commit messages
        patterns = {
            'common_prefixes': Counter(),
            'common_scopes': Counter(),
            'message_templates': [],
            'avg_subject_length': 0,
            'avg_body_length': 0,
        }
        
        subject_lengths = []
        body_lengths = []
        
        for commit in commits:
            message = commit.message
            lines = message.split('\n')
            subject = lines[0]
            
            # Extract prefix (feat:, fix:, etc)
            prefix_match = re.match(r'^(\w+)(\([\w-]+\))?:', subject)
            if prefix_match:
                prefix = prefix_match.group(1)
                patterns['common_prefixes'][prefix] += 1
                
                # Extract scope if present
                if prefix_match.group(2):
                    scope = prefix_match.group(2).strip('()')
                    patterns['common_scopes'][scope] += 1
            
            # Track lengths
            subject_lengths.append(len(subject))
            if len(lines) > 2:
                body = '\n'.join(lines[2:])
                body_lengths.append(len(body))
        
        # Calculate averages
        patterns['avg_subject_length'] = sum(subject_lengths) / len(subject_lengths)
        if body_lengths:
            patterns['avg_body_length'] = sum(body_lengths) / len(body_lengths)
        
        return patterns
    
    def suggest_format(self, commit_type: str, scope: str) -> str:
        """Suggest format based on history"""
        # Find most common pattern for this type
        common_patterns = []
        
        for commit in self.repo.iter_commits(max_count=100):
            if commit_type in commit.message:
                common_patterns.append(commit.message.split('\n')[0])
        
        # Return most representative pattern
        if common_patterns:
            return self._find_representative_pattern(common_patterns)
        
        # Default format
        return f"{commit_type}({scope}): <subject>"
```

## Dependencies to Add
```toml
[project.dependencies]
aiohttp = "^3.9.0"
scikit-learn = "^1.3.2"
joblib = "^1.3.2"
tree-sitter = "^0.20.4"
tree-sitter-python = "^0.20.4"
tree-sitter-javascript = "^0.20.3"
tree-sitter-rust = "^0.20.4"
prompt-toolkit = "^3.0.43"
rich = "^13.7.0"
GitPython = "^3.1.40"
numpy = "^1.26.2"
tenacity = "^8.2.3"
```

## Migration Strategy
1. Add async infrastructure for parallel analysis
2. Implement ML classifier with training pipeline
3. Add tree-sitter for better code analysis
4. Create interactive UI components
5. Build learning system from commit history

## Expected Benefits
- **Performance**: 3-4x faster with async operations
- **Accuracy**: ML-based classification and scope detection
- **Intelligence**: Learn from repository patterns
- **User Experience**: Interactive commit building
- **Code Understanding**: Deep semantic analysis with tree-sitter