"""TOML ローダーのテスト。

T020: load_toml_config — 有効 TOML, 空ファイル, 構文エラー, 不在, 権限なし
T021: load_pyproject_config — セクションあり, 空セクション, セクションなし, tool なし, 構文エラー
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

import pytest

from hachimoku.config._loader import load_pyproject_config, load_toml_config

# =============================================================================
# ヘルパー
# =============================================================================

_SKIP_PERMISSION = pytest.mark.skipif(
    os.name == "nt" or os.getuid() == 0,
    reason="POSIX permissions required and not running as root",
)


def _write_toml(path: Path, content: str) -> Path:
    """TOML ファイルを書き込みパスを返す。"""
    path.write_text(content, encoding="utf-8")
    return path


# =============================================================================
# T020: load_toml_config()
# =============================================================================


class TestLoadTomlConfigValid:
    """有効な TOML ファイルの読み込み。"""

    def test_returns_parsed_dict(self, tmp_path: Path) -> None:
        """有効な TOML → 辞書返却。"""
        path = _write_toml(
            tmp_path / "config.toml",
            'model = "opus"\ntimeout = 600\n',
        )
        result = load_toml_config(path)
        assert result == {"model": "opus", "timeout": 600}

    def test_nested_tables(self, tmp_path: Path) -> None:
        """ネストしたテーブルを含む TOML → 正しくパース。"""
        path = _write_toml(
            tmp_path / "config.toml",
            '[agents.code-reviewer]\nenabled = false\nmodel = "haiku"\n',
        )
        result = load_toml_config(path)
        assert result == {
            "agents": {"code-reviewer": {"enabled": False, "model": "haiku"}}
        }


class TestLoadTomlConfigEmpty:
    """空の TOML ファイルの読み込み。"""

    def test_returns_empty_dict(self, tmp_path: Path) -> None:
        """空ファイル → 空辞書。"""
        path = _write_toml(tmp_path / "config.toml", "")
        result = load_toml_config(path)
        assert result == {}


class TestLoadTomlConfigSyntaxError:
    """TOML 構文エラー。"""

    def test_raises_toml_decode_error(self, tmp_path: Path) -> None:
        """TOML 構文エラー → TOMLDecodeError。"""
        path = _write_toml(tmp_path / "config.toml", "invalid = = = toml")
        with pytest.raises(tomllib.TOMLDecodeError):
            load_toml_config(path)


class TestLoadTomlConfigFileNotFound:
    """ファイル不在。"""

    def test_raises_file_not_found_error(self, tmp_path: Path) -> None:
        """ファイル不在 → FileNotFoundError。"""
        path = tmp_path / "nonexistent.toml"
        with pytest.raises(FileNotFoundError):
            load_toml_config(path)


class TestLoadTomlConfigPermissionError:
    """読み取り権限なし。"""

    @_SKIP_PERMISSION
    def test_raises_permission_error(self, tmp_path: Path) -> None:
        """読み取り権限なし → PermissionError。"""
        path = _write_toml(tmp_path / "config.toml", 'model = "opus"\n')
        path.chmod(0o000)
        try:
            with pytest.raises(PermissionError):
                load_toml_config(path)
        finally:
            path.chmod(0o644)


# =============================================================================
# T021: load_pyproject_config()
# =============================================================================


class TestLoadPyprojectConfigWithSection:
    """[tool.hachimoku] セクションあり。"""

    def test_returns_section_dict(self, tmp_path: Path) -> None:
        """[tool.hachimoku] セクションあり → そのセクションの辞書。"""
        path = _write_toml(
            tmp_path / "pyproject.toml",
            '[tool.hachimoku]\nmodel = "opus"\ntimeout = 600\n',
        )
        result = load_pyproject_config(path)
        assert result == {"model": "opus", "timeout": 600}


class TestLoadPyprojectConfigEmptySection:
    """[tool.hachimoku] セクションあるが空。"""

    def test_returns_empty_dict(self, tmp_path: Path) -> None:
        """[tool.hachimoku] あるが空 → 空辞書。"""
        path = _write_toml(
            tmp_path / "pyproject.toml",
            "[tool.hachimoku]\n",
        )
        result = load_pyproject_config(path)
        assert result == {}


class TestLoadPyprojectConfigNoSection:
    """[tool.hachimoku] セクションなし。"""

    def test_returns_none(self, tmp_path: Path) -> None:
        """[tool.hachimoku] なし → None。"""
        path = _write_toml(
            tmp_path / "pyproject.toml",
            "[tool.ruff]\nline-length = 88\n",
        )
        result = load_pyproject_config(path)
        assert result is None


class TestLoadPyprojectConfigNoToolSection:
    """[tool] セクション自体なし。"""

    def test_returns_none(self, tmp_path: Path) -> None:
        """[tool] なし → None。"""
        path = _write_toml(
            tmp_path / "pyproject.toml",
            '[project]\nname = "test"\n',
        )
        result = load_pyproject_config(path)
        assert result is None


class TestLoadPyprojectConfigNonDictHachimoku:
    """tool.hachimoku が辞書でない場合。"""

    def test_returns_none_when_hachimoku_is_string(self, tmp_path: Path) -> None:
        """tool.hachimoku が文字列 → None。"""
        path = _write_toml(
            tmp_path / "pyproject.toml",
            '[tool]\nhachimoku = "not-a-dict"\n',
        )
        result = load_pyproject_config(path)
        assert result is None


class TestLoadPyprojectConfigSyntaxError:
    """TOML 構文エラー。"""

    def test_raises_toml_decode_error(self, tmp_path: Path) -> None:
        """TOML 構文エラー → TOMLDecodeError。"""
        path = _write_toml(tmp_path / "pyproject.toml", "[invalid\n")
        with pytest.raises(tomllib.TOMLDecodeError):
            load_pyproject_config(path)


class TestLoadPyprojectConfigFileNotFound:
    """ファイル不在。"""

    def test_raises_file_not_found_error(self, tmp_path: Path) -> None:
        """ファイル不在 → FileNotFoundError。"""
        path = tmp_path / "nonexistent.toml"
        with pytest.raises(FileNotFoundError):
            load_pyproject_config(path)


class TestLoadPyprojectConfigPermissionError:
    """読み取り権限なし。"""

    @_SKIP_PERMISSION
    def test_raises_permission_error(self, tmp_path: Path) -> None:
        """読み取り権限なし → PermissionError。"""
        path = _write_toml(
            tmp_path / "pyproject.toml",
            '[tool.hachimoku]\nmodel = "opus"\n',
        )
        path.chmod(0o000)
        try:
            with pytest.raises(PermissionError):
                load_pyproject_config(path)
        finally:
            path.chmod(0o644)
