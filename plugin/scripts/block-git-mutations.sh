#!/usr/bin/env bash
# block-git-mutations.sh — PreToolUse hook: read-only git/gh guard
#
# 許可リストは src/hachimoku/security/readonly_allowlist.py の
# ALLOWED_GIT_SUBCOMMANDS / ALLOWED_GH_PATTERNS と一致させること。
# ドリフトは tests/unit/plugin/test_block_git_mutations.py::test_allowlist_matches_python_definition が検出する。

set -euo pipefail

# ---------------------------------------------------------------------------
# 1. jq が利用可能か確認。不在の場合は安全側（deny）に倒す。
# ---------------------------------------------------------------------------
if ! command -v jq >/dev/null 2>&1; then
    echo "block-git-mutations: jq not found; denying command" >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# 2. stdin から PreToolUse JSON を読み込み、コマンド文字列を取り出す。
# ---------------------------------------------------------------------------
input="$(cat)"
cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"

if [[ -z "$cmd" ]]; then
    # コマンドが取り出せない場合は deny（判定不能は安全側）
    echo "block-git-mutations: could not extract command from input; denying" >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# 3. シェル制御文字・複合コマンドの検出 → deny
#    注意: この検査は git/gh ゲートより先に行うこと（"bash -c 'git push'" 対応）
# ---------------------------------------------------------------------------
if [[ "$cmd" == *";"* ]] \
    || [[ "$cmd" == *"&&"* ]] \
    || [[ "$cmd" == *"||"* ]] \
    || [[ "$cmd" == *"|"* ]] \
    || [[ "$cmd" == *'`'* ]] \
    || [[ "$cmd" == *'$('* ]] \
    || [[ "$cmd" == *"bash -c"* ]]; then
    echo "block-git-mutations: denied compound/shell command: $cmd" >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# 4. git/gh 以外のコマンドはすべて許可
# ---------------------------------------------------------------------------
first_token="${cmd%% *}"  # 最初のスペース区切りトークン

if [[ "$first_token" != "git" && "$first_token" != "gh" ]]; then
    exit 0
fi

# ---------------------------------------------------------------------------
# 5. git の処理
# ---------------------------------------------------------------------------

# git 許可サブコマンドリスト（readonly_allowlist.py の ALLOWED_GIT_SUBCOMMANDS と同一集合）
ALLOWED_GIT_SUBCOMMANDS=(
    "diff"
    "grep"
    "log"
    "show"
    "status"
    "merge-base"
    "rev-parse"
    "branch"
    "ls-files"
)

if [[ "$first_token" == "git" ]]; then
    # 第1サブコマンドを抽出する。
    # `-c key=val` や `-C path` など、オプションとその引数をスキップする。
    remaining="${cmd#git}"  # "git" を除去
    subcommand=""
    # トークンを配列に分割
    read -ra tokens <<< "$remaining"
    i=0
    while [[ $i -lt ${#tokens[@]} ]]; do
        tok="${tokens[$i]}"
        case "$tok" in
            -c|-C|--work-tree|--git-dir|--namespace)
                # 次のトークンは値なのでスキップ
                i=$(( i + 1 ))
                ;;
            --*)
                # --work-tree=path のような形式もスキップ
                ;;
            -*)
                # 短オプション（単体フラグ）はスキップ
                ;;
            "")
                ;;
            *)
                subcommand="$tok"
                break
                ;;
        esac
        i=$(( i + 1 ))
    done

    if [[ -z "$subcommand" ]]; then
        echo "block-git-mutations: denied: could not determine git subcommand: $cmd" >&2
        exit 2
    fi

    # サブコマンドが許可リストに含まれるか確認
    allowed=false
    for allowed_sub in "${ALLOWED_GIT_SUBCOMMANDS[@]}"; do
        if [[ "$subcommand" == "$allowed_sub" ]]; then
            allowed=true
            break
        fi
    done

    if [[ "$allowed" == "false" ]]; then
        echo "block-git-mutations: denied mutating command: $cmd" >&2
        exit 2
    fi

    # `git branch` の特別処理:
    # 変更系フラグや位置引数（新しいブランチ名）がある場合は deny する。
    # 読み取り専用の例: `git branch`, `git branch -a`, `git branch -v`, `git branch -r`, `git branch --list`
    if [[ "$subcommand" == "branch" ]]; then
        # subcommand 以降のトークンを調べる
        past_subcommand=false
        for tok in "${tokens[@]}"; do
            if [[ "$past_subcommand" == "false" ]]; then
                if [[ "$tok" == "branch" ]]; then
                    past_subcommand=true
                fi
                continue
            fi
            # 変更系フラグ
            case "$tok" in
                -d|-D|-m|-M|--delete|--move|--rename|--copy|-c|-C|--force|-f)
                    echo "block-git-mutations: denied mutating git branch flag: $cmd" >&2
                    exit 2
                    ;;
                -*)
                    # 読み取り専用フラグ（-a, -v, -r, --list 等）は許可
                    ;;
                *)
                    # 位置引数 = 新しいブランチ名 → deny
                    echo "block-git-mutations: denied mutating git branch (positional arg): $cmd" >&2
                    exit 2
                    ;;
            esac
        done
    fi

    exit 0
fi

# ---------------------------------------------------------------------------
# 6. gh の処理
# ---------------------------------------------------------------------------
if [[ "$first_token" == "gh" ]]; then
    # トークン配列に分割
    read -ra tokens <<< "${cmd#gh}"

    # 先頭の空トークンを除去して実際のサブコマンドを取得
    gh_tokens=()
    for tok in "${tokens[@]}"; do
        if [[ -n "$tok" ]]; then
            gh_tokens+=("$tok")
        fi
    done

    if [[ ${#gh_tokens[@]} -eq 0 ]]; then
        echo "block-git-mutations: denied: no gh subcommand: $cmd" >&2
        exit 2
    fi

    t0="${gh_tokens[0]}"
    t1="${gh_tokens[1]:-}"

    # 許可パターン（readonly_allowlist.py の ALLOWED_GH_PATTERNS と同一）
    # ("pr", "view"), ("pr", "diff"), ("issue", "view"), ("api",)
    if [[ "$t0" == "api" ]]; then
        # gh api は GET のみ許可。POST 系フラグがあれば deny。
        # IMPLICIT_POST_FLAGS: -f --field -F --raw-field --input
        for tok in "${gh_tokens[@]}"; do
            case "$tok" in
                -f|--field|-F|--raw-field|--input)
                    echo "block-git-mutations: denied gh api with mutating flag: $cmd" >&2
                    exit 2
                    ;;
            esac
        done
        exit 0
    fi

    if [[ "$t0" == "pr" && "$t1" == "view" ]]; then
        exit 0
    fi

    if [[ "$t0" == "pr" && "$t1" == "diff" ]]; then
        exit 0
    fi

    if [[ "$t0" == "issue" && "$t1" == "view" ]]; then
        exit 0
    fi

    echo "block-git-mutations: denied mutating command: $cmd" >&2
    exit 2
fi
