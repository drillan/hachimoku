# hachimoku Claude Code Plugin

A Claude Code plugin that integrates [hachimoku](https://github.com/drillan/hachimoku) — a multi-agent code review orchestrator — directly into your workflow.

## What it does

The plugin provides two skills:

- `/hachimoku:setup` — Generates hachimoku review subagents and a manifest into `.claude/` for the current project.
- `/hachimoku:review` — Dispatches the generated subagents to perform a multi-agent code review. Requires `/hachimoku:setup` to have been run first.

Subagents are generated into `.claude/agents/` (rather than bundled) so that their `hooks` frontmatter is honoured by Claude Code. The bundled `block-git-mutations.sh` guard script is injected into each subagent's hooks at build time to prevent any review agent from mutating the git state.

## Prerequisites

Both tools must be installed and available on `PATH` before running `/hachimoku:setup`:

- [`uv`](https://docs.astral.sh/uv/) — used to run `hachimoku build` ephemerally via `uvx`
- [`jq`](https://jqlang.github.io/jq/) — required by the bundled `block-git-mutations.sh` guard script

## Installation

### Development / local use

```bash
claude --plugin-dir ./plugin
```

### Via marketplace

*(To be published)*

## Usage

### Step 1 — Set up (once per project, or after upgrading)

```
/hachimoku:setup
```

This runs `hachimoku build` via `uvx`, writing review subagent `.md` files and `manifest.json` into `.claude/`. You only need to re-run this after upgrading the plugin or hachimoku itself.

### Step 2 — Review

```
/hachimoku:review
```

Dispatches the generated subagents to review the current changeset and produces a structured report. `/hachimoku:setup` must have been run for this project beforehand so that the subagents exist under `.claude/agents/`.

## hachimoku release pinning

The `setup` and `review` skills install hachimoku ephemerally via `uvx` from a
pinned release tag:

```
git+https://github.com/drillan/hachimoku@v0.1.0
```

Plugin version `0.1.0` is pinned to the matching hachimoku release tag
`v0.1.0`. When the plugin is upgraded, this tag is bumped in lockstep.

## License

MIT
