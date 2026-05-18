# CLI Reference

The `hachimoku` CLI (alias `8moku`) is a **supporting developer utility**, not the review interface. Reviews are run from within Claude Code via the `/hachimoku:setup` and `/hachimoku:review` skills; see [Installation](installation.md).

The CLI provides only deterministic, non-LLM subcommands. The plugin skills invoke it ephemerally via `uvx`, so you normally never run it by hand. It is documented here for developers and for understanding what the plugin does under the hood.

```{contents}
:depth: 2
:local:
```

## Overview

```bash
hachimoku [OPTIONS] COMMAND [ARGS]...
```

| Command | Description |
|---------|-------------|
| `init` | Initialize the `.hachimoku/` directory with default configuration and agent definitions |
| `agents` | List or inspect agent definitions |
| `build` | Build Claude Code subagents and `manifest.json` from TOML agent definitions |
| `select` | Select review agents for a target and emit a dispatch plan (JSON) |
| `aggregate` | Aggregate subagent findings into a review report |

Global options:

| Option | Description |
|--------|-------------|
| `--version` | Display the version number and exit |
| `--help` | Display help |

`select` and `aggregate` are invoked internally by the `/hachimoku:review` skill — `select` computes the dispatch plan and `aggregate` produces the final report. You do not normally run them yourself.

## init

Creates default configuration files and agent definitions in the `.hachimoku/` directory. Works both inside and outside Git repositories. Inside a Git repository, it also adds an entry to `.gitignore`.

```bash
hachimoku init [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--force` | Overwrite existing files with defaults |
| `--upgrade` | Update built-in agent definitions using hash comparison |
| `--help` | Display help |

```bash
# Initial setup
hachimoku init

# Reset all files to defaults (including config.toml)
hachimoku init --force

# Update agent definitions after a version upgrade (skip customized files)
hachimoku init --upgrade

# Force update all agent definitions including customized ones (config.toml preserved)
hachimoku init --upgrade --force
```

### Flag behavior scope

| Target | `init` | `--force` | `--upgrade` | `--upgrade --force` |
|--------|--------|-----------|-------------|---------------------|
| `config.toml` | Create | Overwrite | Not affected | Not affected |
| `agents/*.toml` | Create | Overwrite | Hash-based update | Force overwrite |
| `reviews/` | Create | Create | Not affected | Not affected |
| `.gitignore` | Add entry | Add entry | Not affected | Not affected |

### upgrade hash comparison

`--upgrade` compares the SHA-256 hash of local files against built-in definitions and determines the action:

- **File does not exist**: Add new file (`Added`)
- **Hash matches**: Already up to date (`Skipped (up to date)`)
- **Hash differs**: Skip as customized (`Skipped (customized)`)
- **Hash differs + `--force`**: Force overwrite (`Updated`)

Created files (`init` / `--force`):

- `.hachimoku/config.toml` — Configuration file (template with all options commented out)
- `.hachimoku/agents/*.toml` — Copies of built-in agent definitions
- `.hachimoku/reviews/` — JSONL accumulation directory for review results
- Automatic addition of `/.hachimoku/` entry to `.gitignore` (Git repositories only; only if not already present)

## agents

Displays a list or details of agent definitions.

```bash
hachimoku agents [NAME]
```

| Argument | Description |
|----------|-------------|
| `NAME` | Agent name for detailed info (omit for list view) |

```bash
# List view
hachimoku agents

# Detail view
hachimoku agents code-reviewer
```

The list view displays NAME, MODEL, PHASE, and SCHEMA columns. Project-specific custom agents are marked with `[custom]`.

## build

Builds Claude Code review subagents and a `manifest.json` from the TOML agent definitions. Each `*.toml` agent definition is converted into a subagent `.md` file (with frontmatter, tool permissions, a read-only git guard hook, and an Output Contract) plus one entry in `manifest.json`.

```bash
hachimoku build [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--output PATH` | `.hachimoku/build` | Output directory for generated subagents |
| `--hook-script TEXT` | `${CLAUDE_PLUGIN_ROOT}/scripts/block-git-mutations.sh` | Absolute path to the read-only git guard hook script |
| `--help` | — | Display help |

The `/hachimoku:setup` skill runs `build` with `--output .claude` so that the generated subagents land under `.claude/agents/` and `manifest.json` under `.claude/`.

```bash
# Build into the default directory
hachimoku build

# Build into .claude (as the setup skill does)
hachimoku build --output .claude --hook-script /abs/path/to/block-git-mutations.sh
```

## select

Evaluates the changeset against the agent manifest and emits a dispatch plan as JSON. Invoked internally by `/hachimoku:review`.

```bash
hachimoku select [OPTIONS] [ARGS]...
```

| Argument | Description |
|----------|-------------|
| `ARGS` | PR number or file paths (omit for diff mode) |

| Option | Description |
|--------|-------------|
| `--manifest PATH` | Path to the manifest JSON file (**required**) |
| `--commit TEXT` | Commit ref or range for commit mode (`SHA` or `SHA1..SHA2`) |
| `--base-branch TEXT` | Base branch for diff mode (default: `main`) |
| `--help` | Display help |

The target is determined by the arguments: no arguments selects diff mode, a single integer selects PR mode, and file paths select file mode. The JSON output contains a `run_dir` (a temporary directory consumed by `aggregate`) and `phases` (`early` / `main` / `final`, each a list of agent names).

## aggregate

Reads the subagent findings JSON files from a run directory, validates and deduplicates them, classifies severity, and prints a Markdown review report. It also appends a record to the JSONL review history under `.hachimoku/reviews/`. Invoked internally by `/hachimoku:review`.

```bash
hachimoku aggregate [OPTIONS] [ARGS]...
```

| Argument | Description |
|----------|-------------|
| `ARGS` | PR number or file paths (omit for diff mode) |

| Option | Description |
|--------|-------------|
| `--run-dir PATH` | Run directory created by `select` (**required**) |
| `--manifest PATH` | Path to the manifest JSON file (**required**) |
| `--commit TEXT` | Commit ref or range for commit mode (`SHA` or `SHA1..SHA2`) |
| `--base-branch TEXT` | Base branch for diff mode (default: `main`) |
| `--help` | Display help |

`aggregate` prints the Markdown report to stdout and exits with a severity-based exit code (see [Exit Codes](#exit-codes)). If some subagents failed, the run is not failed wholesale: the report includes a failed-agents section and aggregation continues with the successful findings.

## Output Streams

The CLI separates report output from progress information:

stdout
: The review report (`aggregate`) or the dispatch plan JSON (`select`). Supports pipes and redirects.

stderr
: Progress information, logs, and error messages.

```bash
# Pipe the select dispatch plan to jq
hachimoku select --manifest .claude/manifest.json | jq '.phases'
```

(exit-codes)=

## Exit Codes

| Code | Name | Meaning |
|------|------|---------|
| 0 | SUCCESS | Normal completion |
| 1 | CRITICAL | Critical-level issues detected |
| 2 | IMPORTANT | Important-level issues detected (no Critical) |
| 3 | EXECUTION_ERROR | Runtime error (configuration parsing, Git operations, etc.) |
| 4 | INPUT_ERROR | Input error (invalid arguments, Git requirements not met, file not found, configuration file issues) |

Codes 1 (CRITICAL) and 2 (IMPORTANT) are produced only by `aggregate`, based on the severity of the aggregated findings. The deterministic subcommands `init`, `agents`, `build`, and `select` return only 0 on success, 3 on a runtime error, or 4 on an input error.
