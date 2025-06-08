# Contributor Analysis Tool

The contributor analysis tool analyzes contributors across GitHub organizations and builds detailed performance profiles using AI.

## Features

- **Multi-Organization Analysis**: Analyze contributors across multiple GitHub organizations
- **AI-Powered Insights**: Uses Gemini AI with model rotation for detailed contributor analysis
- **Parallel Processing**: Leverages async operations for high performance
- **Comprehensive Profiles**: Generates detailed markdown profiles for each contributor
- **Rate Limiting**: Respects GitHub API rate limits
- **Real-time Progress**: Shows live progress updates during analysis

## Prerequisites

1. **GitHub CLI**: Install and authenticate with GitHub CLI
   ```bash
   gh auth login
   ```

2. **Gemini API Key**: Set your Gemini API key
   ```bash
   export GEMINI_API_KEY="your-api-key-here"
   ```

## Usage

### Basic Analysis

Analyze contributors from default organizations (pieces-app, open-runtime):

```bash
runtime_fdr_management_tools contributors
```

### Custom Organizations

Analyze specific organizations:

```bash
runtime_fdr_management_tools contributors --organizations pieces-app open-runtime my-org
```

### Specific Repositories

Analyze only specific repositories:

```bash
runtime_fdr_management_tools contributors --repositories pieces-os runtime-tools
```

### Time Period

Analyze contributions from a specific time period:

```bash
runtime_fdr_management_tools contributors --since 1year
runtime_fdr_management_tools contributors --since 3months
runtime_fdr_management_tools contributors --since 2024-01-01
```

### Performance Options

Adjust performance settings:

```bash
runtime_fdr_management_tools contributors --max-workers 8 --rate-limit 20
```

### Output Directory

Specify where to save profiles:

```bash
runtime_fdr_management_tools contributors --profiles-dir team-profiles
```

## Command Options

| Option | Description | Default |
|--------|-------------|---------|
| `--organizations`, `-o` | GitHub organizations to analyze | `pieces-app open-runtime` |
| `--repositories`, `-r` | Specific repositories to analyze | All in organizations |
| `--since` | Analyze contributions since this period | `6months` |
| `--from-scratch` | Start analysis from scratch | False |
| `--update` | Update existing profiles | True (default) |
| `--rate-limit` | API rate limit (requests per minute) | 10 |
| `--max-workers` | Maximum parallel workers | 4 |
| `--profiles-dir` | Directory for profiles | `profiles/` |
| `--dry-run` | Show analysis plan without execution | False |

## Analysis Process

The tool follows these phases:

1. **Discovery**: Finds all repositories in specified organizations
2. **Contributor Discovery**: Identifies all contributors across repositories  
3. **Data Collection**: Gathers contribution data (commits, PRs, etc.)
4. **AI Analysis**: Analyzes contributor patterns using multiple AI models
5. **Profile Generation**: Creates markdown profiles for each contributor

## Generated Profiles

Each contributor gets a comprehensive markdown profile including:

- **Overview**: Basic information and contact details
- **Contribution Summary**: Metrics and activity patterns
- **Active Repositories**: List of repositories they contribute to
- **Skill Assessment**: AI-powered technical skill evaluation
- **AI Analysis**: Detailed analysis of contribution patterns
- **Technical Metrics**: Performance indicators and statistics

## Model Rotation

The tool automatically rotates between multiple Gemini models for better performance:

- `gemini-2.0-flash`
- `gemini-2.5-flash-preview-04-17`
- `gemini-2.5-pro-preview-05-06` 
- `gemini-2.5-pro-preview-06-05`

## Examples

### Dry Run Analysis

See what would be analyzed without making API calls:

```bash
runtime_fdr_management_tools contributors --dry-run
```

### Full Team Analysis

Comprehensive analysis with increased performance:

```bash
runtime_fdr_management_tools contributors \
  --organizations pieces-app open-runtime \
  --since 1year \
  --max-workers 8 \
  --rate-limit 20 \
  --profiles-dir team-analysis-2024
```

### Quick Recent Analysis

Focus on recent contributions:

```bash
runtime_fdr_management_tools contributors \
  --since 3months \
  --from-scratch
```

## Output

The tool generates:

- Individual markdown profiles in the specified directory
- Real-time progress updates during analysis
- Summary table of top contributors
- Performance metrics and statistics

## Performance Notes

- Uses async operations for parallel processing
- Respects GitHub API rate limits
- Rotates between AI models to distribute load
- Caches AI responses to avoid duplicate analysis
- Processes contributors in batches for optimal performance

## Troubleshooting

### GitHub CLI Issues
```bash
gh auth status  # Check authentication
gh auth login   # Re-authenticate if needed
```

### API Rate Limits
```bash
# Reduce rate limit for free tier
runtime_fdr_management_tools contributors --rate-limit 5

# Check current rate limit status
gh api rate_limit
```

### Large Organizations
```bash
# Use more workers for large orgs
runtime_fdr_management_tools contributors --max-workers 8

# Analyze specific repositories to reduce scope
runtime_fdr_management_tools contributors --repositories core-repo main-app
``` 