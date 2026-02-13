"""定義ローダー。

TOML 形式の定義ファイルを読み込み、AgentDefinition / SelectorDefinition /
AggregatorDefinition モデルとして構築する。
セレクター定義（selector.toml）・アグリゲーター定義（aggregator.toml）は専用のローダーで読み込む。
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Iterator
from importlib.resources import as_file, files
from pathlib import Path
from typing import Final, TypeVar

from pydantic import ValidationError

from hachimoku.agents.models import (
    AgentDefinition,
    AggregatorDefinition,
    LoadError,
    LoadResult,
    SelectorDefinition,
)
from hachimoku.models._base import HachimokuBaseModel

SELECTOR_FILENAME: Final[str] = "selector.toml"
"""セレクター定義ファイル名。レビューエージェントローダーから除外される。"""

AGGREGATOR_FILENAME: Final[str] = "aggregator.toml"
"""アグリゲーター定義ファイル名。レビューエージェントローダーから除外される。"""

_EXCLUDED_FILENAMES: Final[frozenset[str]] = frozenset(
    {SELECTOR_FILENAME, AGGREGATOR_FILENAME}
)
"""レビューエージェントローダーから除外されるファイル名集合。"""

_T = TypeVar("_T", bound=HachimokuBaseModel)


# =============================================================================
# ジェネリック内部関数
# =============================================================================


def _load_single_definition(path: Path, model_type: type[_T]) -> _T:
    """単一の TOML ファイルから定義を読み込む。

    Args:
        path: TOML ファイルのパス。
        model_type: バリデーションに使用する pydantic モデルクラス。

    Returns:
        構築された定義モデル。

    Raises:
        tomllib.TOMLDecodeError: TOML 構文エラーの場合。
        pydantic.ValidationError: バリデーションエラーの場合。
        OSError: ファイルが存在しない場合やアクセスエラーの場合。
    """
    with path.open("rb") as f:
        data = tomllib.load(f)
    return model_type.model_validate(data)


def _load_builtin_definition(filename: str, model_type: type[_T]) -> _T:
    """ビルトイン定義をパッケージリソースから読み込む。

    Args:
        filename: ビルトイン定義ファイル名。
        model_type: バリデーションに使用する pydantic モデルクラス。

    Returns:
        構築された定義モデル。

    Raises:
        FileNotFoundError: ビルトイン定義が見つからない場合。
        tomllib.TOMLDecodeError: TOML 構文エラーの場合。
        pydantic.ValidationError: バリデーションエラーの場合。
    """
    builtin_package = files("hachimoku.agents._builtin")
    for resource in builtin_package.iterdir():
        if resource.name == filename:
            with as_file(resource) as path:
                return _load_single_definition(path, model_type)
    raise FileNotFoundError(f"Builtin {model_type.__name__} not found: {filename}")


def _load_definition_with_override(
    custom_dir: Path | None,
    filename: str,
    model_type: type[_T],
) -> _T:
    """ビルトインとカスタムを統合して定義を読み込む。

    カスタムディレクトリに該当ファイルが存在する場合、ビルトインを上書きする。
    カスタムファイルの読み込み失敗時はビルトインへの暗黙的な切り替えを行わず、
    例外を送出する。

    Args:
        custom_dir: カスタム定義ファイルのディレクトリパス。
            None の場合はビルトインのみ読み込む。
        filename: 定義ファイル名。
        model_type: バリデーションに使用する pydantic モデルクラス。

    Returns:
        定義モデル。

    Raises:
        FileNotFoundError: ビルトイン定義が見つからない場合。
        NotADirectoryError: custom_dir がファイルパスの場合。
        tomllib.TOMLDecodeError: TOML 構文エラーの場合。
        pydantic.ValidationError: バリデーションエラーの場合。
    """
    if custom_dir is not None:
        if custom_dir.exists() and not custom_dir.is_dir():
            raise NotADirectoryError(
                f"custom_dir はディレクトリではありません: {custom_dir}"
            )
        custom_path = custom_dir / filename
        if custom_path.exists():
            return _load_single_definition(custom_path, model_type)

    return _load_builtin_definition(filename, model_type)


# =============================================================================
# エージェント定義ローダー
# =============================================================================


def _load_single_agent(path: Path) -> AgentDefinition:
    """AgentDefinition 用の _load_single_definition ラッパー。"""
    return _load_single_definition(path, AgentDefinition)


def _collect_agents(toml_paths: Iterable[Path]) -> LoadResult:
    """TOML ファイルパスのイテラブルからエージェント定義を収集する。

    .toml 以外のファイルおよび除外対象ファイルはスキップされる。
    個々のファイルの読み込みエラーは LoadResult.errors に収集される。

    Args:
        toml_paths: ファイルパスのイテラブル。

    Returns:
        収集されたエージェント定義とエラーの読み込み結果。
    """
    agents: list[AgentDefinition] = []
    errors: list[LoadError] = []

    for path in toml_paths:
        if not path.name.endswith(".toml"):
            continue
        if path.name in _EXCLUDED_FILENAMES:
            continue
        try:
            agent = _load_single_agent(path)
            agents.append(agent)
        except (tomllib.TOMLDecodeError, ValidationError, OSError) as e:
            errors.append(
                LoadError(
                    source=path.name,
                    message=f"{type(e).__name__}: {e}",
                )
            )

    return LoadResult(agents=tuple(agents), errors=tuple(errors))


def load_builtin_agents() -> LoadResult:
    """ビルトインエージェント定義をパッケージリソースから読み込む。

    selector.toml はセレクター専用ローダーで読み込むため除外される。

    Returns:
        ビルトイン定義の読み込み結果。個々のファイルの読み込みエラーは
        LoadResult.errors に収集される。

    Raises:
        ModuleNotFoundError: ビルトインパッケージが見つからない場合。
    """
    builtin_package = files("hachimoku.agents._builtin")

    def _iter_paths() -> Iterator[Path]:
        for resource in sorted(builtin_package.iterdir(), key=lambda r: r.name):
            with as_file(resource) as path:
                yield path

    return _collect_agents(_iter_paths())


def load_custom_agents(custom_dir: Path) -> LoadResult:
    """カスタムエージェント定義を指定ディレクトリから読み込む。

    selector.toml はセレクター専用ローダーで読み込むため除外される。

    Args:
        custom_dir: カスタム定義ファイルのディレクトリパス。
            存在しない場合は空の LoadResult を返す。

    Returns:
        カスタム定義の読み込み結果。個々のファイルの読み込みエラーは
        LoadResult.errors に収集される。

    Raises:
        NotADirectoryError: custom_dir がファイルパスの場合。
    """
    if not custom_dir.exists():
        return LoadResult(agents=(), errors=())
    if not custom_dir.is_dir():
        raise NotADirectoryError(
            f"custom_dir はディレクトリではありません: {custom_dir}"
        )

    return _collect_agents(sorted(custom_dir.iterdir()))


def load_agents(custom_dir: Path | None = None) -> LoadResult:
    """ビルトインとカスタムを統合してエージェント定義を読み込む。

    カスタム定義がビルトイン定義と同名の場合、カスタム定義がビルトインを上書きする。
    カスタム定義の読み込みに失敗した場合（TOML 構文エラー、バリデーションエラー等）、
    上書きは行われずビルトイン定義がそのまま使用される。

    Args:
        custom_dir: カスタム定義ファイルのディレクトリパス。
            None の場合はビルトインのみ読み込む。

    Returns:
        統合された読み込み結果。
    """
    builtin = load_builtin_agents()
    if custom_dir is None:
        return builtin

    custom = load_custom_agents(custom_dir)

    custom_names = {a.name for a in custom.agents}
    merged_agents = [a for a in builtin.agents if a.name not in custom_names]
    merged_agents.extend(custom.agents)

    merged_errors = list(builtin.errors) + list(custom.errors)

    return LoadResult(agents=tuple(merged_agents), errors=tuple(merged_errors))


# =============================================================================
# セレクター定義ローダー
# =============================================================================


def load_builtin_selector() -> SelectorDefinition:
    """ビルトインセレクター定義をパッケージリソースから読み込む。

    Returns:
        ビルトインのセレクター定義。

    Raises:
        FileNotFoundError: ビルトインセレクター定義が見つからない場合。
        tomllib.TOMLDecodeError: TOML 構文エラーの場合。
        pydantic.ValidationError: バリデーションエラーの場合。
    """
    return _load_builtin_definition(SELECTOR_FILENAME, SelectorDefinition)


def load_selector(custom_dir: Path | None = None) -> SelectorDefinition:
    """ビルトインとカスタムを統合してセレクター定義を読み込む。

    カスタムディレクトリに selector.toml が存在する場合、ビルトインを上書きする。
    カスタムの読み込みに失敗した場合は例外を送出する。

    Args:
        custom_dir: カスタム定義ファイルのディレクトリパス。
            None の場合はビルトインのみ読み込む。

    Returns:
        セレクター定義。

    Raises:
        FileNotFoundError: ビルトインセレクター定義が見つからない場合。
        NotADirectoryError: custom_dir がファイルパスの場合。
        tomllib.TOMLDecodeError: TOML 構文エラーの場合。
        pydantic.ValidationError: バリデーションエラーの場合。
    """
    return _load_definition_with_override(
        custom_dir, SELECTOR_FILENAME, SelectorDefinition
    )


# =============================================================================
# アグリゲーター定義ローダー
# =============================================================================


def load_builtin_aggregator() -> AggregatorDefinition:
    """ビルトインアグリゲーター定義をパッケージリソースから読み込む。

    Returns:
        ビルトインのアグリゲーター定義。

    Raises:
        FileNotFoundError: ビルトインアグリゲーター定義が見つからない場合。
        tomllib.TOMLDecodeError: TOML 構文エラーの場合。
        pydantic.ValidationError: バリデーションエラーの場合。
    """
    return _load_builtin_definition(AGGREGATOR_FILENAME, AggregatorDefinition)


def load_aggregator(custom_dir: Path | None = None) -> AggregatorDefinition:
    """ビルトインとカスタムを統合してアグリゲーター定義を読み込む。

    カスタムディレクトリに aggregator.toml が存在する場合、ビルトインを上書きする。
    カスタムの読み込みに失敗した場合は例外を送出する。

    Args:
        custom_dir: カスタム定義ファイルのディレクトリパス。
            None の場合はビルトインのみ読み込む。

    Returns:
        アグリゲーター定義。

    Raises:
        FileNotFoundError: ビルトインアグリゲーター定義が見つからない場合。
        NotADirectoryError: custom_dir がファイルパスの場合。
        tomllib.TOMLDecodeError: TOML 構文エラーの場合。
        pydantic.ValidationError: バリデーションエラーの場合。
    """
    return _load_definition_with_override(
        custom_dir, AGGREGATOR_FILENAME, AggregatorDefinition
    )
