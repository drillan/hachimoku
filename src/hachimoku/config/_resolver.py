"""設定リゾルバー。

FR-CF-001: 5層の設定ソースの階層解決
FR-CF-007: 項目単位のマージ
R-005: CLI オプションの None 除外
"""

from __future__ import annotations

from pathlib import Path

from hachimoku.config._loader import load_pyproject_config, load_toml_config
from hachimoku.config._locator import (
    find_config_file,
    find_pyproject_toml,
    get_user_config_path,
)
from hachimoku.models.config import HachimokuConfig

_AGENTS_KEY: str = "agents"


def _merge_agents(
    base: dict[str, object] | None,
    override: dict[str, object],
) -> dict[str, object]:
    """agents セクションをエージェント名→フィールド単位でマージする。

    返却値はシャローコピー。各エージェント設定の内部辞書は新規作成されるが、
    スカラー値自体は元の辞書と共有される。

    Args:
        base: 既存の agents 辞書。None の場合は空として扱う。
        override: 上書きする agents 辞書。

    Returns:
        マージ済みの agents 辞書。

    Raises:
        TypeError: エージェント設定が dict でない場合。
    """
    for agent_name, agent_config in override.items():
        if not isinstance(agent_config, dict):
            msg = (
                f"Agent config for '{agent_name}' must be a dict, "
                f"got {type(agent_config).__name__}"
            )
            raise TypeError(msg)
    if base is None:
        return dict(override)
    merged: dict[str, object] = dict(base)
    for agent_name, agent_config in override.items():
        existing = merged.get(agent_name)
        if isinstance(existing, dict) and isinstance(agent_config, dict):
            merged_agent = dict(existing)
            merged_agent.update(agent_config)
            merged[agent_name] = merged_agent
        else:
            merged[agent_name] = agent_config
    return merged


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
    result: dict[str, object] = {}
    for layer in layers:
        if layer is None:
            continue
        for key, value in layer.items():
            if key == _AGENTS_KEY:
                if not isinstance(value, dict):
                    msg = f"'{_AGENTS_KEY}' must be a dict, got {type(value).__name__}"
                    raise TypeError(msg)
                result[_AGENTS_KEY] = _merge_agents(
                    result.get(_AGENTS_KEY, None),  # type: ignore[arg-type]
                    value,
                )
            else:
                result[key] = value
    return result


def filter_cli_overrides(cli_options: dict[str, object]) -> dict[str, object]:
    """CLI オプション辞書から None 値を除外する。

    None 値は「未指定」を意味し、マージ対象から除外する。

    Args:
        cli_options: CLI パーサーから渡された辞書。

    Returns:
        None 値を除外した辞書。
    """
    return {k: v for k, v in cli_options.items() if v is not None}


def resolve_config(
    start_dir: Path | None = None,
    cli_overrides: dict[str, object] | None = None,
) -> HachimokuConfig:
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
    effective_start = start_dir if start_dir is not None else Path.cwd()

    # Layer 1 (最低優先): ユーザーグローバル設定
    user_layer: dict[str, object] | None = None
    try:
        user_layer = load_toml_config(get_user_config_path())
    except FileNotFoundError:
        pass

    # Layer 2: pyproject.toml [tool.hachimoku]
    pyproject_layer: dict[str, object] | None = None
    pyproject_path = find_pyproject_toml(effective_start)
    if pyproject_path is not None:
        pyproject_layer = load_pyproject_config(pyproject_path)

    # Layer 3: .hachimoku/config.toml
    config_layer: dict[str, object] | None = None
    config_path = find_config_file(effective_start)
    if config_path is not None:
        # find_config_file はパス構築のみで config.toml の存在チェックをしないため、
        # .hachimoku/ ディレクトリはあるが config.toml が未作成のケースに対応する。
        try:
            config_layer = load_toml_config(config_path)
        except FileNotFoundError:
            pass

    # Layer 4 (最高優先): CLI overrides
    cli_layer: dict[str, object] | None = None
    if cli_overrides is not None:
        cli_layer = filter_cli_overrides(cli_overrides)

    # マージ (低優先度 → 高優先度の順)
    merged = merge_config_layers(user_layer, pyproject_layer, config_layer, cli_layer)

    # Layer 5 (最低優先): デフォルト値 -- HachimokuConfig のフィールドデフォルトが適用される
    return HachimokuConfig(**merged)  # type: ignore[arg-type]
