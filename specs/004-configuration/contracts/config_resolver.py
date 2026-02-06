"""設定リゾルバーの型契約。

FR-CF-001: 5層の設定ソースの階層解決
FR-CF-007: 項目単位のマージ
"""

from __future__ import annotations

from pathlib import Path

# 実装時に hachimoku.models.config.HachimokuConfig を import する


def load_toml_config(path: Path) -> dict[str, object]:
    """TOML 設定ファイルを読み込み辞書として返す。

    Args:
        path: TOML ファイルのパス。

    Returns:
        パースされた設定辞書。

    Raises:
        tomllib.TOMLDecodeError: TOML 構文エラーの場合。
        PermissionError: 読み取り権限がない場合。
        FileNotFoundError: ファイルが存在しない場合。
    """
    ...


def load_pyproject_config(path: Path) -> dict[str, object] | None:
    """pyproject.toml から [tool.hachimoku] セクションを読み込む。

    FR-CF-005: [tool.hachimoku] セクションが存在しない場合は None を返す。

    Args:
        path: pyproject.toml のパス。

    Returns:
        [tool.hachimoku] セクションの辞書。セクションが存在しなければ None。

    Raises:
        tomllib.TOMLDecodeError: TOML 構文エラーの場合。
        PermissionError: 読み取り権限がない場合。
    """
    ...


def merge_config_layers(
    *layers: dict[str, object] | None,
) -> dict[str, object]:
    """複数の設定レイヤーを項目単位でマージする。

    FR-CF-007: 後のレイヤーが先のレイヤーを上書きする。
    agents セクションはエージェント名→フィールド単位でマージする。
    None のレイヤーはスキップされる。

    Args:
        layers: マージ対象の設定辞書。低優先度から高優先度の順。

    Returns:
        マージ済みの設定辞書。
    """
    ...


def filter_cli_overrides(cli_options: dict[str, object]) -> dict[str, object]:
    """CLI オプション辞書から None 値を除外する。

    None 値は「未指定」を意味し、マージ対象から除外する。

    Args:
        cli_options: CLI パーサーから渡された辞書。

    Returns:
        None 値を除外した辞書。
    """
    ...


def resolve_config(
    start_dir: Path | None = None,
    cli_overrides: dict[str, object] | None = None,
) -> "HachimokuConfig":  # type: ignore[name-defined]  # noqa: F821
    """5層の設定ソースを解決し HachimokuConfig を構築する。

    FR-CF-001: CLI > .hachimoku/config.toml > pyproject.toml [tool.hachimoku]
              > ~/.config/hachimoku/config.toml > デフォルト値

    設定ファイルが存在しない場合は該当レイヤーをスキップし、次のレイヤーに進む。
    全ファイルが存在しない場合はデフォルト値のみで HachimokuConfig を構築する。

    Args:
        start_dir: 探索開始ディレクトリ。None の場合はカレントディレクトリ。
        cli_overrides: CLI オプションの辞書。None 値は未指定扱い。

    Returns:
        解決済みの HachimokuConfig インスタンス。

    Raises:
        pydantic.ValidationError: マージ後の設定が不正な場合。
        tomllib.TOMLDecodeError: 設定ファイルの TOML 構文が不正な場合。
        PermissionError: 設定ファイルの読み取り権限がない場合。
    """
    ...
