#!/usr/bin/env bash
# block-git-mutations.sh — PreToolUse hook: read-only git/gh guard
#
# 許可リストは src/hachimoku/security/readonly_allowlist.py の
# ALLOWED_GIT_SUBCOMMANDS / ALLOWED_GH_PATTERNS と一致させること。
# ドリフトは tests/unit/plugin/test_block_git_mutations.py::test_allowlist_matches_python_definition が検出する。
#
# Limitations (best-effort guard, not a complete sandbox):
#   Does NOT catch: unicode whitespace variants, terminal-escape-encoded
#   payloads, or future shell syntax. Quoting/expansion metacharacters are
#   denied wholesale precisely because this script cannot model shell
#   re-parsing. See design doc threat-model section.

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

# 先頭・末尾の空白（スペース・タブ）を除去する。
# これを行わないと "  git push" や "\tgit push" が第1トークン判定をすり抜ける。
cmd="${cmd#"${cmd%%[![:space:]]*}"}"  # 先頭の空白を除去
cmd="${cmd%"${cmd##*[![:space:]]}"}"  # 末尾の空白を除去

if [[ -z "$cmd" ]]; then
    # 空白のみの場合は git/gh ではないため許可
    exit 0
fi

# ---------------------------------------------------------------------------
# 3. シェル制御文字・複合コマンドの検出 → deny
#    注意: この検査は git/gh ゲートより先に、かつ正規化前の生 $cmd に対して
#    行うこと（改行/復帰を消さないため、およびクォート除去前の判定のため）。
#    - 改行 \n / 復帰 \r: コマンド区切り
#    - & : バックグラウンド実行（"&&" もこれで巻き込まれる）
#    - | : パイプ（"||" もこれで巻き込まれる）
#    - < > : リダイレクト（">>" は ">" で、プロセス置換 "<(" ">(" も < > でカバー）
# ---------------------------------------------------------------------------
if [[ "$cmd" == *";"* ]] \
    || [[ "$cmd" == *"&"* ]] \
    || [[ "$cmd" == *"|"* ]] \
    || [[ "$cmd" == *"<"* ]] \
    || [[ "$cmd" == *">"* ]] \
    || [[ "$cmd" == *$'\n'* ]] \
    || [[ "$cmd" == *$'\r'* ]]; then
    echo "block-git-mutations: denied compound/shell command: $cmd" >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# 3b. クォート/展開メタ文字の検出 → deny
#     シェルは実行前にクォート除去・展開・再パースを行うため、これらの文字を
#     含むコマンドはフックが素朴にトークン化しても実体と一致しない
#     （例: '"git" push'・'g\it push'・'git${IFS}push'）。
#     フックはシェル再パースをモデル化できないため、これらを一律 deny する。
#     レビュー用の読取専用コマンド（git diff / git log / gh pr diff N /
#     gh api /repos/o/r/pulls）はこれらの文字を必要としない。
#     注: バッククォート ` と $( は本検査の $ ・ ` で巻き込まれる。
# ---------------------------------------------------------------------------
if [[ "$cmd" == *"'"* ]] \
    || [[ "$cmd" == *'"'* ]] \
    || [[ "$cmd" == *'\'* ]] \
    || [[ "$cmd" == *'`'* ]] \
    || [[ "$cmd" == *'$'* ]] \
    || [[ "$cmd" == *'{'* ]] \
    || [[ "$cmd" == *'}'* ]]; then
    echo "block-git-mutations: denied quoting/expansion metacharacter: $cmd" >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# 4. タブを単一スペースに正規化する。
#    タブ区切り（"git\tcommit\t-m\tx"）はシェルでは語の区切りだが、
#    スペース区切り前提のトークン抽出をすり抜ける。改行/復帰は section 3 で
#    既に deny 済みのため、ここで消えても問題ない（ここはタブのみ正規化する）。
# ---------------------------------------------------------------------------
cmd="${cmd//$'\t'/ }"

# ---------------------------------------------------------------------------
# 5. 第1トークン解析と git/gh ゲート
# ---------------------------------------------------------------------------
# トークン列に分割（スペース区切り。連続スペースは read が吸収する）。
read -ra all_tokens <<< "$cmd"

if [[ ${#all_tokens[@]} -eq 0 ]]; then
    # トークンが無い場合は git/gh ではないため許可
    exit 0
fi

first_token="${all_tokens[0]}"

# 環境変数プレフィックスの検出 → deny
#   `VAR=val git push` 形式は有効な mutating コマンド呼び出しであり、
#   第1トークンが "git"/"gh" に一致しないため判定をすり抜ける。
#   サブエージェントが env プレフィックス付き git/gh を使う正当な理由はないため一律 deny。
if [[ "$first_token" == *"="* ]]; then
    echo "block-git-mutations: denied command with env-var prefix: $cmd" >&2
    exit 2
fi

# パス指定バイナリの検出 → deny
#   `/usr/bin/git push` は第1トークンがリテラル "git" に一致しないため
#   判定をすり抜ける。レビュー subagent が git/gh を絶対パスで呼ぶ正当理由は
#   ないため、第1トークンに "/" を含むコマンドは一律 deny。
if [[ "$first_token" == *"/"* ]]; then
    echo "block-git-mutations: denied path-qualified binary: $cmd" >&2
    exit 2
fi

# シェルランチャの検出 → deny
#   `sh -c "git push"`・`eval "git push"` 等はサブシェルで任意コマンドを
#   実行する。第1トークン（正規化後）が既知のシェル/評価ランチャに完全一致
#   すれば、後続引数に関わらず一律 deny する。部分文字列マッチではなく
#   トークン完全一致で判定する（旧 `*"bash -c"*` 部分文字列チェックを置換）。
case "$first_token" in
    sh|bash|zsh|ksh|dash|eval|source|.)
        echo "block-git-mutations: denied shell launcher: $cmd" >&2
        exit 2
        ;;
esac

# ---------------------------------------------------------------------------
# 6. git/gh 以外のコマンドの処理
#    第1トークンが git/gh でない場合でも、後続トークンに git/gh（あるいは
#    パス指定の */git ・ */gh）が含まれれば `env git push`・`sudo git push`・
#    `nohup git push` 等のランチャ経由実行であるため deny。
#    ランチャ名を列挙するのではなく汎用ルールで捕捉する。
#    （`time git diff` のような読取専用も巻き込むが、安全側に倒す設計に従う）
# ---------------------------------------------------------------------------
if [[ "$first_token" != "git" && "$first_token" != "gh" ]]; then
    for tok in "${all_tokens[@]:1}"; do
        case "$tok" in
            git|gh|*/git|*/gh)
                echo "block-git-mutations: denied git/gh via launcher: $cmd" >&2
                exit 2
                ;;
        esac
    done
    # 純粋な非 git/gh コマンドは許可
    exit 0
fi

# ---------------------------------------------------------------------------
# 7. git の処理
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
    # all_tokens の先頭（"git"）を除いた残りを対象にする。
    tokens=("${all_tokens[@]:1}")
    subcommand=""
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
# 8. gh の処理
# ---------------------------------------------------------------------------
if [[ "$first_token" == "gh" ]]; then
    # all_tokens の先頭（"gh"）を除いた残りをサブコマンド列とする。
    gh_tokens=("${all_tokens[@]:1}")

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
        # IMPLICIT_POST_FLAGS（readonly_allowlist.py と同一）: -f --field -F --raw-field --input
        #
        # --method / -X は「明示的な HTTP メソッド指定」であり、readonly_allowlist.py の
        # IMPLICIT_POST_FLAGS（暗黙的 POST フラグ）とは意味が異なるため Python 側には追加しない。
        # 読み取り専用の gh api はメソッド指定が不要なため、--method / -X は一律 deny する。
        for tok in "${gh_tokens[@]}"; do
            case "$tok" in
                -f|--field|-F|--raw-field|--input)
                    echo "block-git-mutations: denied gh api with mutating flag: $cmd" >&2
                    exit 2
                    ;;
                --method|--method=*|-X|-X=*)
                    echo "block-git-mutations: denied gh api with explicit HTTP method: $cmd" >&2
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
