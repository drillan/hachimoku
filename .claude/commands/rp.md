# /rp

Shortcut command to execute a comprehensive review of a pull request.

## Usage

```
/rp <pr-number>
```

## Arguments

| Argument Name | Type | Required | Description |
|---------------|------|----------|-------------|
| `pr-number`   | integer | Yes      | The number of the GitHub pull request |

## Operation Process

Use the `/pr-review-toolkit:review-pr` skill to review the PR and output the results to the `ai_working/review-pr-<pr-number>.md` file.

## Error Handling

| Error Condition | Resolution Method |
|-----------------|-------------------|
| PR not found    | Guide user to run `gh pr view <number>` command to verify PR existence |
| gh authentication incomplete | Guide user to execute `gh auth login` command |
