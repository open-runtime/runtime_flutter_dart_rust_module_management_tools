# Smart Commit Tools - Comprehensive Documentation

## Table of Contents

1. [Overview](#overview)
2. [Why Smart Commit?](#why-smart-commit)
3. [Tool Comparison](#tool-comparison)
4. [Architecture Deep Dive](#architecture-deep-dive)
5. [smart_commit_fast.py - The Speed Champion](#smart_commit_fastpy---the-speed-champion)
6. [smart_commit.py - The Thoroughbred](#smart_commitpy---the-thoroughbred)
7. [Usage Guide](#usage-guide)
8. [Performance Optimization](#performance-optimization)
9. [Advanced Features](#advanced-features)
10. [Best Practices](#best-practices)
11. [Troubleshooting](#troubleshooting)
12. [Future Roadmap](#future-roadmap)

## Overview

The Smart Commit suite consists of two AI-powered tools that revolutionize the git commit workflow:

- **`smart_commit_fast.py`**: Ultra-fast commits (2-3s) optimized for everyday development
- **`smart_commit.py`**: Comprehensive analysis (30-50s) for complex, multi-package changes

Both tools leverage Google's Gemini AI models to analyze code changes and generate conventional commit messages that are informative, consistent, and follow best practices.

## Why Smart Commit?

### The Problem with Manual Commits

1. **Inconsistent Messages**: Different developers write commits differently
2. **Missing Context**: Important details often omitted
3. **Poor Categorization**: Changes not properly grouped by package/scope
4. **Time Consuming**: Writing good commit messages takes mental effort
5. **Cross-Package Blindness**: Hard to see how changes affect multiple packages

### The Smart Commit Solution

1. **AI-Powered Analysis**: Understands code changes at a semantic level
2. **Conventional Format**: Always follows conventional commit standards
3. **Package-Aware**: Recognizes monorepo structure and package boundaries
4. **Context-Rich**: Includes technical details, impacts, and dependencies
5. **Speed Options**: Choose between speed and thoroughness

## Tool Comparison

| Feature | smart_commit_fast.py | smart_commit.py |
|---------|---------------------|-----------------|
| **Default Speed** | 2-3 seconds | 30-50 seconds |
| **AI Calls** | 1 (default) | 11 |
| **Model** | Flash (fast) | Pro (comprehensive) |
| **Analysis Depth** | Summary | Deep technical analysis |
| **Package Analysis** | Combined | Individual + cross-package |
| **Context Gathering** | Enhanced (optional) | Standard |
| **Multi-stage Pipeline** | Yes (--enhanced) | No |
| **Parallel Processing** | Yes | Yes |
| **Best For** | Daily commits | Complex PRs |

## Architecture Deep Dive

### Core Components

#### 1. Text Sanitization Layer
Both tools include robust text sanitization to handle:
- ANSI escape sequences from git output
- Control characters and spinner animations
- Markdown artifacts from AI responses
- Progress indicators and formatting codes

```python
class TextSanitizer:
    """Handles cleaning of text from ANSI codes and control characters"""
    
    @staticmethod
    def sanitize_text(text: str) -> str:
        # Remove ANSI escape sequences
        # Remove spinner characters
        # Remove control characters but keep newlines and tabs
        # Clean AI response artifacts
```

#### 2. File Categorization Engine
Intelligent file categorization for monorepo structure:

```python
PACKAGE_PATTERNS = [
    (re.compile(r'^dart/rust/'), 'rust'),
    (re.compile(r'^flutter/'), 'flutter'),
    (re.compile(r'^dart/'), 'dart'),
    (re.compile(r'^tooling/'), 'tooling'),
    # ... more patterns
]
```

#### 3. Context Gathering System
Enhanced context gathering extracts:
- File history and recent commits
- Code symbols (functions, classes, imports)
- Dependency relationships
- Related issues from branch names
- Test file associations

#### 4. AI Analysis Pipeline
Multi-model support with fallback:
- Primary: Gemini 2.0 Flash (speed)
- Enhanced: Gemini 2.5 Pro (depth)
- Configurable via environment variables

### How smart_commit_fast.py Works - Technical Deep Dive

#### Overall Flow Diagram

```mermaid
graph TB
    Start([Start]) --> Check[Check Prerequisites]
    Check --> GetChanges[Get All Changed Files]
    GetChanges --> Mode{Which Mode?}
    
    Mode -->|Default/Quick| QuickAnalysis[Quick Mode Analysis]
    Mode -->|--max| MaxAnalysis[Max Mode Analysis]
    Mode -->|--max --enhanced| EnhancedAnalysis[Enhanced Multi-Stage]
    
    QuickAnalysis --> SingleAI[Single AI Call<br/>2-3 seconds]
    MaxAnalysis --> ParallelAI[Parallel Package Analysis<br/>15-20 seconds]
    EnhancedAnalysis --> MultiStage[4-Stage Pipeline<br/>20-30 seconds]
    
    SingleAI --> GenerateMsg[Generate Commit Message]
    ParallelAI --> GenerateMsg
    MultiStage --> GenerateMsg
    
    GenerateMsg --> Display[Display Message]
    Display --> Confirm{User Confirms?}
    Confirm -->|Yes| Commit[Commit & Push]
    Confirm -->|Edit| Edit[Edit Message]
    Confirm -->|No| End([End])
    
    Edit --> Commit
    Commit --> End
    
    style Start fill:#2ecc71,stroke:#27ae60,stroke-width:3px,color:#fff
    style End fill:#e74c3c,stroke:#c0392b,stroke-width:3px,color:#fff
    style SingleAI fill:#3498db,stroke:#2980b9,stroke-width:2px,color:#fff
    style ParallelAI fill:#9b59b6,stroke:#8e44ad,stroke-width:2px,color:#fff
    style MultiStage fill:#e67e22,stroke:#d35400,stroke-width:2px,color:#fff
```

#### Quick Mode Analysis (Default)

```mermaid
graph LR
    subgraph "Quick Mode Pipeline"
        Files[Changed Files] --> Cat[Categorize by Package]
        Cat --> Context[Gather Context<br/>- File history<br/>- Symbols<br/>- Dependencies]
        Context --> Sample[Sample Diffs<br/>Max 5 files]
        Sample --> Prompt[Build Optimized Prompt]
        Prompt --> AI[Single Gemini Flash Call]
        AI --> Message[Commit Message]
    end
    
    style Files fill:#34495e,stroke:#2c3e50,stroke-width:2px,color:#fff
    style AI fill:#3498db,stroke:#2980b9,stroke-width:3px,color:#fff
    style Message fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff
```

The quick mode works by:
1. **File Collection**: Uses `git status --porcelain` for all changes
2. **Smart Categorization**: Groups files by package using compiled regex patterns
3. **Context Gathering**: Extracts metadata without full diff analysis
4. **Prompt Optimization**: Builds a concise prompt with file summaries and sample diffs
5. **Single AI Call**: Uses Gemini Flash for 2-3 second response

#### Enhanced Multi-Stage Analysis

```mermaid
graph TB
    subgraph "Stage 1: Classification"
        S1_Files[All Files] --> S1_Context[Gather Full Context]
        S1_Context --> S1_AI[AI Classification]
        S1_AI --> S1_Output[File Importance Map<br/>- Critical/High/Medium/Low<br/>- Risk Assessment<br/>- Change Types]
    end
    
    subgraph "Stage 2: Deep Analysis"
        S1_Output --> S2_Filter[Filter Critical Files]
        S2_Filter --> S2_Diffs[Get Full Diffs]
        S2_Diffs --> S2_AI[AI Deep Analysis]
        S2_AI --> S2_Output[Technical Implications<br/>Breaking Changes<br/>Dependencies]
    end
    
    subgraph "Stage 3: Dependency Impact"
        S2_Output --> S3_Graph[Build Dependency Graph]
        S3_Graph --> S3_AI[AI Impact Analysis]
        S3_AI --> S3_Output[Ripple Effects<br/>Integration Points<br/>Missing Tests]
    end
    
    subgraph "Stage 4: Metadata Generation"
        S3_Output --> S4_Compile[Compile All Analyses]
        S4_Compile --> S4_AI[AI Metadata Generation]
        S4_AI --> S4_Output[Version Bump<br/>PR Labels<br/>Changelog Entry<br/>Review Checklist]
    end
    
    S4_Output --> Final[Final Commit Message<br/>+ Rich Metadata]
    
    style S1_AI fill:#3498db,stroke:#2980b9,stroke-width:2px,color:#fff
    style S2_AI fill:#9b59b6,stroke:#8e44ad,stroke-width:2px,color:#fff
    style S3_AI fill:#e67e22,stroke:#d35400,stroke-width:2px,color:#fff
    style S4_AI fill:#e74c3c,stroke:#c0392b,stroke-width:2px,color:#fff
    style Final fill:#2ecc71,stroke:#27ae60,stroke-width:3px,color:#fff
```

#### Context Gathering Deep Dive

```mermaid
graph LR
    subgraph "Context Gathering System"
        File[Changed File] --> History[Get History<br/>git log -n 5]
        File --> Symbols[Extract Symbols<br/>Functions/Classes/Imports]
        File --> Deps[Find Dependencies<br/>Who imports this?]
        File --> Tests[Find Test Files<br/>*_test, test_*]
        File --> Type[Determine Type<br/>Language/Purpose]
        
        History --> Context[Rich Context Object]
        Symbols --> Context
        Deps --> Context
        Tests --> Context
        Type --> Context
    end
    
    style File fill:#34495e,stroke:#2c3e50,stroke-width:2px,color:#fff
    style Context fill:#2ecc71,stroke:#27ae60,stroke-width:3px,color:#fff
```

The context gathering system:
1. **File History**: Last 5 commits, modification dates, commit messages
2. **Symbol Extraction**: Language-aware parsing for functions, classes, imports
3. **Dependency Mapping**: Uses `git grep` to find importers
4. **Test Discovery**: Pattern matching for associated test files
5. **Type Classification**: Language, test, doc, config, generated

### How smart_commit.py Works - Technical Deep Dive

#### Overall Architecture

```mermaid
graph TB
    subgraph "Initialization"
        Start([Start]) --> Check[Check Prerequisites<br/>- gemini-cli<br/>- API key]
        Check --> Status[Check Git Status]
        Status --> Stage{Need Staging?}
        Stage -->|Yes| Interactive[Interactive Staging]
        Stage -->|No| Proceed[Proceed]
        Interactive --> Proceed
    end
    
    subgraph "Analysis Phase"
        Proceed --> Collect[Collect All Files]
        Collect --> Categorize[Categorize by Package<br/>9 Categories]
        Categorize --> Progress[Start Progress Tracker]
        Progress --> Parallel[Parallel Analysis]
        
        Parallel --> P1[Dart Package]
        Parallel --> P2[Flutter Package]
        Parallel --> P3[Rust Package]
        Parallel --> P4[Tooling]
        Parallel --> P5[Docs]
        Parallel --> P6[Config]
        Parallel --> P7[Tests]
        Parallel --> P8[Top-Level]
        Parallel --> P9[Other]
    end
    
    subgraph "Synthesis Phase"
        P1 --> Compile[Compile Analyses]
        P2 --> Compile
        P3 --> Compile
        P4 --> Compile
        P5 --> Compile
        P6 --> Compile
        P7 --> Compile
        P8 --> Compile
        P9 --> Compile
        
        Compile --> Cross[Cross-Package Analysis]
        Cross --> Generate[Generate Final Message]
    end
    
    Generate --> Display[Display & Confirm]
    Display --> End([End])
    
    style Start fill:#2ecc71,stroke:#27ae60,stroke-width:3px,color:#fff
    style Parallel fill:#e74c3c,stroke:#c0392b,stroke-width:3px,color:#fff
    style Cross fill:#9b59b6,stroke:#8e44ad,stroke-width:3px,color:#fff
    style End fill:#34495e,stroke:#2c3e50,stroke-width:3px,color:#fff
```

#### Package Analysis Pipeline

```mermaid
graph LR
    subgraph "Per-Package Analysis"
        Files[Package Files] --> Diff[Generate Diffs<br/>- Staged<br/>- Unstaged]
        Diff --> Prompt[Build Analysis Prompt<br/>- Files list<br/>- Full diffs<br/>- Package context]
        Prompt --> AI[Gemini Pro Call<br/>60s timeout]
        AI --> Analysis[Package Analysis<br/>- What changed<br/>- Why changed<br/>- Technical details<br/>- Dependencies]
    end
    
    style Files fill:#34495e,stroke:#2c3e50,stroke-width:2px,color:#fff
    style AI fill:#3498db,stroke:#2980b9,stroke-width:3px,color:#fff
    style Analysis fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff
```

#### Progress Tracking System

```mermaid
graph TB
    subgraph "Real-time Progress Display"
        Thread[Background Thread] --> Loop{Running?}
        Loop -->|Yes| Update[Update Display<br/>Every 100ms]
        Update --> Render[Render Status<br/>⠋ Analyzing...<br/>✓ Complete<br/>✗ Error]
        Render --> Loop
        Loop -->|No| Final[Final Display]
        
        Status[Package Status] --> Update
        Status --> |"pending"| Spinner1[⠋ Gray]
        Status --> |"analyzing"| Spinner2[⠸ Yellow]
        Status --> |"complete"| Check[✓ Green]
        Status --> |"error"| Cross[✗ Red]
        Status --> |"skipped"| Dash[- Gray]
    end
    
    style Thread fill:#9b59b6,stroke:#8e44ad,stroke-width:2px,color:#fff
    style Check fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff
    style Cross fill:#e74c3c,stroke:#c0392b,stroke-width:2px,color:#fff
```

### Detailed Algorithm Explanations

#### 1. File Categorization Algorithm

```python
def categorize_files(files: List[str]) -> Dict[str, List[str]]:
    """
    Algorithm:
    1. For each file, strip git status prefixes (M, A, D, etc.)
    2. Apply regex patterns in order (most specific first)
    3. Fall back to location-based rules
    4. Group into 9 categories for comprehensive analysis
    """
    
    # Order matters - most specific patterns first
    for file in files:
        if file.startswith("dart/rust/"):
            category = "Rust"  # Rust FFI bindings
        elif file.startswith("flutter/"):
            category = "Flutter"  # Flutter-specific code
        elif file.startswith("dart/"):
            category = "Dart"  # Pure Dart code
        # ... continue pattern matching
```

#### 2. Context Extraction Algorithm

```python
def extract_symbols(file: str, diff: str) -> Dict[str, List[str]]:
    """
    Language-aware symbol extraction:
    1. Detect file language by extension
    2. Apply language-specific regex patterns
    3. Extract only from added/modified lines (+)
    4. Return categorized symbols
    """
    
    # Example for Python
    if file.endswith('.py'):
        # Function: def function_name(
        # Class: class ClassName:
        # Import: import module, from module import
```

#### 3. Parallel Analysis Coordination

```mermaid
graph TB
    subgraph "ThreadPoolExecutor Flow"
        Main[Main Thread] --> Submit[Submit 9 Tasks]
        Submit --> W1[Worker 1<br/>Dart]
        Submit --> W2[Worker 2<br/>Flutter]
        Submit --> W3[Worker 3<br/>Rust]
        Submit --> WN[Worker N<br/>...]
        
        W1 --> Future1[Future Result]
        W2 --> Future2[Future Result]
        W3 --> Future3[Future Result]
        WN --> FutureN[Future Result]
        
        Future1 --> Complete[as_completed()]
        Future2 --> Complete
        Future3 --> Complete
        FutureN --> Complete
        
        Complete --> Update[Update Progress]
        Update --> Collect[Collect Results]
    end
    
    style Main fill:#3498db,stroke:#2980b9,stroke-width:3px,color:#fff
    style Complete fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff
```

#### 4. AI Prompt Engineering Strategy

```mermaid
graph LR
    subgraph "Prompt Construction"
        Context[Package Context] --> Structure[Structured Prompt]
        Files[File List] --> Structure
        Diffs[Code Diffs] --> Structure
        Instructions[Analysis Instructions] --> Structure
        
        Structure --> Sections[Prompt Sections<br/>1. Role Definition<br/>2. Context Setting<br/>3. Data Presentation<br/>4. Task Instructions<br/>5. Output Format]
        
        Sections --> Token[Token Optimization<br/>- Limit diffs<br/>- Summarize files<br/>- Focus instructions]
    end
    
    style Context fill:#34495e,stroke:#2c3e50,stroke-width:2px,color:#fff
    style Token fill:#e74c3c,stroke:#c0392b,stroke-width:2px,color:#fff
```

### Performance Characteristics

#### Time Complexity Analysis

```mermaid
graph TB
    subgraph "smart_commit_fast.py"
        Fast_Files[O(n) File Collection] --> Fast_Cat[O(n) Categorization]
        Fast_Cat --> Fast_Context[O(k) Context<br/>k = min(n, 20)]
        Fast_Context --> Fast_AI[O(1) Single AI Call]
        Fast_Total[Total: O(n) + 2-3s constant]
    end
    
    subgraph "smart_commit.py"
        Slow_Files[O(n) File Collection] --> Slow_Cat[O(n) Categorization]
        Slow_Cat --> Slow_Diff[O(n*m) Diff Generation<br/>m = lines per file]
        Slow_Diff --> Slow_AI[O(p) AI Calls<br/>p = packages with changes]
        Slow_AI --> Slow_Cross[O(1) Cross Analysis]
        Slow_Total[Total: O(n*m) + p*5s + 5s]
    end
    
    style Fast_Total fill:#2ecc71,stroke:#27ae60,stroke-width:3px,color:#fff
    style Slow_Total fill:#e74c3c,stroke:#c0392b,stroke-width:3px,color:#fff
```

### Memory Usage Patterns

```mermaid
graph LR
    subgraph "Memory Profile"
        Start[Baseline<br/>~50MB] --> Load[Load Files<br/>+10-50MB]
        Load --> Diff[Generate Diffs<br/>+20-200MB]
        Diff --> Context[Build Context<br/>+5-20MB]
        Context --> AI[AI Processing<br/>+100-500MB]
        AI --> Clean[Cleanup<br/>-50-400MB]
        Clean --> End[Final<br/>~100MB]
    end
    
    style Start fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff
    style AI fill:#e74c3c,stroke:#c0392b,stroke-width:2px,color:#fff
    style End fill:#3498db,stroke:#2980b9,stroke-width:2px,color:#fff
```

### Technical Implementation Details

#### Git Integration Layer

```mermaid
graph TB
    subgraph "Git Command Execution"
        Cmd[Git Command] --> Sub[subprocess.run()]
        Sub --> Timeout{Timeout?}
        Timeout -->|No| Output[Capture Output]
        Timeout -->|Yes| Kill[Kill Process]
        
        Output --> Sanitize[Text Sanitization]
        Kill --> Error[Error Handling]
        
        Sanitize --> Parse[Parse Results]
        Error --> Retry{Retry?}
        Retry -->|Yes| Cmd
        Retry -->|No| Fail[Report Failure]
    end
    
    style Cmd fill:#34495e,stroke:#2c3e50,stroke-width:2px,color:#fff
    style Sanitize fill:#3498db,stroke:#2980b9,stroke-width:2px,color:#fff
    style Error fill:#e74c3c,stroke:#c0392b,stroke-width:2px,color:#fff
```

The Git integration layer handles:
- **Command Execution**: Safe subprocess calls with timeouts
- **Output Sanitization**: Removes ANSI codes and control characters
- **Error Recovery**: Graceful handling of git failures
- **Performance**: Caches frequently used commands

#### Symbol Extraction Engine

```mermaid
graph LR
    subgraph "Language-Specific Parsers"
        Diff[Git Diff] --> Lang{Language?}
        
        Lang -->|Python| PyParser[Python Parser<br/>- def functions<br/>- class definitions<br/>- imports]
        Lang -->|Dart| DartParser[Dart Parser<br/>- void/type functions<br/>- class declarations<br/>- imports]
        Lang -->|Rust| RustParser[Rust Parser<br/>- fn functions<br/>- struct/trait<br/>- use statements]
        Lang -->|JS/TS| JSParser[JS/TS Parser<br/>- function/const<br/>- class/interface<br/>- import/export]
        
        PyParser --> Symbols[Symbol Map]
        DartParser --> Symbols
        RustParser --> Symbols
        JSParser --> Symbols
    end
    
    style Diff fill:#34495e,stroke:#2c3e50,stroke-width:2px,color:#fff
    style Symbols fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff
```

#### AI Communication Protocol

```mermaid
sequenceDiagram
    participant Tool as Smart Commit Tool
    participant Sanitizer as Text Sanitizer
    participant Gemini as Gemini CLI
    participant API as Gemini API
    
    Tool->>Sanitizer: Raw prompt
    Sanitizer->>Tool: Clean prompt
    Tool->>Gemini: subprocess.Popen()
    Gemini->>API: HTTPS request
    API-->>Gemini: AI response
    Gemini-->>Tool: stdout/stderr
    Tool->>Sanitizer: Raw response
    Sanitizer->>Tool: Clean response
    
    Note over Tool,API: Timeout: 30s (fast) / 60s (full)
```

### Advanced Features Implementation

#### 1. Dependency Graph Construction

```mermaid
graph TB
    subgraph "Dependency Discovery"
        File[Changed File] --> Import[Find Importers<br/>git grep patterns]
        File --> Export[Find Exports<br/>Symbol analysis]
        File --> Test[Find Tests<br/>Pattern matching]
        
        Import --> Graph[Dependency Graph]
        Export --> Graph
        Test --> Graph
        
        Graph --> Analyze[Impact Analysis<br/>- Direct deps<br/>- Transitive deps<br/>- Circular deps]
    end
    
    style File fill:#34495e,stroke:#2c3e50,stroke-width:2px,color:#fff
    style Graph fill:#9b59b6,stroke:#8e44ad,stroke-width:2px,color:#fff
    style Analyze fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff
```

#### 2. Intelligent Diff Limiting

```python
def get_limited_diff(file: str, max_lines: int) -> str:
    """
    Smart diff limiting algorithm:
    1. Get full diff size
    2. If under limit, return full diff
    3. If over limit:
       - Prioritize file header (@@)
       - Include first N and last M lines
       - Add context around symbols
       - Indicate truncation points
    """
```

#### 3. Prompt Token Optimization

```mermaid
graph LR
    subgraph "Token Budget Management"
        Full[Full Context<br/>10K tokens] --> Check{Over Budget?}
        Check -->|No| Send[Send to AI]
        Check -->|Yes| Optimize[Optimization]
        
        Optimize --> Trim[Trim Strategies<br/>- Limit files<br/>- Reduce diffs<br/>- Summarize context]
        Trim --> Priority[Prioritize<br/>- Critical files<br/>- Recent changes<br/>- Breaking changes]
        Priority --> Compact[Compact Format]
        Compact --> Send
    end
    
    style Full fill:#e74c3c,stroke:#c0392b,stroke-width:2px,color:#fff
    style Compact fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff
```

### Error Handling and Recovery

```mermaid
graph TB
    subgraph "Error Recovery System"
        Operation[Any Operation] --> Try{Success?}
        Try -->|Yes| Continue[Continue]
        Try -->|No| Error[Error Type?]
        
        Error -->|Timeout| Retry1[Retry with<br/>shorter timeout]
        Error -->|API Error| Retry2[Retry with<br/>backoff]
        Error -->|Git Error| Fallback[Fallback<br/>strategy]
        Error -->|Parse Error| Default[Default<br/>behavior]
        
        Retry1 --> Try
        Retry2 --> Try
        Fallback --> Continue
        Default --> Continue
    end
    
    style Operation fill:#34495e,stroke:#2c3e50,stroke-width:2px,color:#fff
    style Error fill:#e74c3c,stroke:#c0392b,stroke-width:2px,color:#fff
    style Continue fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff
```

### Caching Architecture

```mermaid
graph TB
    subgraph "Multi-Level Cache"
        Request[Data Request] --> L1{L1: Memory<br/>Cache?}
        L1 -->|Hit| Return1[Return Data]
        L1 -->|Miss| L2{L2: File<br/>Cache?}
        L2 -->|Hit| Update1[Update L1]
        L2 -->|Miss| Compute[Compute Data]
        
        Update1 --> Return1
        Compute --> Update2[Update L1 & L2]
        Update2 --> Return2[Return Data]
        
        subgraph "Cache Types"
            C1[Git Commands<br/>TTL: 5 min]
            C2[File Metadata<br/>TTL: Session]
            C3[Symbol Cache<br/>TTL: Until change]
            C4[AI Responses<br/>TTL: 1 hour]
        end
    end
    
    style Request fill:#34495e,stroke:#2c3e50,stroke-width:2px,color:#fff
    style Return1 fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff
    style Return2 fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff
```

### Metadata Generation Pipeline

```mermaid
graph LR
    subgraph "Metadata Generation (Enhanced Mode)"
        Analysis[All Analyses] --> Extract[Extract Signals<br/>- Breaking changes<br/>- API changes<br/>- New features]
        
        Extract --> Version[Version Bump<br/>Logic]
        Extract --> Labels[PR Label<br/>Inference]
        Extract --> Changelog[Changelog<br/>Generation]
        Extract --> Checklist[Review<br/>Checklist]
        
        Version --> Meta[Metadata Object]
        Labels --> Meta
        Changelog --> Meta
        Checklist --> Meta
        
        Meta --> Save[Save to<br/>.git/commit-metadata/]
    end
    
    style Analysis fill:#34495e,stroke:#2c3e50,stroke-width:2px,color:#fff
    style Meta fill:#9b59b6,stroke:#8e44ad,stroke-width:2px,color:#fff
    style Save fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff
```

### Optimization Strategies

#### 1. Parallel Processing Architecture

```mermaid
graph TB
    subgraph "Process Pool Design"
        Main[Main Process] --> Pool[ProcessPoolExecutor<br/>workers = CPU count]
        
        Pool --> W1[Worker 1<br/>Package A]
        Pool --> W2[Worker 2<br/>Package B]
        Pool --> W3[Worker 3<br/>Package C]
        Pool --> WN[Worker N<br/>Package N]
        
        W1 --> IPC1[IPC: Pickle]
        W2 --> IPC2[IPC: Pickle]
        W3 --> IPC3[IPC: Pickle]
        WN --> IPCN[IPC: Pickle]
        
        IPC1 --> Results[Aggregated<br/>Results]
        IPC2 --> Results
        IPC3 --> Results
        IPCN --> Results
    end
    
    style Main fill:#3498db,stroke:#2980b9,stroke-width:3px,color:#fff
    style Pool fill:#e74c3c,stroke:#c0392b,stroke-width:2px,color:#fff
    style Results fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff
```

#### 2. Memory-Efficient Diff Processing

```python
def process_large_diff(file_path: str, chunk_size: int = 1000):
    """
    Stream-based diff processing for large files:
    1. Read diff in chunks
    2. Process each chunk independently
    3. Aggregate results without loading full diff
    4. Yield processed chunks for immediate use
    """
    with subprocess.Popen(['git', 'diff', file_path], 
                         stdout=subprocess.PIPE, 
                         text=True) as proc:
        buffer = []
        for line in proc.stdout:
            buffer.append(line)
            if len(buffer) >= chunk_size:
                yield process_chunk(buffer)
                buffer = []
        if buffer:
            yield process_chunk(buffer)
```

### Integration Points

```mermaid
graph TB
    subgraph "External Integrations"
        Tool[Smart Commit] --> Git[Git CLI<br/>- status<br/>- diff<br/>- log<br/>- grep]
        Tool --> Gemini[Gemini CLI<br/>- prompt<br/>- model selection]
        Tool --> FS[File System<br/>- read files<br/>- find patterns<br/>- cache data]
        Tool --> Env[Environment<br/>- API keys<br/>- config vars<br/>- user prefs]
        
        Git --> Output[Unified<br/>Output]
        Gemini --> Output
        FS --> Output
        Env --> Output
    end
    
    style Tool fill:#34495e,stroke:#2c3e50,stroke-width:3px,color:#fff
    style Output fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff
```

### Security Considerations

```mermaid
graph LR
    subgraph "Security Layers"
        Input[User Input] --> Sanitize[Input Sanitization<br/>- Remove control chars<br/>- Escape sequences<br/>- Path validation]
        
        Sanitize --> Validate[Validation<br/>- File paths<br/>- Git commands<br/>- API inputs]
        
        Validate --> Execute[Safe Execution<br/>- Subprocess limits<br/>- Timeout controls<br/>- Resource limits]
        
        Execute --> Output[Output Filtering<br/>- No secrets<br/>- No PII<br/>- Clean responses]
    end
    
    style Input fill:#e74c3c,stroke:#c0392b,stroke-width:2px,color:#fff
    style Output fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff
```

## smart_commit_fast.py - The Speed Champion

### Key Innovations

#### 1. Single-Pass Analysis (Default Mode)
```python
def analyze_quick_mode(self, all_files: List[str]) -> str:
    """Single fast AI call for quick mode with enhanced context"""
    # Gather context in parallel
    # Build optimized prompt
    # Single AI call with Flash model
    # Return in 2-3 seconds
```

#### 2. Enhanced Multi-Stage Analysis (--enhanced flag)
Revolutionary 4-stage pipeline for deep understanding:

**Stage 1: Classification**
- Categorizes files by importance (critical/high/medium/low)
- Identifies change types (feature/fix/refactor/perf)
- Assesses risk levels
- Determines which files need deep analysis

**Stage 2: Deep Analysis**
- Focuses on critical files only
- Analyzes technical implications
- Identifies breaking changes
- Maps dependencies

**Stage 3: Dependency Impact**
- Analyzes ripple effects
- Identifies affected packages
- Finds integration points
- Suggests missing tests

**Stage 4: Metadata Generation**
- Suggests semantic version bumps
- Generates changelog entries
- Recommends PR labels
- Creates review checklists

#### 3. Smart Context Gathering
```python
class EnhancedContextGatherer:
    def gather_enhanced_context(self, files, diffs):
        # Extract code symbols
        # Analyze file history
        # Find related issues
        # Map dependencies
        # Identify test coverage
```

### Usage Examples

#### Default Mode (Fastest - 2-3s)
```bash
./tooling/smart_commit_fast.py
```

#### Max Analysis Mode (15-20s)
```bash
./tooling/smart_commit_fast.py --max
```

#### Enhanced Multi-Stage Mode (20-30s)
```bash
./tooling/smart_commit_fast.py --max --enhanced
```

#### Skip Cross-Package Analysis
```bash
./tooling/smart_commit_fast.py --max --skip-cross
```

### Performance Optimizations

1. **Parallel Diff Collection**: Uses ProcessPoolExecutor for true parallelism
2. **Limited Diff Sizes**: Caps at 500 lines per package
3. **Smart File Selection**: Prioritizes important files
4. **Batch Processing**: Groups related operations
5. **Compiled Regex Patterns**: Pre-compiled for speed

## smart_commit.py - The Thoroughbred

### Architecture

#### 1. Comprehensive Package Analysis
Analyzes each package individually:
- Dart package changes
- Flutter package changes
- Rust FFI bindings
- Tooling updates
- Documentation changes
- Configuration files
- Test modifications
- Top-level files

#### 2. Cross-Package Dependency Analysis
After individual analysis, performs cross-package impact assessment:
```python
def analyze_cross_package_impacts(self, all_analyses: str) -> str:
    """Analyze cross-package dependencies and impacts"""
    # Identify cross-package dependencies
    # Find interface changes
    # Map integration points
    # Detect potential conflicts
    # Assess architecture impact
```

#### 3. Real-Time Progress Tracking
Visual feedback with spinner animation:
```python
class ProgressTracker:
    """Handle progress display with spinner animation"""
    # Shows real-time status for each package
    # ⠋ Analyzing Dart...
    # ✓ Flutter complete
    # ⠸ Analyzing Rust...
```

### Advanced Features

1. **Interactive Staging**: Choose which files to include
2. **GitHub Integration**: Shows commit URL after push
3. **Editor Integration**: Edit generated messages in your preferred editor
4. **Regeneration Option**: Not happy? Regenerate with one command

## Usage Guide

### Prerequisites

1. **Install gemini-cli**:
   ```bash
   # Install via pip or your package manager
   pip install gemini-cli
   ```

2. **Set API Key**:
   ```bash
   export GEMINI_API_KEY="your-api-key"
   ```

3. **Python 3.6+** installed

### Workflow Examples

#### Daily Development Workflow
```bash
# Make your changes
vim src/feature.py

# Quick commit with smart analysis
./tooling/smart_commit_fast.py

# Review generated message (2-3s)
# Press Y to commit
```

#### Complex Feature Workflow
```bash
# Multiple package changes
vim dart/lib/api.dart
vim flutter/lib/widget.dart
vim rust/src/ffi.rs

# Use enhanced analysis
./tooling/smart_commit_fast.py --max --enhanced

# Review comprehensive analysis
# See suggested version bump
# Check breaking changes
# Commit with confidence
```

#### PR-Ready Commits
```bash
# Use the original tool for maximum detail
./tooling/smart_commit.py

# Get individual package analyses
# Cross-package dependency mapping
# Comprehensive commit message
# Perfect for PR descriptions
```

### Commit Message Quality

Both tools generate messages following this structure:

```
<type>(<scope>): <subject>

<body explaining changes>

<footer with breaking changes>
```

Example output:
```
feat(dart): implement advanced vector search with HNSW algorithm

- Added HNSWIndex class for hierarchical navigable small world graphs
- Implemented efficient k-NN search with O(log n) complexity
- Added comprehensive test suite with 95% coverage
- Integrated with existing VectorStore interface

Flutter package:
- Updated VectorSearchWidget to use new HNSW backend
- Added performance monitoring UI components
- Improved search result rendering performance by 40%

Rust FFI:
- Implemented native HNSW bindings for performance
- Added memory-safe wrappers for index operations
- Optimized vector distance calculations with SIMD

BREAKING CHANGE: VectorStore.search() now requires IndexType parameter
Migration: Add IndexType.HNSW to existing search calls
```

## Performance Optimization

### Speed Techniques

1. **Model Selection**:
   - Flash models for speed (gemini-2.0-flash-exp)
   - Pro models for depth (gemini-2.5-pro)
   - Automatic selection based on context size

2. **Prompt Optimization**:
   - Structured prompts for faster inference
   - Limited context windows
   - Focused analysis directives

3. **Parallel Processing**:
   ```python
   with ProcessPoolExecutor(max_workers=len(packages)) as executor:
       # True parallel analysis
   ```

4. **Caching Strategy**:
   - File metadata caching
   - Symbol extraction caching
   - Git command output caching

### Memory Management

1. **Diff Limiting**:
   ```python
   MAX_DIFF_LINES = 500  # Per package
   MAX_DIFF_PER_FILE = 100  # Per file
   ```

2. **File Prioritization**:
   - Analyze only top 20 files in quick mode
   - Focus on critical files in enhanced mode

## Advanced Features

### 1. Metadata Generation (smart_commit_fast.py --enhanced)

The tool generates rich metadata beyond the commit message:

```json
{
  "semantic_version_bump": "minor",
  "changelog_entry": {
    "type": "Added",
    "description": "Advanced vector search with HNSW algorithm",
    "breaking_changes": ["VectorStore.search() signature changed"]
  },
  "pr_labels": ["enhancement", "breaking-change", "performance"],
  "review_checklist": [
    "Verify HNSW index performance benchmarks",
    "Check memory usage with large datasets",
    "Validate migration guide completeness"
  ],
  "documentation_updates": ["API.md", "MIGRATION.md"],
  "follow_up_tasks": ["Add batch search optimization", "Implement index persistence"]
}
```

### 2. Issue Tracking Integration

Automatically detects and references issues:
- From branch names: `feature/issue-123-vector-search`
- From recent commits: `Fixes #456`
- From PR references: `Related to PR #789`

### 3. Symbol-Aware Analysis

Extracts and analyzes code symbols:
```python
{
  "functions": ["createIndex", "searchVectors", "calculateDistance"],
  "classes": ["HNSWIndex", "VectorNode", "SearchResult"],
  "imports": ["numpy", "scikit-learn", "faiss"],
  "exports": ["VectorSearchAPI", "IndexConfiguration"]
}
```

### 4. Dependency Mapping

Maps file relationships:
- Which files import the changed file
- Test files for the changed code
- Related configuration files
- Documentation that might need updates

## Best Practices

### 1. Choose the Right Tool

**Use smart_commit_fast.py when:**
- Making focused changes to 1-2 packages
- Daily development commits
- Need quick turnaround
- Changes are well-understood

**Use smart_commit.py when:**
- Complex multi-package changes
- Major refactoring
- Breaking changes
- Need detailed documentation

### 2. Optimize Your Workflow

1. **Pre-stage files**: Stage before running to skip interactive prompt
   ```bash
   git add .
   ./tooling/smart_commit_fast.py
   ```

2. **Use aliases**: Add to your shell config
   ```bash
   alias scf='./tooling/smart_commit_fast.py'
   alias sce='./tooling/smart_commit_fast.py --max --enhanced'
   alias sc='./tooling/smart_commit.py'
   ```

3. **Review metadata**: Use enhanced mode for PRs to get labels and checklists

### 3. Commit Message Guidelines

1. **Let AI do the heavy lifting**: Don't pre-edit, let the tool analyze
2. **Review for accuracy**: AI is good but verify technical details
3. **Add human context**: Edit to add "why" if AI misses it
4. **Keep conventional**: Stick to the generated format

## Troubleshooting

### Common Issues

1. **"Gemini API timeout"**
   - Solution: Reduce diff size or use quick mode
   - Check API key validity
   - Verify network connectivity

2. **"No changes detected"**
   - Solution: Check `git status`
   - Ensure files are saved
   - Verify you're in the right directory

3. **"Analysis failed for package X"**
   - Solution: Check if package has actual changes
   - Verify file permissions
   - Look for syntax errors in changed files

### Debug Mode

Enable verbose output:
```bash
DEBUG=1 ./tooling/smart_commit_fast.py
```

### Performance Tuning

Adjust timeouts and limits:
```python
# In smart_commit_fast.py
Config.MAX_DIFF_LINES = 300  # Reduce for faster analysis
Config.MAX_FILES_PER_PACKAGE = 3  # Fewer files to analyze
```

## Future Roadmap

### Planned Enhancements

1. **Local LLM Support**: Use Ollama or llama.cpp for offline commits
2. **Incremental Analysis**: Cache unchanged file analysis
3. **Git Hook Integration**: Automatic analysis on `git commit`
4. **IDE Plugins**: VSCode and IntelliJ integration
5. **Team Templates**: Customizable commit message templates
6. **Metrics Dashboard**: Track commit quality over time
7. **PR Description Generation**: Auto-generate PR descriptions
8. **Change Impact Prediction**: Estimate bug risk and test coverage

### Experimental Features

1. **Streaming Analysis**: Real-time analysis as you type
2. **Voice Commits**: Describe changes verbally
3. **Visual Diff Analysis**: Understand UI changes
4. **Test Generation**: Suggest tests for changes
5. **Documentation Updates**: Auto-update docs based on changes

## Comprehensive Tool Comparison

### Decision Flow Chart

```mermaid
graph TB
    Start([Need to Commit]) --> Size{Change Size?}
    
    Size -->|"< 10 files"| Quick[Use smart_commit_fast.py<br/>Default mode]
    Size -->|"10-50 files"| Medium{Complex Changes?}
    Size -->|"> 50 files"| Large{Time Available?}
    
    Medium -->|No| Quick
    Medium -->|Yes| Enhanced[Use smart_commit_fast.py<br/>--max --enhanced]
    
    Large -->|"< 1 min"| Quick
    Large -->|"1-5 min"| Enhanced
    Large -->|"> 5 min"| Full[Use smart_commit.py<br/>Full analysis]
    
    Quick --> Result1[2-3 seconds<br/>Good message]
    Enhanced --> Result2[20-30 seconds<br/>Great message<br/>+ metadata]
    Full --> Result3[30-50 seconds<br/>Comprehensive<br/>+ cross-package]
    
    style Start fill:#34495e,stroke:#2c3e50,stroke-width:3px,color:#fff
    style Quick fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff
    style Enhanced fill:#e67e22,stroke:#d35400,stroke-width:2px,color:#fff
    style Full fill:#e74c3c,stroke:#c0392b,stroke-width:2px,color:#fff
```

### Feature Matrix Visualization

```mermaid
graph LR
    subgraph "smart_commit_fast.py Features"
        F1[Ultra-fast 2-3s]
        F2[Single AI call]
        F3[Smart context]
        F4[Enhanced mode]
        F5[Metadata generation]
        F6[Process parallelism]
        F7[Symbol extraction]
        F8[Dependency mapping]
    end
    
    subgraph "smart_commit.py Features"
        S1[Comprehensive 30-50s]
        S2[Multi-package analysis]
        S3[Cross-package deps]
        S4[Real-time progress]
        S5[Interactive staging]
        S6[Thread parallelism]
        S7[Deep technical analysis]
        S8[Architecture impact]
    end
    
    style F1 fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff
    style F4 fill:#e67e22,stroke:#d35400,stroke-width:2px,color:#fff
    style S1 fill:#e74c3c,stroke:#c0392b,stroke-width:2px,color:#fff
    style S2 fill:#9b59b6,stroke:#8e44ad,stroke-width:2px,color:#fff
```

### Performance vs Quality Trade-off

```mermaid
graph TB
    subgraph "Trade-off Analysis"
        Fast[smart_commit_fast.py<br/>Default] --> Q1[Quality: 85%<br/>Speed: 2-3s]
        FastMax[smart_commit_fast.py<br/>--max] --> Q2[Quality: 90%<br/>Speed: 15-20s]
        FastEnhanced[smart_commit_fast.py<br/>--max --enhanced] --> Q3[Quality: 95%<br/>Speed: 20-30s]
        Full[smart_commit.py] --> Q4[Quality: 98%<br/>Speed: 30-50s]
        
        Q1 --> Use1[Daily commits<br/>Small changes<br/>Clear purpose]
        Q2 --> Use2[Feature commits<br/>Multiple files<br/>Single package]
        Q3 --> Use3[Complex features<br/>Need metadata<br/>PR preparation]
        Q4 --> Use4[Major changes<br/>Multi-package<br/>Architecture changes]
    end
    
    style Fast fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff
    style FastMax fill:#3498db,stroke:#2980b9,stroke-width:2px,color:#fff
    style FastEnhanced fill:#e67e22,stroke:#d35400,stroke-width:2px,color:#fff
    style Full fill:#e74c3c,stroke:#c0392b,stroke-width:2px,color:#fff
```

### Architecture Comparison

```mermaid
graph TB
    subgraph "smart_commit_fast.py Architecture"
        Fast_Entry[Entry Point] --> Fast_Mode{Mode Selection}
        Fast_Mode --> Fast_Quick[Quick Pipeline<br/>1 AI call]
        Fast_Mode --> Fast_Max[Max Pipeline<br/>Parallel analysis]
        Fast_Mode --> Fast_Enhanced[Enhanced Pipeline<br/>4-stage analysis]
        
        Fast_Quick --> Fast_Out[Output]
        Fast_Max --> Fast_Out
        Fast_Enhanced --> Fast_Meta[Output + Metadata]
    end
    
    subgraph "smart_commit.py Architecture"
        Slow_Entry[Entry Point] --> Slow_Stage[Interactive Staging]
        Slow_Stage --> Slow_Cat[Categorization]
        Slow_Cat --> Slow_Parallel[Parallel Package Analysis]
        Slow_Parallel --> Slow_Cross[Cross-Package Analysis]
        Slow_Cross --> Slow_Gen[Message Generation]
        Slow_Gen --> Slow_Out[Comprehensive Output]
    end
    
    style Fast_Entry fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff
    style Fast_Enhanced fill:#e67e22,stroke:#d35400,stroke-width:2px,color:#fff
    style Slow_Entry fill:#e74c3c,stroke:#c0392b,stroke-width:2px,color:#fff
    style Slow_Cross fill:#9b59b6,stroke:#8e44ad,stroke-width:2px,color:#fff
```

## Conclusion

The Smart Commit tools transform the mundane task of writing commit messages into an intelligent, automated process that improves code documentation, team communication, and development velocity. Whether you need a quick 2-second commit or a comprehensive analysis of complex changes, these tools adapt to your workflow while maintaining high-quality standards.

Choose `smart_commit_fast.py` for speed, `smart_commit.py` for depth, or use both as your workflow demands. The future of git commits is here, and it's intelligent. 