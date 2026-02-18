# Agent Definitions

hachimoku's review agents are defined in TOML files.
It adopts a data-driven architecture that allows adding and customizing agents without code changes.
Six built-in agents are provided as standard, and project-specific custom agents can also be added.

```{contents}
:depth: 2
:local:
```

## Built-in Agents

The following six agents are included in the package.

| Agent Name | Description | Output Schema | Phase | Applicability |
|------------|-------------|---------------|-------|---------------|
| code-reviewer | Code quality and bug detection | scored_issues | main | Always applied |
| silent-failure-hunter | Detection of silent failures | severity_classified | main | content_patterns |
| pr-test-analyzer | Test coverage assessment | test_gap_assessment | main | file_patterns |
| type-design-analyzer | Practical analysis of type annotations and type safety | multi_dimensional_analysis | main | file_patterns + content_patterns |
| comment-analyzer | Comment accuracy analysis | category_classification | final | content_patterns |
| code-simplifier | Code simplification suggestions | improvement_suggestions | final | Always applied |

See [Output Schemas](output-schemas) for details on output schemas.

(selector-definition)=
## Selector Agent

The selector agent is a specialized agent that analyzes the review target and selects which review agents to run.
Like review agents, its configuration is managed via a TOML definition file.

### SelectorDefinition

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | Selector name (fixed as `"selector"`) |
| `description` | `str` | Yes | Description of the selector |
| `model` | `str` | Yes | LLM model name to use |
| `system_prompt` | `str` | Yes | Selector's system prompt |
| `allowed_tools` | `list[str]` | No | Allowed tool categories. Default: `git_read`, `gh_read`, `file_read` (3 categories, `web_fetch` not included) |

Unlike `AgentDefinition` for review agents, there are no `output_schema`, `phase`, or `applicability` fields.
The selector's output is always fixed to `SelectorOutput` (list of selected agent names with reasons).

### Model Resolution Priority

The selector agent's model is resolved in the following priority order:

1. `model` in `[selector]` configuration (see [Configuration](configuration.md))
2. `model` in the selector definition
3. Global `model` setting (default: `"claudecode:claude-opus-4-6"`)

### Built-in Selector Definition

A built-in `selector.toml` is included in the package.
Placing a custom `selector.toml` at `.hachimoku/agents/selector.toml` overrides the built-in.

```{literalinclude} ../../src/hachimoku/agents/_builtin/selector.toml
:language: toml
:caption: selector.toml (built-in)
```

### load_selector()

Loads the built-in selector definition. Uses a custom definition if one exists.

```{code-block} python
from hachimoku.agents import load_selector

definition = load_selector()
print(definition.name)  # "selector"
```

## TOML Definition File Format

Agent definitions are written as TOML files in the following format.

```{literalinclude} ../../src/hachimoku/agents/_builtin/code-reviewer.toml
:language: toml
:caption: code-reviewer.toml (built-in)
```

### Field List

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | Agent name. Only lowercase letters, digits, and hyphens (`^[a-z0-9-]+$`) |
| `description` | `str` | Yes | Agent description |
| `model` | `str` | Yes | LLM model name to use |
| `output_schema` | `str` | Yes | Schema name registered in [SCHEMA_REGISTRY](schema-registry) |
| `system_prompt` | `str` | Yes | Agent's system prompt |
| `allowed_tools` | `list[str]` | No | List of allowed tool categories. Default: empty |
| `phase` | `str` | No | Execution phase. Default: `"main"` |

`[applicability]` table:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `always` | `bool` | `false` | Always-applied flag |
| `file_patterns` | `list[str]` | `[]` | List of fnmatch patterns |
| `content_patterns` | `list[str]` | `[]` | List of regex patterns |

When the `[applicability]` table is omitted, `always = true` is applied as the default.

## Phase (Execution Phase)

Phases that control the execution order of agents.
Agents are executed in phase order, and within the same phase, in alphabetical order by name.

| Value | Execution Order | Description |
|-------|----------------|-------------|
| `early` | 0 | Pre-processing phase |
| `main` | 1 | Main review phase |
| `final` | 2 | Post-processing phase |

```{code-block} python
from hachimoku.agents import Phase, PHASE_ORDER

assert PHASE_ORDER[Phase.EARLY] < PHASE_ORDER[Phase.MAIN] < PHASE_ORDER[Phase.FINAL]
```

## ApplicabilityRule

Rules that determine whether an agent is applied to the review target.

Condition evaluation logic:

1. If `always = true`, always applied
2. If any `file_patterns` match the filename (basename), applied
3. If any `content_patterns` match the content, applied
4. If none of the above conditions are met, not applied

`file_patterns` and `content_patterns` have an OR relationship.

### Built-in Agent Applicability

| Agent | Condition | Patterns |
|-------|-----------|----------|
| code-reviewer | `always = true` | - |
| silent-failure-hunter | content_patterns | `try\s*:`, `except\s`, `catch\s*\(`, `\.catch\s*\(` |
| pr-test-analyzer | file_patterns | `test_*.py`, `*_test.py`, `*.test.ts`, `*.test.js`, `*.spec.ts`, `*.spec.js` |
| type-design-analyzer | file_patterns + content_patterns | Files: `*.py`, `*.ts`, `*.tsx` / Content: `class\s+\w+`, `interface\s+\w+`, `type\s+\w+\s*=` |
| comment-analyzer | content_patterns | `"""`, `'''`, `/\*\*`, `//\s*TODO`, `#\s*TODO` |
| code-simplifier | `always = true` | - |

(load-error)=
## LoadError

Holds error information that occurs when loading agent definition files.
Individual agent definitions that fail to load are skipped, and loading of other agents continues.

| Field | Type | Constraint |
|-------|------|------------|
| `source` | `str` | Non-empty. Error origin (file path, etc.) |
| `message` | `str` | Non-empty. Error message |

## LoadResult

The result of loading agent definitions.
Holds successfully loaded definitions and skipped error information separately.

| Field | Type | Constraint |
|-------|------|------------|
| `agents` | `tuple[AgentDefinition, ...]` | Successfully loaded agent definitions |
| `errors` | `tuple[LoadError, ...]` | Default empty tuple. Load error information |

## Loading Agents

### load_builtin_agents()

Loads the six built-in agent definitions included in the package.

```{code-block} python
from hachimoku.agents import load_builtin_agents

result = load_builtin_agents()
print(len(result.agents))  # 6
```

### load_custom_agents(custom_dir)

Loads `*.toml` files in the specified directory as custom agent definitions.
Returns an empty LoadResult if the directory does not exist.

```{code-block} python
from pathlib import Path
from hachimoku.agents import load_custom_agents

result = load_custom_agents(Path(".hachimoku/agents"))
```

### load_agents(custom_dir=None)

Loads and merges built-in and custom agent definitions.
When a custom definition has the same name as a built-in, the custom overrides the built-in.

```{code-block} python
from pathlib import Path
from hachimoku.agents import load_agents

# Built-in only
result = load_agents()

# Merged with custom
result = load_agents(custom_dir=Path(".hachimoku/agents"))

for agent in result.agents:
    print(f"{agent.name}: {agent.description}")

# Check load errors
for error in result.errors:
    print(f"Skipped {error.source}: {error.message}")
```

## Creating Custom Agents

Steps to add project-specific custom agents:

1. Create the `.hachimoku/agents/` directory
2. Place agent definition files in TOML format

```{literalinclude} ../_examples/security-checker.toml
:language: toml
:caption: .hachimoku/agents/security-checker.toml
```

Specify a schema name registered in [SCHEMA_REGISTRY](schema-registry) for `output_schema`.
Placing a file with the same name as a built-in overrides the built-in definition.
