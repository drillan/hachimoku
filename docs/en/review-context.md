# Review Context Guidelines

Review Context is a section included in GitHub Issue templates that provides supplementary information referenced by review agents during code review.
By documenting relevant information not included in the diff, it broadens the scope of review analysis and helps improve the accuracy of findings.

```{contents}
:depth: 2
:local:
```

## Background

hachimoku's review agents typically analyze code within the diff.
However, when changes have ripple effects on other files or configurations, analysis of the diff alone may miss impacts.

For example, when changing a configuration default value, template files containing the old default value may not be updated.
Such ripple effects outside the diff can be included in the agent's investigation scope by documenting the impact range in Review Context.

## Field Descriptions

Review Context consists of three fields.

### Related Specifications

Document references to specifications and documentation related to the change.

Purpose
: Provide information sources for review agents to verify alignment with specifications

What to include:

- Spec file paths with section and requirement IDs
- Related Constitution Articles
- Related Issue or PR numbers
- Related documents under docs/

Granularity guidelines:

- Include specific sections or requirement IDs, not just file paths
- Document each specification if changes relate to multiple specs

Good examples:

```text
# From Issue #152 — Specify spec sections and requirement IDs
- specs/005-review-engine/spec.md — FR-RE-002 (Pipeline Step 1-9), FR-RE-008 (ReviewReport aggregation)
- specs/005-review-engine/data-model.md — ReviewReport structure

# From Issue #150 — Specify Constitution Articles and related principles
- Constitution Art.4 (Simplicity) — No unnecessary wrappers or over-abstraction
- specs/003-agent-definition/spec.md — Agent definition TOML structure
```

Insufficient examples:

```text
# Points to entire file; agent cannot identify specific areas to reference
- specs/005-review-engine/spec.md
```

### Impact Scope

Document files and configurations that may be affected beyond the directly changed files.

Purpose
: Identify targets for review agents to investigate ripple effects outside the diff

What to include:

- Paths of files affected but not included in the diff
- Type of impact (configuration compatibility, interface changes, tests, etc.)
- Table format is effective when there are specific before/after values

Granularity guidelines:

- Document at the file level, not directory level
- Supplement with the type of impact in parentheses

Good examples:

```text
# From Issue #155 — Table format listing affected files, current values, and new values
| File | Current Value | After Change |
|------|---------------|--------------|
| src/hachimoku/models/config.py:83 | claudecode:claude-sonnet-4-5 | claudecode:claude-opus-4-6 |
| src/hachimoku/agents/_builtin/code-reviewer.toml:3 | anthropic:claude-sonnet-4-5 | anthropic:claude-opus-4-6 |

# From Issue #148 — Bullet points with file paths and change summaries
- src/hachimoku/engine/_selector.py — 4 fields added to SelectorOutput model
- src/hachimoku/engine/_instruction.py — New function build_selector_context_section() added
- src/hachimoku/engine/_engine.py — Metadata propagation logic added between Step 5-6

# From Issue #150 — Brief when change targets are limited
- src/hachimoku/agents/_builtin/type-design-analyzer.toml (sole change target)
- No Python code changes
```

Insufficient examples:

```text
# Points to entire directory; cannot narrow investigation scope
- src/hachimoku/
```

### Existing Pattern References

Document existing similar implementations that should maintain consistency.

Purpose
: Enable review agents to have consistency evaluation criteria and detect deviations from existing patterns

What to include:

- File paths of reference implementations
- Specific pattern names (classes, functions, structures, etc.)
- Explanation of what is "similar"

Granularity guidelines:

- Be specific about which pattern, not just "similar pattern"

Good examples:

```text
# From Issue #148 — Specify function names and roles
- build_review_instruction() in src/hachimoku/engine/_instruction.py — Existing pattern for user_message construction
- src/hachimoku/engine/_engine.py Step 4-6 — Current context construction flow from user_message

# From Issue #152 — List reference points for the same architectural pattern
- SelectorOutput in src/hachimoku/engine/_selector.py — Structured output model pattern
- SelectorDefinition in src/hachimoku/agents/models.py — TOML definition model pattern
- src/hachimoku/agents/_builtin/selector.toml — Built-in TOML definition pattern

# From Issue #155 — Processing logic pattern
- _model_resolver.py executes model resolution based on prefix
```

Insufficient examples:

```text
# Unclear which pattern; agent cannot evaluate consistency
- Implement with the same pattern
```

## Impact on Review Quality

The completeness of Review Context affects the analysis scope of review agents.

When related specifications are documented
: Agents include specification alignment in their verification scope. Without documentation, detection of specification violations depends on the agent's own investigative ability.

When impact scope is documented
: Agents include the listed files in their investigation scope. Without documentation, ripple effects outside the diff (stale values in configuration files, interface inconsistencies, etc.) may be missed.

When existing patterns are documented
: Agents include consistency with existing patterns in their evaluation criteria. Without documentation, inconsistencies with similar code in the project may not be detected.

## Principles for Documentation

Document what you know
: Only include information you are confident about. Complete coverage of all fields is not required.

Empty fields are acceptable
: Inaccurate information can mislead agents, so leave fields empty when uncertain.

Can be added later
: Information discovered after Issue creation can be supplemented via comments.

Do not include speculation
: Do not document uncertain information such as "probably affected." Only include confirmed facts.
