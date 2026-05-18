---
description: Run a multi-agent code review. Use when the user asks for a code review of changes, a PR, or files.
argument-hint: [PR number | file paths | empty for diff]
allowed-tools: Bash Agent Read
---

# hachimoku review

Orchestrate a multi-agent code review. You are the orchestrator: dispatch
review subagents, but do NOT read diffs or findings into your own context —
keep your context light. Subagents work in isolated context windows.

## Preconditions

- `.claude/manifest.json` and `.claude/agents/` must exist. If not, tell the
  user to run `/hachimoku:setup` first, then stop.
- `uv` must be available (`uv --version`).

## Steps

1. **Determine the target** from `$ARGUMENTS`:
   - empty → diff mode
   - a single integer → PR mode (`--commit` not used)
   - file paths → file mode

2. **Select** — run `select` to compute the dispatch plan. Replace `<ref>`
   with the pinned hachimoku release:

   ```bash
   uvx --from git+https://github.com/drillan/hachimoku@<ref> hachimoku select \
     <target args> --manifest .claude/manifest.json
   ```

   Parse the JSON output: it contains `run_dir` and `phases`
   (`early` / `main` / `final`, each a list of agent names).

3. **Dispatch subagents** — for each phase in order (early → main → final),
   dispatch every listed agent **in parallel** using the Agent tool. Give
   each subagent this instruction (substitute the run_dir and agent name):

   > Review the changes for <target>. The run directory is `<run_dir>`.
   > Write your findings JSON to `<run_dir>/<agent-name>.json` per your
   > Output Contract.

   Wait for all agents in a phase before starting the next phase. Do not
   read the subagents' findings yourself.

4. **Aggregate** — after all phases complete:

   ```bash
   uvx --from git+https://github.com/drillan/hachimoku@<ref> hachimoku aggregate \
     --run-dir <run_dir> --manifest .claude/manifest.json <target args>
   ```

   This prints the Markdown report and exits with a severity-based code.

5. **Present** the Markdown report to the user.

## Notes

- If `uv`/`uvx` is missing, stop with a clear error (do not fall back).
- If `select` reports no applicable agents, tell the user there is nothing
  to review and stop.
