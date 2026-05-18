# hachimoku

**English** | [日本語](README.ja.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)

hachimoku is a Claude Code plugin for multi-agent code review.
A review runs **inside your interactive Claude Code session**, dispatching specialized review subagents in parallel and aggregating their findings into a single report.

Because reviews run in your existing Claude Code session, they are covered by your interactive subscription rather than the metered programmatic-usage billing that `claude -p` incurs from 2026-06-15.

## Key Features

- Runs as a Claude Code plugin — no separate review tool to install or run
- Built-in review subagents covering code quality, security, dependencies, type design, test coverage, comments, simplification, and more
- Add project-specific custom review perspectives via TOML agent definitions — no code changes required
- Parallel dispatch in ordered phases (early → main → final)
- Deterministic selection and aggregation: agent selection and report aggregation run as plain CLI steps that consume no LLM budget
- Review subagents are restricted to read-only `git`/`gh` access by a bundled guard hook
- Review results accumulate in JSONL format under `.hachimoku/reviews/` for review history analysis

## Prerequisites

Both must be installed and available on `PATH`:

- [`uv`](https://docs.astral.sh/uv/) — runs the hachimoku CLI ephemerally via `uvx`
- [`jq`](https://jqlang.github.io/jq/) — required by the bundled read-only git guard hook

## Quick Start

### 1. Install the plugin

For local / development use, point Claude Code at the bundled plugin directory:

```bash
claude --plugin-dir ./plugin
```

Marketplace distribution is to be published.

### 2. Set up the project (once)

In your project, run the setup skill inside Claude Code:

```
/hachimoku:setup
```

This generates the review subagents into `.claude/agents/` along with `.claude/manifest.json`. Re-run it only after upgrading the plugin.

### 3. Run a review

```
/hachimoku:review
```

The review skill orchestrates the review: it selects applicable subagents, dispatches them in parallel phases, aggregates their findings, and presents a structured report. Pass a PR number or file paths as arguments, or leave it empty to review the current branch diff.

## Architecture

hachimoku has two parts:

- **Claude Code plugin** (user-facing) — the `/hachimoku:setup` and `/hachimoku:review` skills. This is the review interface.
- **Thin CLI** (`hachimoku`, alias `8moku`) — a supporting developer utility with deterministic, non-LLM subcommands (`init`, `agents`, `build`, `select`, `aggregate`). The plugin skills invoke it ephemerally via `uvx`.

You do not need to install the CLI to run reviews. Installing it locally with `uv tool install` is optional — useful only for developers who want to run `build` / `select` / `aggregate` by hand. See [Installation](docs/en/installation.md).

## Agent Definitions

Review subagents are generated from TOML agent definitions under `.hachimoku/agents/`. Each definition declares its review perspective, model, applicability rules, and output schema. You can add project-specific custom agents by dropping a new TOML file into that directory and re-running `/hachimoku:setup`.

See [Agent Definitions](docs/en/agents.md) for details.

## Configuration

Supports TOML-based hierarchical configuration (in priority order):

1. `.hachimoku/config.toml`
2. `pyproject.toml [tool.hachimoku]`
3. `~/.config/hachimoku/config.toml`
4. Default values

See [Configuration](docs/en/configuration.md) for details.

## Documentation

📖 **Online**: [English](https://drillan.github.io/hachimoku/en/) | [Japanese](https://drillan.github.io/hachimoku/ja/)

Source files are in [docs/](docs/).

- [Installation](docs/en/installation.md)
- [CLI Reference](docs/en/cli.md)
- [Agent Definitions](docs/en/agents.md)
- [Configuration](docs/en/configuration.md)
- [Domain Models](docs/en/models.md)
- [Review Context Guide](docs/en/review-context.md)

## License

[MIT License](LICENSE)
