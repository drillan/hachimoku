"""設定リゾルバー。

FR-CF-007: 項目単位のマージ
R-005: CLI オプションの None 除外
"""

from __future__ import annotations

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
