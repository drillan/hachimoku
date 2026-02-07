"""InputResolver contract — 位置引数からの入力モード判定。

FR-CLI-002: 位置引数の優先順ルールに基づくモード自動判定。
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Union

from pydantic import Field

from hachimoku.models._base import HachimokuBaseModel


class DiffInput(HachimokuBaseModel):
    """diff モード判定結果（引数なし）。"""

    mode: Literal["diff"] = "diff"


class PRInput(HachimokuBaseModel):
    """PR モード判定結果（整数引数）。"""

    mode: Literal["pr"] = "pr"
    pr_number: int = Field(gt=0)


class FileInput(HachimokuBaseModel):
    """file モード判定結果（パスライク引数）。"""

    mode: Literal["file"] = "file"
    paths: tuple[Annotated[str, Field(min_length=1)], ...] = Field(min_length=1)


ResolvedInput = Annotated[
    Union[DiffInput, PRInput, FileInput],
    Field(discriminator="mode"),
]
"""入力モード判定結果の判別共用体。"""


class InputError(Exception):
    """入力モード判定エラー。

    エラーメッセージは解決方法のヒントを含む（憲法 Art.3）。
    """


def resolve_input(args: list[str] | None) -> ResolvedInput:
    """位置引数から入力モードを判定する。

    FR-CLI-002 の優先順ルール（サブコマンドは Typer が処理済み）:
    1. 全引数が正の整数、かつ引数が1つ → PRInput
    2. パスライク文字列（/, \\, *, ?, . を含む）→ FileInput
    3. ファイルシステム上に存在するパス → FileInput
    4. 引数なし → DiffInput
    5. 上記のいずれにも該当しない → InputError

    PR 番号とファイルパスの同時指定（整数と非整数の混在）→ InputError

    Args:
        args: 位置引数のリスト。None または空リストは引数なし（diff モード）。

    Returns:
        ResolvedInput: 判定された入力モード。

    Raises:
        InputError: 判定不可能な引数パターンの場合。
    """
    ...


def _is_path_like(arg: str) -> bool:
    """引数がパスライク文字列かどうかを判定する。

    パスライク: /, \\, *, ?, . のいずれかを含む文字列。
    """
    ...


def _is_existing_path(arg: str) -> bool:
    """引数がファイルシステム上に存在するパスかどうかを判定する。"""
    ...
