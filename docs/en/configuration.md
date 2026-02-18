# Configuration

hachimoku provides a hierarchical TOML-based configuration system.
It reads configuration from five sources and resolves values based on priority.

```{contents}
:depth: 2
:local:
```

## Configuration Hierarchy

The system consists of five layers. Higher-priority sources override lower ones.

1. CLI options (highest priority)
2. `.hachimoku/config.toml` (project settings)
3. `[tool.hachimoku]` section in `pyproject.toml`
4. `~/.config/hachimoku/config.toml` (user global settings)
5. Default values (lowest priority)

Project settings (`.hachimoku/config.toml`) and `pyproject.toml` are searched upward from the current directory toward the root.

### Merge Rules

- Scalar values: Higher-priority layer values override
- `agents` section: Fields are merged per agent name
- `selector` section: Fields are merged individually

## Configuration File Format

### .hachimoku/config.toml

```{literalinclude} ../_examples/config.toml
:language: toml
:caption: .hachimoku/config.toml
```

### pyproject.toml

```{code-block} toml
[tool.hachimoku]
model = "anthropic:claude-opus-4-6"
timeout = 300
parallel = false
```

## Configuration Items

### HachimokuConfig

Complete list of all configuration items.

| Item | Type | Default | Constraint | Description |
|------|------|---------|------------|-------------|
| `model` | `str` | `"claudecode:claude-opus-4-6"` | Non-empty, prefix required | LLM model name (specify provider with `claudecode:` or `anthropic:` prefix) |
| `timeout` | `int` | `600` | Positive value | Agent timeout (seconds) |
| `max_turns` | `int` | `20` | Positive value | Maximum number of agent turns |
| `parallel` | `bool` | `true` | - | Enable parallel execution |
| `base_branch` | `str` | `"main"` | Non-empty | Base branch for diff mode |
| `output_format` | `str` | `"markdown"` | `"markdown"` or `"json"` | Output format |
| `save_reviews` | `bool` | `true` | - | Save review history as JSONL (see below) |
| `show_cost` | `bool` | `false` | - | Display cost information |
| `max_files_per_review` | `int` | `100` | Positive value | Maximum number of files for file mode |
| `selector` | `SelectorConfig` | See below | - | Selector agent settings |
| `aggregation` | `AggregationConfig` | See below | - | Aggregation agent settings |
| `agents` | `dict[str, AgentConfig]` | `{}` | - | Per-agent settings |

### SelectorConfig

Configuration overrides for the selector agent.
When `model`, `timeout`, or `max_turns` is `None`, the selector definition value is used; if that is also `None`, the global configuration value is used (3-layer resolution: config -> definition -> global).

| Item | Type | Default | Constraint | Description |
|------|------|---------|------------|-------------|
| `model` | `str \| None` | `None` | Non-empty | Model name override (specify provider with prefix) |
| `timeout` | `int \| None` | `None` | Positive value | Timeout (seconds) |
| `max_turns` | `int \| None` | `None` | Positive value | Maximum turns |
| `referenced_content_max_chars` | `int` | `5000` | Positive value | Maximum characters per referenced_content item. Truncated content gets a truncation marker appended |

### AggregationConfig

Aggregation agent settings. Same pattern as SelectorConfig, plus `enabled` to toggle aggregation on/off.
When `model`, `timeout`, or `max_turns` is `None`, the aggregation agent definition value is used; if that is also `None`, the global configuration value is used (3-layer resolution: config -> definition -> global).

| Item | Type | Default | Constraint | Description |
|------|------|---------|------------|-------------|
| `enabled` | `bool` | `true` | - | Enable/disable aggregation |
| `model` | `str \| None` | `None` | Non-empty | Model name override (specify provider with prefix) |
| `timeout` | `int \| None` | `None` | Positive value | Timeout (seconds) |
| `max_turns` | `int \| None` | `None` | Positive value | Maximum turns |

```{code-block} toml
[aggregation]
enabled = true
model = "claudecode:claude-opus-4-6"
timeout = 300
max_turns = 10
```

### AgentConfig

Per-agent individual settings.
When `model`, `timeout`, or `max_turns` is `None`, the global configuration value is used.

| Item | Type | Default | Constraint | Description |
|------|------|---------|------------|-------------|
| `enabled` | `bool` | `true` | - | Enable/disable the agent |
| `model` | `str \| None` | `None` | Non-empty | Model name (specify provider with prefix) |
| `timeout` | `int \| None` | `None` | Positive value | Timeout (seconds) |
| `max_turns` | `int \| None` | `None` | Positive value | Maximum turns |

Agent names are specified in `[agents.<name>]` format and must match the `^[a-z0-9-]+$` pattern.

## Review History Accumulation

When `save_reviews = true` (default), review results are automatically accumulated in JSONL format in the `.hachimoku/reviews/` directory after review completion.

### Accumulation Files

Accumulation files are separated by review mode.

| Review Mode | Accumulation File | Example |
|-------------|-------------------|---------|
| diff | `diff.jsonl` | `.hachimoku/reviews/diff.jsonl` |
| PR | `pr-{number}.jsonl` | `.hachimoku/reviews/pr-123.jsonl` |
| file | `files.jsonl` | `.hachimoku/reviews/files.jsonl` |

Each line is an independent JSON object. New reviews are appended to existing files.

### Disabling

```{code-block} toml
save_reviews = false
```

Can also be controlled via CLI options.

```{code-block} bash
8moku review --no-save-reviews
```

## Project Root Discovery

`find_project_root()` searches upward from the specified directory for a `.hachimoku/` directory.
Returns `None` if not found.

```{code-block} python
from pathlib import Path
from hachimoku.config import find_project_root

root = find_project_root(Path.cwd())
if root is not None:
    print(f"Project root: {root}")
```

## Configuration Resolution

`resolve_config()` merges the five configuration layers and builds the final configuration object.
If no configuration files exist, it builds with default values only.

```{code-block} python
from pathlib import Path
from hachimoku.config import resolve_config

# Default configuration (searches from current directory)
config = resolve_config()

# Specify search start directory and CLI overrides
config = resolve_config(
    start_dir=Path("/path/to/project"),
    cli_overrides={"timeout": 600, "parallel": False},
)

print(config.model)      # "claudecode:claude-opus-4-6"
print(config.timeout)    # 600 (CLI override applied)
print(config.parallel)   # False (CLI override applied)
```
