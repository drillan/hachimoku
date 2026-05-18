# hachimoku

hachimoku is a Claude Code plugin for multi-agent code review.
A review runs inside your interactive Claude Code session, dispatching specialized review subagents in parallel and aggregating their findings into a single report.

Because reviews run in your existing Claude Code session, they are covered by your interactive subscription rather than the metered programmatic-usage billing that `claude -p` incurs from 2026-06-15.

## Architecture

hachimoku has two parts:

- **Claude Code plugin** (user-facing) — the `/hachimoku:setup` and `/hachimoku:review` skills. This is the review interface: it orchestrates a review by selecting applicable subagents, dispatching them in parallel phases, aggregating their findings, and presenting a report.
- **Thin CLI** (`hachimoku`, alias `8moku`) — a supporting developer utility with deterministic, non-LLM subcommands (`init`, `agents`, `build`, `select`, `aggregate`). The plugin skills invoke it ephemerally via `uvx`; you do not need to install it to run reviews.

See [Installation](installation.md) to get started, and [CLI Reference](cli.md) for the developer CLI.

## Key Features

### Plugin Workflow

A review is driven entirely from within Claude Code by two skills.

- `/hachimoku:setup` — Run once per project. Generates the review subagents into `.claude/agents/` and `.claude/manifest.json`.
- `/hachimoku:review` — Orchestrates a review. Accepts a PR number, file paths, or no argument (current branch diff).

### Agents

Multiple built-in review subagents are provided out of the box, covering perspectives such as code quality, security, dependency auditing, type design, test coverage, comment accuracy, and code simplification.

Agents are defined in TOML format under `.hachimoku/agents/`, and you can add project-specific custom agents.
See [Agent Definitions](agents.md) for details.

### Deterministic Selection and Aggregation

Agent selection (`hachimoku select`) and report aggregation (`hachimoku aggregate`) run as deterministic CLI steps that consume no LLM budget. Only the review subagents themselves use the model, within your Claude Code session.

### Security

Review subagents are generated with a `PreToolUse` hook (`block-git-mutations.sh`) that restricts them to read-only `git`/`gh` access, so a review cannot mutate repository state.

### Output and History

- Review reports are produced as Markdown and presented in your Claude Code session
- Review results are automatically accumulated in JSONL format under `.hachimoku/reviews/`
- The thin CLI separates report output (stdout) from progress and logs (stderr)

### Configuration

Supports a hierarchical TOML-based configuration system.

- `.hachimoku/config.toml` > `pyproject.toml [tool.hachimoku]` > `~/.config/hachimoku/config.toml` > defaults

See [Configuration](configuration.md) for details.

### Domain Models

Review results are managed with type-safe domain models.
Provides Severity (4-level severity), ReviewIssue (unified issue representation), AgentResult (discriminated union of success/error), ReviewReport (aggregated report), ToolCategory (tool categories), and ReviewHistoryRecord (review history records).
See [Domain Models](models.md) for details.

```{toctree}
:maxdepth: 2
:caption: Contents

installation
cli
agents
configuration
models
review-context
```
