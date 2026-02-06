"""エージェント定義ローダー。

TOML 形式のエージェント定義ファイルを読み込み、AgentDefinition モデルとして構築する。
"""

from __future__ import annotations

import tomllib
from importlib.resources import as_file, files
from pathlib import Path

from pydantic import ValidationError

from hachimoku.agents.models import AgentDefinition, LoadError, LoadResult


def _load_single_agent(path: Path) -> AgentDefinition:
    """単一の TOML ファイルからエージェント定義を読み込む。

    Args:
        path: TOML ファイルのパス。

    Returns:
        構築された AgentDefinition。

    Raises:
        tomllib.TOMLDecodeError: TOML 構文エラーの場合。
        pydantic.ValidationError: バリデーションエラーの場合。
        FileNotFoundError: ファイルが存在しない場合。
    """
    with path.open("rb") as f:
        data = tomllib.load(f)
    return AgentDefinition.model_validate(data)


def load_builtin_agents() -> LoadResult:
    """ビルトインエージェント定義をパッケージリソースから読み込む。

    Returns:
        ビルトイン定義の読み込み結果。個々のファイルの読み込みエラーは
        LoadResult.errors に収集される。

    Raises:
        ModuleNotFoundError: ビルトインパッケージが見つからない場合。
    """
    builtin_package = files("hachimoku.agents._builtin")
    agents: list[AgentDefinition] = []
    errors: list[LoadError] = []

    for resource in builtin_package.iterdir():
        if not resource.name.endswith(".toml"):
            continue
        try:
            with as_file(resource) as path:
                agent = _load_single_agent(path)
            agents.append(agent)
        except (tomllib.TOMLDecodeError, ValidationError, OSError) as e:
            errors.append(
                LoadError(
                    source=resource.name,
                    message=f"{type(e).__name__}: {e}",
                )
            )

    return LoadResult(agents=tuple(agents), errors=tuple(errors))


def load_custom_agents(custom_dir: Path) -> LoadResult:
    """カスタムエージェント定義を指定ディレクトリから読み込む。

    Args:
        custom_dir: カスタム定義ファイルのディレクトリパス。
            存在しない場合は空の LoadResult を返す。

    Returns:
        カスタム定義の読み込み結果。個々のファイルの読み込みエラーは
        LoadResult.errors に収集される。
    """
    if not custom_dir.is_dir():
        return LoadResult(agents=(), errors=())

    agents: list[AgentDefinition] = []
    errors: list[LoadError] = []

    for toml_path in sorted(custom_dir.iterdir()):
        if not toml_path.name.endswith(".toml"):
            continue
        try:
            agent = _load_single_agent(toml_path)
            agents.append(agent)
        except (tomllib.TOMLDecodeError, ValidationError, OSError) as e:
            errors.append(
                LoadError(
                    source=toml_path.name,
                    message=f"{type(e).__name__}: {e}",
                )
            )

    return LoadResult(agents=tuple(agents), errors=tuple(errors))


def load_agents(custom_dir: Path | None = None) -> LoadResult:
    """ビルトインとカスタムを統合してエージェント定義を読み込む。

    カスタム定義がビルトイン定義と同名の場合、カスタム定義がビルトインを上書きする。
    カスタム定義がバリデーションエラーの場合、上書きは行われず
    ビルトイン定義がそのまま使用される。

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
