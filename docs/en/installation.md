# Installation

```{contents}
:depth: 2
:local:
```

## Prerequisites

- [Claude Code](https://docs.claude.com/en/docs/claude-code) — hachimoku runs as a plugin inside it
- [`uv`](https://docs.astral.sh/uv/) — runs the hachimoku CLI ephemerally via `uvx`; must be on `PATH`
- [`jq`](https://jqlang.github.io/jq/) — required by the bundled read-only git guard hook; must be on `PATH`
- Git (required for diff mode and PR mode reviews)

Verify the prerequisites:

```bash
uv --version
jq --version
```

## Install the Claude Code Plugin

The plugin is the primary, user-facing way to use hachimoku. Reviews run from within Claude Code via the `/hachimoku:setup` and `/hachimoku:review` skills.

### Local / development use

Clone the repository and point Claude Code at the bundled plugin directory:

```bash
git clone https://github.com/drillan/hachimoku.git
cd hachimoku
claude --plugin-dir ./plugin
```

### Via marketplace

Marketplace distribution is to be published.

## Project Setup

In each project you want to review, initialize hachimoku and generate the review subagents.

### 1. Initialize the project

```bash
cd your-project
uvx --from git+https://github.com/drillan/hachimoku@v0.1.0 hachimoku init
```

The following files are created in the `.hachimoku/` directory:

- `config.toml` — Configuration file (template with all options commented out)
- `agents/*.toml` — Copies of built-in agent definitions
- `reviews/` — Directory for accumulating review result JSONL files
- Automatic addition of `/.hachimoku/` entry to `.gitignore` (Git repositories only; only if not already present)

See [Configuration](configuration.md) for configuration details.

### 2. Generate the review subagents

Inside Claude Code, run the setup skill:

```
/hachimoku:setup
```

This generates the review subagents into `.claude/agents/` along with `.claude/manifest.json`. You only need to re-run it after upgrading the plugin or hachimoku itself.

## Optional: Install the CLI Locally (for developers)

You do **not** need to install the CLI to run reviews — the plugin skills invoke it ephemerally via `uvx`. Installing it locally is only useful for developers who want to run `hachimoku build` / `select` / `aggregate` by hand.

### Global installation (uv tool install)

```bash
uv tool install git+https://github.com/drillan/hachimoku.git
```

This makes the `hachimoku` and `8moku` commands available globally. To upgrade:

```bash
uv tool install --reinstall git+https://github.com/drillan/hachimoku.git
```

```{note}
`uv tool install` does nothing if the package is already installed.
The `--reinstall` flag forces reinstallation and implies `--refresh` (cache
invalidation), ensuring the latest code is fetched from the remote repository.
```

### Install from source

Clone the repository and synchronize dependencies:

```bash
git clone https://github.com/drillan/hachimoku.git
cd hachimoku
uv sync
```

To include development tools (tests, linter, type checker):

```bash
uv sync --group dev
```

## Verification

Confirm the plugin loads in Claude Code by listing its skills — `/hachimoku:setup` and `/hachimoku:review` should be available. After running `/hachimoku:setup` in a project, confirm that `.claude/agents/` contains the generated review subagent `.md` files and that `.claude/manifest.json` exists.

If you installed the CLI locally, you can also verify it directly:

```bash
hachimoku --help
hachimoku agents
```
