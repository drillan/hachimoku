"""InitHandler -- init サブコマンドのビジネスロジック。

FR-CLI-007: .hachimoku/ ディレクトリ構造の初期化。
FR-CLI-008: 既存ファイルのスキップと --force による上書き。
"""

from __future__ import annotations

import shutil
from importlib.resources import as_file, files
from pathlib import Path
from typing import Literal

from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.config import DEFAULT_MAX_TURNS


class InitError(Exception):
    """init コマンドのエラー。

    Git リポジトリ外での実行等。
    エラーメッセージは解決方法のヒントを含む（憲法 Art.3）。
    """


class InitResult(HachimokuBaseModel):
    """init コマンドの実行結果。

    Attributes:
        created: 新規作成されたファイル/ディレクトリのパスタプル。
        skipped: 既存のためスキップされたファイル/ディレクトリのパスタプル。
    """

    created: tuple[Path, ...] = ()
    skipped: tuple[Path, ...] = ()


_CONFIG_TEMPLATE: str = """\
# hachimoku configuration
# Uncomment and modify settings as needed.

# --- Execution Settings ---

# LLM model name (prefix: "claudecode:" or "anthropic:")
# model = "claudecode:claude-opus-4-6"

# Timeout in seconds
# timeout = 600

# Maximum agent turns
# max_turns = {max_turns}

# Enable parallel execution
# parallel = true

# Base branch for diff mode
# base_branch = "main"

# --- Output Settings ---

# Output format: "markdown" or "json"
# output_format = "markdown"

# Save review results to .hachimoku/reviews/
# save_reviews = true

# Show cost information
# show_cost = false

# --- File Mode Settings ---

# Maximum files per review
# max_files_per_review = 100

# --- Selector Agent Settings ---

# [selector]
# model = "claudecode:claude-opus-4-6"
# timeout = 600
# max_turns = {max_turns}

# --- Agent-Specific Settings ---
# Override settings for individual agents.
# Agent names must match definition file names (without .toml).
#
# [agents.code-reviewer]
# enabled = true
# model = "claudecode:claude-opus-4-6"
# timeout = 600
# max_turns = {max_turns}
"""


def _ensure_git_repository(project_root: Path) -> None:
    """Git リポジトリ内であることを確認する。

    Args:
        project_root: プロジェクトルートディレクトリ。

    Raises:
        InitError: .git/ が存在しない場合。
    """
    if not (project_root / ".git").exists():
        raise InitError(
            f"Not a Git repository: {project_root}\n"
            "Run 'git init' to initialize a Git repository first."
        )


GITIGNORE_SECTION: str = "# hachimoku"
"""gitignore に追加するセクションコメント。"""

GITIGNORE_ENTRY: str = "/.hachimoku/"
"""gitignore に追加するエントリ。"""


def _ensure_gitignore(project_root: Path) -> Literal["created", "skipped"]:
    """プロジェクトの .gitignore に /.hachimoku/ エントリを追加する。

    既に /.hachimoku/ エントリが存在する場合はスキップする。
    .gitignore が存在しない場合は新規作成する。

    Args:
        project_root: プロジェクトルートディレクトリ。

    Returns:
        "created": エントリを追加した場合。
        "skipped": エントリが既に存在していた場合。
    """
    gitignore_path = project_root / ".gitignore"

    if gitignore_path.exists():
        content = gitignore_path.read_text(encoding="utf-8")
        # 行単位で完全一致チェック
        lines = content.splitlines()
        if GITIGNORE_ENTRY in lines:
            return "skipped"
        # 末尾に改行がない場合は追加
        if content and not content.endswith("\n"):
            content += "\n"
        content += f"{GITIGNORE_SECTION}\n{GITIGNORE_ENTRY}\n"
        gitignore_path.write_text(content, encoding="utf-8")
    else:
        content = f"{GITIGNORE_SECTION}\n{GITIGNORE_ENTRY}\n"
        gitignore_path.write_text(content, encoding="utf-8")

    return "created"


def _generate_config_template() -> str:
    """コメント付き config.toml テンプレートを生成する。

    全設定項目をコメントとして記載し、デフォルト値を示す。

    Returns:
        テンプレート文字列。
    """
    return _CONFIG_TEMPLATE.format(max_turns=DEFAULT_MAX_TURNS)


def _copy_builtin_agents(
    agents_dir: Path, *, force: bool
) -> tuple[list[Path], list[Path]]:
    """ビルトインエージェント定義を agents_dir にコピーする。

    importlib.resources で hachimoku.agents._builtin パッケージからファイルを取得する。

    Args:
        agents_dir: コピー先の agents ディレクトリ。
        force: True の場合、既存ファイルを上書きする。

    Returns:
        (作成されたファイルリスト, スキップされたファイルリスト)
    """
    builtin_package = files("hachimoku.agents._builtin")
    created: list[Path] = []
    skipped: list[Path] = []

    for resource in sorted(builtin_package.iterdir(), key=lambda r: r.name):
        if not resource.name.endswith(".toml"):
            continue
        dest = agents_dir / resource.name
        if dest.exists() and not force:
            skipped.append(dest)
            continue
        with as_file(resource) as src_path:
            shutil.copy2(src_path, dest)
        created.append(dest)

    return created, skipped


def run_init(project_root: Path, *, force: bool = False) -> InitResult:
    """init コマンドのビジネスロジックを実行する。

    手順:
    1. Git リポジトリ確認（.git/ の存在）
    2. .hachimoku/ ディレクトリ作成
    3. .hachimoku/config.toml 生成（コメント付きテンプレート）
    4. .hachimoku/agents/ にビルトインエージェント定義コピー
    5. .hachimoku/reviews/ ディレクトリ作成
    6. .gitignore に /.hachimoku/ エントリを追加

    Args:
        project_root: プロジェクトルートディレクトリ。
        force: True の場合、既存ファイルを上書きする。

    Returns:
        InitResult: 作成・スキップされたファイル情報。

    Raises:
        InitError: Git リポジトリ外での実行、ファイルシステム操作エラー等。
    """
    _ensure_git_repository(project_root)

    hachimoku_dir = project_root / ".hachimoku"
    config_path = hachimoku_dir / "config.toml"
    agents_dir = hachimoku_dir / "agents"
    reviews_dir = hachimoku_dir / "reviews"

    created: list[Path] = []
    skipped: list[Path] = []

    try:
        # ディレクトリ作成（常に exist_ok=True で安全）
        hachimoku_dir.mkdir(parents=True, exist_ok=True)
        agents_dir.mkdir(exist_ok=True)
        reviews_dir.mkdir(exist_ok=True)

        # config.toml 生成
        if config_path.exists() and not force:
            skipped.append(config_path)
        else:
            config_path.write_text(_generate_config_template(), encoding="utf-8")
            created.append(config_path)

        # ビルトインエージェント定義コピー
        agent_created, agent_skipped = _copy_builtin_agents(agents_dir, force=force)
        created.extend(agent_created)
        skipped.extend(agent_skipped)

        # .gitignore に /.hachimoku/ エントリを追加
        gitignore_path = project_root / ".gitignore"
        gitignore_result = _ensure_gitignore(project_root)
        if gitignore_result == "created":
            created.append(gitignore_path)
        else:
            skipped.append(gitignore_path)
    except OSError as e:
        raise InitError(
            f"Failed to initialize .hachimoku/: {e}\n"
            "Check directory permissions and available disk space."
        ) from e

    return InitResult(created=tuple(created), skipped=tuple(skipped))
