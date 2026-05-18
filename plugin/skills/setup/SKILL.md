---
description: Set up hachimoku review subagents for this project. Run once before the first review, or after upgrading hachimoku.
disable-model-invocation: true
allowed-tools: Bash
---

# hachimoku setup

Generate hachimoku's review subagents and manifest into `.claude/` so that
`/hachimoku:review` can dispatch them.

## Steps

1. Verify `uv` is available by running `uv --version`. If it is not installed,
   stop and tell the user to install `uv` (https://docs.astral.sh/uv/).

2. Run the build command, passing the absolute path of the bundled guard script:

   ```
   uvx --from git+https://github.com/drillan/hachimoku@<ref> hachimoku build \
     --output .claude \
     --hook-script "${CLAUDE_PLUGIN_ROOT}/scripts/block-git-mutations.sh"
   ```

   Replace `<ref>` with the pinned hachimoku release matching this plugin
   version (see the plugin README).

3. Confirm that `.claude/agents/` now contains the review subagent `.md`
   files and `.claude/manifest.json` exists. Report the count to the user.
