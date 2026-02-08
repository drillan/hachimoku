"""InputResolver — 位置引数からの入力モード判定。

FR-CLI-002: 位置引数の優先順ルールに基づくモード自動判定。
"""

from __future__ import annotations

import os
from typing import Annotated, Literal, Union

from pydantic import Field

from hachimoku.models._base import HachimokuBaseModel

_PATH_LIKE_CHARS = frozenset("/\\*?.")


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


ResolvedInput = Union[DiffInput, PRInput, FileInput]
"""入力モード判定結果の共用体型。"""


class InputError(Exception):
    """入力モード判定エラー。

    エラーメッセージは解決方法のヒントを含む（憲法 Art.3）。
    """


def resolve_input(args: list[str] | None) -> ResolvedInput:
    """位置引数から入力モードを判定する。

    FR-CLI-002 の優先順ルール:
    1. 全引数が正の整数、かつ引数が1つ → PRInput
    2. パスライク文字列を含む → FileInput
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
    if not args:
        return DiffInput()

    integer_args: list[str] = []
    non_integer_args: list[str] = []

    for arg in args:
        if _is_positive_integer(arg):
            integer_args.append(arg)
        else:
            non_integer_args.append(arg)

    # 整数と非整数の混在 → エラー
    if integer_args and non_integer_args:
        raise InputError(
            f"Cannot mix PR number and file paths: {', '.join(args)}. "
            "Specify either a single PR number or file paths, not both."
        )

    # 全引数が正の整数
    if integer_args:
        if len(integer_args) == 1:
            return PRInput(pr_number=int(integer_args[0]))
        raise InputError(
            f"Multiple PR numbers specified: {', '.join(integer_args)}. "
            "Specify a single PR number for PR mode."
        )

    # パスライク文字列チェック
    if any(_is_path_like(arg) for arg in args):
        return FileInput(paths=tuple(args))

    # ファイルシステム存在チェック
    if any(_is_existing_path(arg) for arg in args):
        return FileInput(paths=tuple(args))

    # いずれにも該当しない → エラー
    raise InputError(
        f"Unrecognized argument: '{args[0]}'. "
        "Use a PR number, file path, or run without arguments for diff mode."
    )


def _is_positive_integer(arg: str) -> bool:
    """引数が正の整数文字列かどうかを判定する。"""
    try:
        return int(arg) > 0
    except ValueError:
        return False


def _is_path_like(arg: str) -> bool:
    """引数がパスライク文字列かどうかを判定する。

    パスライク: /, \\, *, ?, . のいずれかを含む文字列。
    """
    return bool(arg) and bool(set(arg) & _PATH_LIKE_CHARS)


def _is_existing_path(arg: str) -> bool:
    """引数がファイルシステム上に存在するパスかどうかを判定する。"""
    return bool(arg) and os.path.exists(arg)
