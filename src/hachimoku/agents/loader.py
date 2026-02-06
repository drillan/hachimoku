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
