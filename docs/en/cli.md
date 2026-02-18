# CLI Reference

hachimoku provides two command names: `8moku` and `hachimoku`. Both execute the same functionality.

```{contents}
:depth: 2
:local:
```

## Review Command (Default)

Running with no arguments or with arguments performs a code review.

```bash
8moku [OPTIONS] [ARGS]
```

The input mode is automatically determined by the type of arguments:

No arguments
: diff mode. Reviews the changes on the current branch. Must be run inside a Git repository.

Single positive integer
: PR mode. Reviews the diff and metadata of the specified GitHub PR. Must be run inside a Git repository.

File path(s) (one or more)
: file mode. Reviews entire specified files. Supports glob patterns (`*`, `?`, `[`) and directory specifications. Works outside of Git repositories.

```bash
# diff mode
8moku

# PR mode
8moku 42

# file mode
8moku src/main.py
8moku src/**/*.py
8moku src/
```

### Review Options

Options for the review command. These override configuration file values.

| Option | Type | Description |
|--------|------|-------------|
| `--model TEXT` | str | LLM model name |
| `--timeout INTEGER` | int (min: 1) | Timeout in seconds |
| `--max-turns INTEGER` | int (min: 1) | Maximum number of agent turns |
| `--parallel / --no-parallel` | bool | Enable/disable parallel execution |
| `--base-branch TEXT` | str | Base branch for diff mode |
| `--format FORMAT` | OutputFormat | Output format (`markdown` / `json`, default: `markdown`) |
| `--save-reviews / --no-save-reviews` | bool | Save review results |
| `--show-cost / --no-show-cost` | bool | Display cost information |
| `--max-files INTEGER` | int (min: 1) | Maximum number of files to review |
| `--issue INTEGER` | int (min: 1) | GitHub Issue number for context |
| `--no-confirm` | bool | Skip confirmation prompts |
| `--version` | - | Display version number and exit |
| `--help` | - | Display help |

See [Configuration](configuration.md) for default values in the configuration file.

### File Mode Behavior

In file mode, the following processing is performed:

- Expansion of glob patterns (`*`, `?`, `[`)
- Recursive file collection for directory specifications
- Symlink loop detection
- Results are a sorted, deduplicated list of absolute paths

When the number of files exceeds `max_files_per_review` (default: 100), a confirmation prompt is displayed. Use the `--no-confirm` option to skip the confirmation.

## init

Creates default configuration files and agent definitions in the `.hachimoku/` directory.

```bash
8moku init [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--force` | Overwrite existing files with defaults |
| `--help` | Display help |

```bash
# Initial setup
8moku init

# Reset configuration
8moku init --force
```

Created files:

- `.hachimoku/config.toml` - Configuration file (template with all options commented out)
- `.hachimoku/agents/*.toml` - Copies of built-in agent definitions
- `.hachimoku/reviews/` - JSONL accumulation directory for review results
- Automatic addition of `/.hachimoku/` entry to `.gitignore` (only if not already present)

## agents

Displays a list or details of agent definitions.

```bash
8moku agents [NAME]
```

| Argument | Description |
|----------|-------------|
| `NAME` | Agent name (omit for list view) |

```bash
# List view
8moku agents

# Detail view
8moku agents code-reviewer
```

The list view displays NAME, MODEL, PHASE, and SCHEMA columns. Project-specific custom agents are marked with `[custom]`.

## config (Planned)

The configuration management subcommand is not yet implemented. Please edit `.hachimoku/config.toml` directly.

## Output Streams

hachimoku separates review reports from progress information in its output:

stdout
: Review reports only. Supports pipes and redirects.

stderr
: Progress information, logs, error messages, and confirmation prompts.

```bash
# Save report to file
8moku > review.md

# Pipe report to another command
8moku --format json | jq '.agents'
```

## Exit Codes

| Code | Name | Meaning |
|------|------|---------|
| 0 | SUCCESS | Normal completion. No issues found, or user confirmed an action |
| 1 | CRITICAL | Critical-level issues detected |
| 2 | IMPORTANT | Important-level issues detected (no Critical) |
| 3 | EXECUTION_ERROR | Runtime error (network, timeout, configuration parsing, etc.) |
| 4 | INPUT_ERROR | Input error (invalid arguments, Git requirements not met, file not found, permissions, configuration file issues) |

Exit codes can be used for conditional branching in scripts and CI/CD pipelines:

```bash
8moku
case $? in
  0) echo "No issues found" ;;
  1) echo "Critical issues found" ;;
  2) echo "Important issues found" ;;
  3) echo "Execution error" ;;
  4) echo "Input error" ;;
esac
```
