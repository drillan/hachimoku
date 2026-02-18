# hachimoku

**English** | [日本語](README.ja.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)

hachimoku (8moku) is a CLI tool that performs code reviews using multiple specialized agents.
Agent definitions are managed via TOML files, allowing you to add and customize review perspectives without any code changes.

## Key Features

- 3 review modes: diff (branch diff), PR (GitHub PR), file (specified files)
- Built-in agents: code quality, silent failures, test coverage, type safety, comments, simplification
- Add custom agents via TOML-based agent definitions
- Choose between sequential and parallel execution
- LLM-based result aggregation: deduplicates and merges findings from multiple agents, generating recommended actions
- Cost efficiency: selector and aggregation use lightweight models, reviews use high-performance models to maintain accuracy
- Flexible model configuration: resolved in config > definition > global priority order, can always revert to Opus 4.6
- Markdown / JSON output support (default: Markdown)
- Automatic review result accumulation in JSONL format for review history analysis

## Installation

Install globally with `uv tool install`:

```bash
uv tool install git+https://github.com/drillan/hachimoku.git
```

For developers (setup from source):

```bash
git clone https://github.com/drillan/hachimoku.git
cd hachimoku
uv sync
```

See [Installation](docs/en/installation.md) for details.

## Upgrade

```bash
uv tool install --reinstall git+https://github.com/drillan/hachimoku.git
```

> **Note**: `uv tool install` does nothing if already installed.
> The `--reinstall` flag fetches the latest code from the remote repository and reinstalls.

## Quick Start

### 1. Initialize the Project

```bash
8moku init
```

Default configuration files and agent definitions are created in the `.hachimoku/` directory.

### 2. Run a Code Review

```bash
# diff mode: review changes in the current branch
8moku

# PR mode: review a GitHub PR
8moku 42

# file mode: review specified files
8moku src/main.py tests/test_main.py
```

### 3. View Agents

```bash
# List agents
8moku agents

# Agent details
8moku agents code-reviewer
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `8moku [OPTIONS] [ARGS]` | Run a code review (default) |
| `8moku init [--force]` | Initialize the `.hachimoku/` directory |
| `8moku agents [NAME]` | List or show details of agent definitions |

Main review options:

| Option | Description |
|--------|-------------|
| `--model TEXT` | LLM model name (with prefix: `claudecode:` or `anthropic:`) |
| `--timeout INTEGER` | Timeout in seconds |
| `--parallel / --no-parallel` | Enable/disable parallel execution |
| `--format FORMAT` | Output format (`markdown` / `json`, default: `markdown`) |
| `--base-branch TEXT` | Base branch for diff mode |
| `--issue INTEGER` | GitHub Issue number for context |
| `--no-confirm` | Skip confirmation prompts |

## Model Prefixes

hachimoku determines the provider based on the model name prefix:

| Prefix | Description | API Key | Example |
|--------|-------------|---------|---------|
| `claudecode:` | Claude Code built-in model (default) | Not required | `claudecode:claude-opus-4-6` |
| `anthropic:` | Direct Anthropic API call | `ANTHROPIC_API_KEY` required | `anthropic:claude-opus-4-6` |

```bash
# Using the Anthropic API
export ANTHROPIC_API_KEY="your-api-key"
8moku --model "anthropic:claude-opus-4-6"
```

## Configuration

Supports TOML-based hierarchical configuration (in priority order):

1. CLI options
2. `.hachimoku/config.toml`
3. `pyproject.toml [tool.hachimoku]`
4. `~/.config/hachimoku/config.toml`
5. Default values

## Documentation

See [docs/](docs/) for detailed documentation. Available in [English](docs/en/) and [Japanese](docs/ja/).

- [Installation](docs/en/installation.md)
- [CLI Reference](docs/en/cli.md)
- [Agent Definitions](docs/en/agents.md)
- [Configuration](docs/en/configuration.md)
- [Domain Models](docs/en/models.md)
- [Review Context Guide](docs/en/review-context.md)

## License

[MIT License](LICENSE)
