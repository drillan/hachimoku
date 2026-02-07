"""InitHandler contract — init サブコマンドのビジネスロジック。

FR-CLI-007: .hachimoku/ ディレクトリ構造の初期化。
FR-CLI-008: 既存ファイルのスキップと --force による上書き。
"""

from __future__ import annotations

from pathlib import Path

from hachimoku.models._base import HachimokuBaseModel


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


def run_init(project_root: Path, *, force: bool = False) -> InitResult:
    """init コマンドのビジネスロジックを実行する。

    手順:
    1. Git リポジトリ確認（.git/ の存在）
    2. .hachimoku/ ディレクトリ作成
    3. .hachimoku/config.toml 生成（コメント付きテンプレート）
    4. .hachimoku/agents/ にビルトイン6エージェント定義コピー
    5. .hachimoku/reviews/ ディレクトリ作成

    Args:
        project_root: プロジェクトルートディレクトリ。
        force: True の場合、既存ファイルを上書きする。

    Returns:
        InitResult: 作成・スキップされたファイル情報。

    Raises:
        InitError: Git リポジトリ外での実行等。
    """
    ...


def _ensure_git_repository(project_root: Path) -> None:
    """Git リポジトリ内であることを確認する。

    Raises:
        InitError: .git/ が存在しない場合。
    """
    ...


def _generate_config_template() -> str:
    """コメント付き config.toml テンプレートを生成する。

    全設定項目をコメントとして記載し、デフォルト値を示す。
    """
    ...


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
    ...
