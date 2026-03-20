"""InitHandler -- init サブコマンドのビジネスロジック。

FR-CLI-007: .hachimoku/ ディレクトリ構造の初期化。
FR-CLI-008: 既存ファイルのスキップと --force による上書き。
"""

from __future__ import annotations

import hashlib
import shutil
from importlib.resources import as_file, files
from pathlib import Path
from typing import Literal

from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.config import DEFAULT_MAX_TURNS


class InitError(Exception):
    """init コマンドのエラー。

    ファイルシステム操作エラー等。
    エラーメッセージは解決方法のヒントを含む（憲法 Art.3）。
    """


class InitResult(HachimokuBaseModel):
    """init コマンドの実行結果。

    Attributes:
        created: 新規作成されたファイル/ディレクトリのパスタプル。
        updated: ビルトイン更新により上書きされたファイルのパスタプル。
        skipped: 既存のためスキップされたファイル/ディレクトリのパスタプル（通常 init 用）。
        skipped_up_to_date: ビルトインと同一ハッシュのためスキップされたファイル（upgrade 用）。
        skipped_customized: カスタマイズ済みのためスキップされたファイル（upgrade 用）。
    """

    created: tuple[Path, ...] = ()
    updated: tuple[Path, ...] = ()
    skipped: tuple[Path, ...] = ()
    skipped_up_to_date: tuple[Path, ...] = ()
    skipped_customized: tuple[Path, ...] = ()


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

# File extension filter (list, e.g. [".py", ".rst"])
# file_extensions = []

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
        try:
            content = gitignore_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            raise InitError(
                f"Failed to read .gitignore: {e}\n"
                "The file is not valid UTF-8. "
                "Convert .gitignore to UTF-8 encoding and try again."
            ) from e
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


def _compute_file_hash(path: Path) -> str:
    """ファイルの SHA-256 ハッシュを 16 進数文字列で返す。

    Args:
        path: ハッシュを計算するファイルのパス。

    Returns:
        SHA-256 ハッシュの 16 進数文字列。
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _compute_bytes_hash(data: bytes) -> str:
    """バイト列の SHA-256 ハッシュを 16 進数文字列で返す。

    Args:
        data: ハッシュを計算するバイト列。

    Returns:
        SHA-256 ハッシュの 16 進数文字列。
    """
    return hashlib.sha256(data).hexdigest()


def _upgrade_builtin_agents(
    agents_dir: Path, *, force: bool
) -> tuple[list[Path], list[Path], list[Path], list[Path]]:
    """ハッシュ比較により、ビルトインエージェント定義を更新する。

    ローカルファイルのハッシュとビルトインのハッシュを比較し、
    カスタマイズの有無を判定する。

    Args:
        agents_dir: エージェント定義ディレクトリ。
        force: True の場合、カスタマイズ済みファイルも上書きする。

    Returns:
        (created, updated, skipped_up_to_date, skipped_customized)
    """
    builtin_package = files("hachimoku.agents._builtin")
    created: list[Path] = []
    updated: list[Path] = []
    skipped_up_to_date: list[Path] = []
    skipped_customized: list[Path] = []

    for resource in sorted(builtin_package.iterdir(), key=lambda r: r.name):
        if not resource.name.endswith(".toml"):
            continue
        dest = agents_dir / resource.name

        with as_file(resource) as src_path:
            builtin_content = src_path.read_bytes()

        if not dest.exists():
            dest.write_bytes(builtin_content)
            created.append(dest)
            continue

        local_hash = _compute_file_hash(dest)
        builtin_hash = _compute_bytes_hash(builtin_content)

        if local_hash == builtin_hash:
            skipped_up_to_date.append(dest)
        elif force:
            dest.write_bytes(builtin_content)
            updated.append(dest)
        else:
            skipped_customized.append(dest)

    return created, updated, skipped_up_to_date, skipped_customized


def run_init(
    project_root: Path, *, force: bool = False, upgrade: bool = False
) -> InitResult:
    """init コマンドのビジネスロジックを実行する。

    手順（通常モード）:
    1. .hachimoku/ ディレクトリ作成
    2. .hachimoku/config.toml 生成（コメント付きテンプレート）
    3. .hachimoku/agents/ にビルトインエージェント定義コピー
    4. .hachimoku/reviews/ ディレクトリ作成
    5. Git リポジトリ内のみ、.gitignore に /.hachimoku/ エントリを追加

    upgrade モード（upgrade=True）:
    ハッシュ比較によりビルトインエージェント定義を更新する。
    config.toml、reviews/、.gitignore には一切触れない。

    upgrade + force モード（upgrade=True, force=True）:
    カスタマイズ済みファイルも含め全ビルトイン TOML を更新する。
    config.toml、reviews/、.gitignore には一切触れない。

    Args:
        project_root: プロジェクトルートディレクトリ。
        force: True の場合、既存ファイルを上書きする。
        upgrade: True の場合、ハッシュ比較でエージェント定義を更新する。

    Returns:
        InitResult: 作成・スキップ・更新されたファイル情報。

    Raises:
        InitError: ファイルシステム操作エラー等。
    """
    hachimoku_dir = project_root / ".hachimoku"
    agents_dir = hachimoku_dir / "agents"

    try:
        if upgrade:
            # upgrade モード: ハッシュ比較でエージェント定義を更新
            hachimoku_dir.mkdir(parents=True, exist_ok=True)
            agents_dir.mkdir(exist_ok=True)

            agent_created, agent_updated, agent_up_to_date, agent_customized = (
                _upgrade_builtin_agents(agents_dir, force=force)
            )
            return InitResult(
                created=tuple(agent_created),
                updated=tuple(agent_updated),
                skipped_up_to_date=tuple(agent_up_to_date),
                skipped_customized=tuple(agent_customized),
            )

        # 通常モード
        created: list[Path] = []
        skipped: list[Path] = []
        config_path = hachimoku_dir / "config.toml"
        reviews_dir = hachimoku_dir / "reviews"

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

        # .gitignore に /.hachimoku/ エントリを追加（Git リポジトリ内のみ）
        if (project_root / ".git").exists():
            gitignore_path = project_root / ".gitignore"
            gitignore_result = _ensure_gitignore(project_root)
            if gitignore_result == "created":
                created.append(gitignore_path)
            else:
                skipped.append(gitignore_path)

        return InitResult(created=tuple(created), skipped=tuple(skipped))
    except OSError as e:
        raise InitError(
            f"Failed to initialize .hachimoku/: {e}\n"
            "Check directory permissions and available disk space."
        ) from e
