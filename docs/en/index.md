# hachimoku

hachimoku (8moku) is a CLI tool that performs code reviews using multiple specialized agents.
Agent definitions are managed via TOML files, allowing you to add and customize review perspectives without code changes.

## Key Features

### Review Modes

Specify the review target using one of three modes.

- diff mode (`8moku`): Reviews the changes on the current branch
- PR mode (`8moku <PR number>`): Reviews the diff and metadata of a GitHub PR
- file mode (`8moku <file paths...>`): Reviews entire specified files. Works outside of Git repositories

### Agents

Six built-in agents are provided out of the box.

- code-reviewer: Code quality and bug detection
- silent-failure-hunter: Detection of silent failures
- pr-test-analyzer: Test coverage assessment
- type-design-analyzer: Practical analysis of type annotations and type safety
- comment-analyzer: Comment accuracy analysis
- code-simplifier: Code simplification suggestions

Agents are defined in TOML format under `.hachimoku/agents/`, and you can add project-specific custom agents.
See [Agent Definitions](agents.md) for details.

### Execution and Output

- Choose between sequential and parallel execution
- Output formats: Markdown (human-readable) and JSON (machine-readable)
- Review results are automatically accumulated in JSONL format under `.hachimoku/reviews/`
- Review reports go to stdout, progress information to stderr, supporting pipes and redirects

### Configuration

Supports a hierarchical TOML-based configuration system.

- CLI options > `.hachimoku/config.toml` > `pyproject.toml [tool.hachimoku]` > `~/.config/hachimoku/config.toml` > defaults

See [Configuration](configuration.md) for details.

### Domain Models

Review results are managed with type-safe domain models.
Provides Severity (4-level severity), ReviewIssue (unified issue representation), AgentResult (discriminated union for success/truncated/error/timeout), ReviewReport (aggregated report), ToolCategory (tool categories), and ReviewHistoryRecord (review history records).
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
